"""R module: query analysis, planning and four retrieval channels.

The runner is deliberately explicit: analyze -> plan -> execute nodes (respecting
dependencies) -> merge candidates.  S3 stops after retrieval; fusion/rerank belong
to M (S4), so ``merge`` only deduplicates and labels the channels that found each
candidate.

Every channel is an implementation on the ``retrieval.channel`` axis, every planner
on ``planner`` and every analyzer on ``planner.analyzer``, so E1 can swap them
through config.  Per-node results are cached with the content-addressed
:class:`~memlab.cache.ArtifactCache`; the key includes the store's index hash.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping, Sequence

from . import model
from .contracts import Candidate, Plan, PlanNode, QueryFrame
from .registry import UnknownImplementation
from .registry import build as build_impl
from .registry import get as get_impl
from .registry import register
from .trace import Trace
from .write import Parametrised, fact_fields

AXIS_ANALYZER = "planner.analyzer"
AXIS_PLANNER = "planner"
AXIS_CHANNEL = "retrieval.channel"
AXIS_GRAPH_RETRIEVAL = "graph.retrieval"


def _store(ctx: Any) -> Any:
    store = getattr(ctx, "store", None)
    if store is None:
        raise ValueError("runtime has no store; build one with memlab.ingest.build_store")
    return store


def _config(ctx: Any) -> Any:
    return getattr(ctx, "config", None)


def _config_get(ctx: Any, path: str, default: Any = None) -> Any:
    config = _config(ctx)
    return config.get(path, default) if config is not None and hasattr(config, "get") else default


def _config_impl(ctx: Any, path: str) -> str | None:
    config = _config(ctx)
    if config is not None and hasattr(config, "impl"):
        return config.impl(path)
    return None


def _k(ctx: Any, requested: int | None) -> int:
    if requested is not None:
        return max(1, int(requested))
    configured = _config_get(ctx, "retrieval.k", 15)
    return max(1, int(configured or 15))


# ---- query analyzer ----------------------------------------------------

@register(AXIS_ANALYZER, "none")
class NoneAnalyzer(Parametrised):
    def analyze(self, query: str, ctx: Any) -> QueryFrame:
        return QueryFrame(query=str(query))


@register(AXIS_ANALYZER, "rule")
class RuleAnalyzer(Parametrised):
    TEMPORAL = re.compile(
        r"\b(when|what date|what time|how long|before|after|last|next|ago|currently|now|used to|"
        r"since|until|year|month|day|week|morning|evening)\b", re.IGNORECASE,
    )
    MULTI_HOP = re.compile(
        r"\b(both|after|before|then|first|relationship between|how many|why|which of|which one|"
        r"and then|between)\b", re.IGNORECASE,
    )
    AS_OF = re.compile(r"\bas of\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
    PROPER = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")

    def analyze(self, query: str, ctx: Any) -> QueryFrame:
        text = " ".join(str(query).split())
        temporal = bool(self.TEMPORAL.search(text))
        multi_hop = bool(self.MULTI_HOP.search(text))
        entities = sorted({match.group(0).casefold() for match in self.PROPER.finditer(text)
                           if match.start() > 0})
        complexity = min(1.0, 0.25 * sum((temporal, multi_hop)) + 0.1 * len(entities))
        if temporal:
            intent = "temporal"
        elif multi_hop or complexity >= 0.5:
            intent = "multi_hop"
        else:
            intent = "single_hop"
        match = self.AS_OF.search(text)
        as_of = model.parse_time(match.group(1)) if match else None
        return QueryFrame(
            query=text,
            as_of=as_of,
            intent=intent,
            entity_ids=entities,
            temporal={"time_intent": temporal},
            complexity=round(complexity, 3),
            filters={"temporal": temporal, "multi_hop": multi_hop},
        )


# ---- planner -----------------------------------------------------------

def _planner_params(ctx: Any) -> dict[str, Any]:
    config = _config(ctx)
    return config.params("planner") if config is not None and hasattr(config, "params") else {}


def _node(node_id: str, frame: QueryFrame, channel: str, k: int,
          depends_on: Sequence[str] = ()) -> PlanNode:
    return PlanNode(node_id=node_id, query=frame.query, channel=channel,
                    depends_on=list(depends_on), k=k, filters={})


def _graph_impl_name(ctx: Any) -> str:
    """Selected graph-retrieval implementation (never inferred from the channel)."""
    return _config_impl(ctx, "graph.retrieval") or "entity_subgraph"


def _graph_enabled(ctx: Any) -> bool:
    """A graph channel exists only when the impl needs one and a graph exists.

    ``vector_only`` is the explicit off switch: it must suppress the graph channel
    for every intent, including multi-hop.  ``graph.repr=none`` also disables it.
    """
    if _graph_impl_name(ctx) == "vector_only":
        return False
    return (_config_impl(ctx, "graph.repr") or "state_slot") != "none"


def _channels_for(frame: QueryFrame, ctx: Any = None) -> list[str]:
    if frame.intent == "temporal" or frame.as_of is not None:
        return ["temporal", "bm25"]
    if frame.intent == "multi_hop" or frame.complexity >= 0.5:
        if _graph_enabled(ctx):
            return ["bm25", "graph_khop"]
        # vector_only keeps the lexical channel and replaces the graph with dense.
        return ["bm25", "dense"]
    return ["bm25", "dense"]


@register(AXIS_PLANNER, "none")
class NonePlanner(Parametrised):
    def plan(self, frame: QueryFrame, ctx: Any) -> Plan:
        k = _k(ctx, None)
        node = _node("n1", frame, "bm25", k)
        return Plan(nodes=[node], parallel_groups=[["n1"]], rationale="one query, one BM25 search")


@register(AXIS_PLANNER, "rule_router")
class RuleRouterPlanner(Parametrised):
    def plan(self, frame: QueryFrame, ctx: Any) -> Plan:
        k = _k(ctx, None)
        params = _planner_params(ctx)
        channels = _channels_for(frame, ctx)
        if params.get("temporal_forced") and "temporal" not in channels and frame.temporal.get("time_intent"):
            channels.insert(0, "temporal")
        nodes = [_node(f"n{index}", frame, channel, k) for index, channel in enumerate(channels, 1)]
        return Plan(nodes=nodes, parallel_groups=[[node.node_id for node in nodes]],
                    rationale=f"intent={frame.intent}; route={channels}")


@register(AXIS_PLANNER, "dag")
class DagPlanner(Parametrised):
    """Rule-based DAG: multi-hop expands graph from a lexical seed set."""

    def plan(self, frame: QueryFrame, ctx: Any) -> Plan:
        k = _k(ctx, None)
        if frame.intent == "multi_hop":
            if _graph_enabled(ctx):
                nodes = [_node("n1", frame, "bm25", k),
                         _node("n2", frame, "graph_khop", k, depends_on=["n1"])]
                groups = [["n1"], ["n2"]]
            else:
                nodes = [_node("n1", frame, "bm25", k), _node("n2", frame, "dense", k)]
                groups = [["n1", "n2"]]
        elif frame.intent == "temporal" or frame.as_of is not None:
            nodes = [_node("n1", frame, "bm25", k), _node("n2", frame, "temporal", k)]
            groups = [["n1", "n2"]]
        else:
            nodes = [_node("n1", frame, "bm25", k)]
            groups = [["n1"]]
        return Plan(nodes=nodes, parallel_groups=groups, rationale=f"dag for intent={frame.intent}")


# ---- channels ----------------------------------------------------------

def _ranked(scores: Mapping[str, float], node: PlanNode, channel: str, k: int,
            **provenance: Any) -> list[Candidate]:
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
    return [
        Candidate(memory_id=memory_id, channel=channel, rank=rank, raw_score=score, score=score,
                  stage_scores={channel: score},
                  provenance={"retriever": channel, **provenance})
        for rank, (memory_id, score) in enumerate(ordered, 1)
    ]


class ChannelRetriever(Parametrised):
    axis = AXIS_CHANNEL
    name = ""

    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        raise NotImplementedError


@register(AXIS_CHANNEL, "bm25")
class BM25Retriever(ChannelRetriever):
    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        store = _store(ctx)
        return _ranked(store.bm25_scores(node.query or frame.query), node, "bm25", k)


@register(AXIS_CHANNEL, "dense")
class DenseRetriever(ChannelRetriever):
    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        store = _store(ctx)
        client = getattr(ctx, "embedding", None)
        if client is None:
            raise ValueError("dense retrieval requires an embedding client")
        scores = store.dense_scores(node.query or frame.query, client, getattr(ctx, "cache", None))
        return _ranked(scores, node, "dense", k)


# ---- graph retrieval dispatch -----------------------------------------
#
# ``retrieval.channel=graph_khop`` is one channel; *how* it fills candidates is
# selected by ``graph.retrieval.impl``.  Before R3 the impl switch was only
# validated and its params were read, while the channel always ran k-hop.  The
# classes below are the dispatch targets, registered on their own axis so an
# unknown/unimplemented impl fails closed instead of silently becoming k-hop.

class GraphRetriever:
    """One graph-retrieval implementation over an already-built GraphIndex."""

    axis = AXIS_GRAPH_RETRIEVAL
    name = ""
    params_allowed: frozenset[str] = frozenset()

    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any,
                 params: Mapping[str, Any]) -> list[Candidate]:
        raise NotImplementedError


def _graph_params(ctx: Any) -> dict[str, Any]:
    config = _config(ctx)
    return config.params("graph.retrieval") if config is not None and hasattr(config, "params") else {}


def _graph_representation(ctx: Any) -> str:
    return _config_impl(ctx, "graph.repr") or "state_slot"


def _graph_seeds(frame: QueryFrame, node: PlanNode, ctx: Any, limit: int = 3) -> list[str]:
    seeds = [str(item) for item in node.filters.get("seed_ids") or []]
    if seeds:
        return list(dict.fromkeys(seeds))
    store = _store(ctx)
    scores = store.bm25_scores(node.query or frame.query)
    return [memory_id for memory_id, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _graph_candidate(store: Any, memory_id: str, rank: int, score: float, impl: str,
                     representation: str, **extra: Any) -> Candidate | None:
    unit = store.get(memory_id)
    if unit is None:  # auxiliary layers (entity:/event:/topic:) are not memories
        return None
    return Candidate(
        memory_id=unit.memory_id, channel="graph_khop", rank=rank,
        raw_score=score, score=score, stage_scores={"graph_khop": score},
        provenance={"retriever": "graph_khop", "retrieval_impl": impl,
                    "representation": representation, **extra},
    )


@register(AXIS_GRAPH_RETRIEVAL, "vector_only")
class VectorOnlyGraphRetriever(GraphRetriever):
    """No graph candidates; the router must not add the graph channel either."""

    def retrieve(self, frame, node, k, ctx, params):
        return []


@register(AXIS_GRAPH_RETRIEVAL, "slot_expand")
class SlotExpandGraphRetriever(GraphRetriever):
    """Same-slot version-chain expansion (state_slot only, ``params.limit``)."""

    params_allowed = frozenset({"limit"})

    @staticmethod
    def _fact_key(unit: Any) -> tuple[str, str] | None:
        if unit is None or unit.kind != "fact":
            return None
        fields = fact_fields(unit)
        entity = str(fields.get("entity") or "").casefold()
        slot = str(fields.get("slot") or fields.get("attribute") or "")
        if not slot:
            return None
        return entity, slot

    def retrieve(self, frame, node, k, ctx, params):
        store = _store(ctx)
        representation = _graph_representation(ctx)
        if representation != "state_slot":
            # config validation already rejects this; keep the runtime fail-closed
            # too so a hand-built context cannot silently graph-expand another repr.
            raise ValueError("graph.retrieval.impl=slot_expand requires graph.repr=state_slot")
        limit = max(1, int(params.get("limit", 8) or 8))
        graph = store.ensure_graph("state_slot")
        seeds = _graph_seeds(frame, node, ctx)

        # Seeds may be facts or ordinary memory units; a turn seed is mapped to
        # the facts it is evidence for, then the slot group does the expansion.
        initial: list[Any] = []
        for seed in seeds:
            unit = store.get(seed)
            if unit is not None and unit.kind == "fact" and self._fact_key(unit):
                initial.append(unit)
            for neighbor in graph.neighbors(seed):
                candidate = store.get(neighbor)
                if candidate is not None and candidate.kind == "fact" and self._fact_key(candidate):
                    initial.append(candidate)

        groups: dict[tuple[str, str], list[Any]] = {}
        for unit in store.units:
            key = self._fact_key(unit)
            if key is not None:
                groups.setdefault(key, []).append(unit)
        for group in groups.values():
            group.sort(key=lambda unit: (
                (unit.t_ingest.start.isoformat() if unit.t_ingest and unit.t_ingest.start else ""),
                unit.memory_id,
            ))

        ordered: list[tuple[Any, int]] = []
        seen: set[str] = set()
        for unit in initial:
            key = self._fact_key(unit)
            if key is None:
                continue
            group = groups.get(key) or []
            if unit not in group:
                continue
            position = group.index(unit)
            offsets = [0]
            for distance in range(1, len(group)):
                offsets.extend((distance, -distance))
            for offset in offsets:
                index = position + offset
                if not 0 <= index < len(group):
                    continue
                candidate = group[index]
                if candidate.memory_id in seen:
                    continue
                seen.add(candidate.memory_id)
                ordered.append((candidate, abs(offset)))
                if len(ordered) >= limit:
                    break
            if len(ordered) >= limit:
                break

        # No fact seed: keep the one-hop evidence facts so the channel is never
        # silently empty when the query only matched a turn.
        if not ordered:
            for seed in seeds:
                for neighbor in graph.neighbors(seed):
                    candidate = store.get(neighbor)
                    if candidate is not None and candidate.kind == "fact" and candidate.memory_id not in seen:
                        seen.add(candidate.memory_id)
                        ordered.append((candidate, 1))
                        if len(ordered) >= limit:
                            break
                if len(ordered) >= limit:
                    break

        candidates: list[Candidate] = []
        for unit, distance in ordered:
            score = 1.0 / (1 + distance)
            candidate = _graph_candidate(store, unit.memory_id, len(candidates) + 1, score,
                                         "slot_expand", representation,
                                         limit=limit, version_distance=distance,
                                         slot=self._fact_key(unit))
            if candidate is not None:
                candidates.append(candidate)
        return candidates[:k]


@register(AXIS_GRAPH_RETRIEVAL, "entity_subgraph")
class EntitySubgraphGraphRetriever(GraphRetriever):
    """The original k-hop expansion: seeds first, then distance-decayed neighbours."""

    params_allowed = frozenset({"k_hop", "max_neighbors"})

    def retrieve(self, frame, node, k, ctx, params):
        store = _store(ctx)
        representation = _graph_representation(ctx)
        k_hop = int(node.filters.get("k_hop", params.get("k_hop", 2)) or 2)
        max_neighbors = params.get("max_neighbors")
        graph = store.ensure_graph(representation)
        seeds = _graph_seeds(frame, node, ctx)
        candidates: list[Candidate] = []
        for node_id, distance in graph.expand(seeds, k_hop, max_neighbors=max_neighbors):
            score = 1.0 / (1 + distance)
            candidate = _graph_candidate(store, node_id, len(candidates) + 1, score,
                                         "entity_subgraph", representation,
                                         distance=distance, seeds=seeds[:5],
                                         k_hop=k_hop, max_neighbors=max_neighbors)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= k:
                break
        return candidates


@register(AXIS_GRAPH_RETRIEVAL, "dual_channel")
class DualChannelGraphRetriever(GraphRetriever):
    """Entity-seed and lexical/relation-seed channels, weighted and merged.

    APPROXIMATION: :class:`~memlab.store.GraphIndex` is an undirected, untyped
    adjacency list.  It does not record whether an edge is a relation, an entity
    membership, a slot-version link or an evidence link, so the "entity" channel
    here is the k-hop expansion and the "semantic/relation" channel is the lexical
    (BM25) score of each candidate, normalised.  ``channel_weights`` is therefore
    consumed, but the two channels are not the typed GraphRAG channels; this is
    why the result is reported as an approximate dual channel, not exact.
    """

    params_allowed = frozenset({"k_hop", "max_neighbors", "channel_weights"})

    def retrieve(self, frame, node, k, ctx, params):
        store = _store(ctx)
        representation = _graph_representation(ctx)
        k_hop = int(node.filters.get("k_hop", params.get("k_hop", 2)) or 2)
        max_neighbors = params.get("max_neighbors")
        weights = params.get("channel_weights") or {"entity": 0.6, "semantic": 0.4}
        entity_weight = float(weights.get("entity", 0.6) or 0.0)
        semantic_weight = float(weights.get("semantic", 0.4) or 0.0)
        graph = store.ensure_graph(representation)
        seeds = _graph_seeds(frame, node, ctx)
        expansion = graph.expand(seeds, k_hop, max_neighbors=max_neighbors)
        entity_scores = {node_id: 1.0 / (1 + distance) for node_id, distance in expansion}
        lexical = store.bm25_scores(node.query or frame.query)
        scale = max(lexical.values(), default=0.0) or 1.0
        merged: dict[str, float] = {}
        for node_id, entity_score in entity_scores.items():
            if store.get(node_id) is None:
                continue
            semantic_score = float(lexical.get(node_id, 0.0)) / scale
            merged[node_id] = entity_weight * entity_score + semantic_weight * semantic_score
        ordered = sorted(merged.items(), key=lambda item: (-item[1], item[0]))[:k]
        candidates: list[Candidate] = []
        for rank, (node_id, score) in enumerate(ordered, 1):
            candidate = _graph_candidate(store, node_id, rank, score, "dual_channel", representation,
                                         seeds=seeds[:5], channel_weights={
                                             "entity": entity_weight, "semantic": semantic_weight})
            if candidate is not None:
                candidates.append(candidate)
        return candidates


@register(AXIS_GRAPH_RETRIEVAL, "ppr")
class PersonalisedPageRankGraphRetriever(GraphRetriever):
    """Pure-Python power iteration for personalised PageRank (alpha=0.15, top_k=30).

    ``alpha`` is the teleport/restart probability (so 0.85 is the damping factor).
    Iteration count is fixed rather than convergence-tested so the same graph and
    seeds always produce byte-identical scores, which the R3 determinism test checks.
    """

    params_allowed = frozenset({"alpha", "top_k", "iterations"})

    def retrieve(self, frame, node, k, ctx, params):
        store = _store(ctx)
        representation = _graph_representation(ctx)
        alpha = float(params.get("alpha", 0.15) if params.get("alpha") is not None else 0.15)
        top_k = max(1, int(params.get("top_k", 30) or 30))
        iterations = max(1, int(params.get("iterations", 50) or 50))
        graph = store.ensure_graph(representation)
        nodes = sorted(graph.nodes)
        if not nodes:
            return []
        neighbours = {node_id: sorted(graph.adj.get(node_id, ())) for node_id in nodes}
        seeds = [seed for seed in _graph_seeds(frame, node, ctx) if seed in neighbours]
        if not seeds:
            seeds = [node_id for node_id in nodes if store.get(node_id) is not None][:3]
        teleport = {seed: 1.0 / len(seeds) for seed in seeds} if seeds else {}
        if not teleport:
            return []
        pagerank = dict(teleport)
        for _ in range(iterations):
            nxt = {node_id: alpha * teleport.get(node_id, 0.0) for node_id in nodes}
            dangling = sum(pagerank.get(node_id, 0.0) for node_id in nodes if not neighbours[node_id])
            for node_id in nodes:
                degree = len(neighbours[node_id])
                if not degree:
                    continue
                share = (1.0 - alpha) * pagerank.get(node_id, 0.0) / degree
                for neighbour in neighbours[node_id]:
                    nxt[neighbour] += share
            if dangling:
                mass = (1.0 - alpha) * dangling
                for seed, weight in teleport.items():
                    nxt[seed] += mass * weight
            total = sum(nxt.values()) or 1.0
            pagerank = {node_id: nxt[node_id] / total for node_id in nodes}
        ranked = [(node_id, pagerank[node_id]) for node_id in nodes if store.get(node_id) is not None]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        candidates: list[Candidate] = []
        for rank, (node_id, score) in enumerate(ranked[:top_k], 1):
            candidate = _graph_candidate(store, node_id, rank, score, "ppr", representation,
                                         alpha=alpha, top_k=top_k, iterations=iterations,
                                         seeds=seeds[:5])
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= k:
                break
        return candidates


@register(AXIS_GRAPH_RETRIEVAL, "community_summary")
class CommunitySummaryGraphRetriever(GraphRetriever):
    def retrieve(self, frame, node, k, ctx, params):
        raise NotImplementedError(
            "graph.retrieval.impl=community_summary is not implemented; refusing to fall back to k-hop"
        )


@register(AXIS_GRAPH_RETRIEVAL, "hybrid_graph")
class HybridGraphRetriever(GraphRetriever):
    def retrieve(self, frame, node, k, ctx, params):
        raise NotImplementedError(
            "graph.retrieval.impl=hybrid_graph is not implemented; refusing to fall back to k-hop"
        )


@register(AXIS_CHANNEL, "graph_khop")
class GraphKHopRetriever(ChannelRetriever):
    """The graph channel; delegates to the configured graph-retrieval impl."""

    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        impl = _graph_impl_name(ctx)
        try:
            implementation = get_impl(AXIS_GRAPH_RETRIEVAL, impl)
        except UnknownImplementation as exc:
            raise NotImplementedError(
                f"graph.retrieval.impl={impl!r} is not implemented; refusing to fall back to k-hop"
            ) from exc
        params = _graph_params(ctx)
        return implementation().retrieve(frame, node, k, ctx, params)


@register(AXIS_CHANNEL, "temporal")
class TemporalRetriever(ChannelRetriever):
    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        store = _store(ctx)
        as_of = frame.as_of or node.filters.get("as_of")
        if as_of is not None:
            units = store.temporal_units(as_of)
            scores = store.bm25_scores(node.query or frame.query)
            selected = [unit for unit in units if unit.memory_id in scores]
            ordered = sorted(selected, key=lambda unit: (-scores[unit.memory_id], unit.memory_id))[:k]
            return [Candidate(memory_id=unit.memory_id, channel="temporal", rank=rank,
                              raw_score=scores[unit.memory_id], score=scores[unit.memory_id],
                              stage_scores={"temporal": scores[unit.memory_id]},
                              provenance={"retriever": "temporal", "as_of": as_of.isoformat()})
                    for rank, unit in enumerate(ordered, 1)]
        # Without an explicit as-of date there is nothing to filter; rank lexically
        # and let the time ordering be a tie-breaker rather than a selection rule.
        scores = store.bm25_scores(node.query or frame.query)
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return [Candidate(memory_id=memory_id, channel="temporal", rank=rank, raw_score=score,
                          score=score, stage_scores={"temporal": score},
                          provenance={"retriever": "temporal", "as_of": None})
                for rank, (memory_id, score) in enumerate(ordered, 1)]


# ---- runner ------------------------------------------------------------

@dataclass
class RetrievalResult:
    frame: QueryFrame
    plan: Plan
    candidates: list[Candidate]
    trace: list[dict]
    k: int
    by_channel: dict[str, list[Candidate]] = field(default_factory=dict)

    def memory_ids(self) -> list[str]:
        return [candidate.memory_id for candidate in self.candidates]

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.frame.query,
            "intent": self.frame.intent,
            "as_of": self.frame.as_of.isoformat() if self.frame.as_of else None,
            "k": self.k,
            "nodes": [{"id": node.node_id, "channel": node.channel, "depends_on": node.depends_on}
                      for node in self.plan.nodes],
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "channels": {name: [candidate.memory_id for candidate in items]
                         for name, items in self.by_channel.items()},
            "trace": list(self.trace),
        }


class RetrievalRunner:
    """Analyze -> plan -> retrieve -> merge, with per-node caching."""

    def __init__(self, analyzer: str | None = None, planner: str | None = None):
        self.analyzer = analyzer
        self.planner = planner

    def _analyzer_name(self, ctx: Any, trace: Trace) -> str:
        name = self.analyzer
        if name is None:
            name = _config_get(ctx, "planner.analyzer") or _config_get(ctx, "planner.params.analyzer") or "rule"
        if name not in ("none", "rule"):
            trace.add("retrieve", "analyzer_fallback", f"{name} not implemented in S3; using rule")
            name = "rule"
        return name

    def _planner_name(self, ctx: Any, trace: Trace) -> str:
        name = self.planner or _config_impl(ctx, "planner") or "none"
        try:
            get_impl(AXIS_PLANNER, name)
            return name
        except UnknownImplementation:
            trace.add("retrieve", "planner_fallback", f"{name} not implemented in S3; using rule_router")
            return "rule_router"

    def run(self, query: str, ctx: Any, k: int | None = None) -> RetrievalResult:
        store = _store(ctx)
        trace = Trace()
        analyzer_name = self._analyzer_name(ctx, trace)
        frame = build_impl(AXIS_ANALYZER, analyzer_name).analyze(query, ctx)
        trace.add("retrieve", "analyze",
                  f"{analyzer_name}: intent={frame.intent}, complexity={frame.complexity}, "
                  f"entities={len(frame.entity_ids)}")
        planner_name = self._planner_name(ctx, trace)
        plan = build_impl(AXIS_PLANNER, planner_name).plan(frame, ctx)
        trace.add("retrieve", "plan", f"{planner_name}: {len(plan.nodes)} nodes "
                                      f"{[node.channel for node in plan.nodes]}")
        budget = _k(ctx, k)

        executed: dict[str, list[Candidate]] = {}
        pending = list(plan.nodes)
        while pending:
            progressed = False
            for node in list(pending):
                if any(dependency not in executed for dependency in node.depends_on):
                    continue
                seeds: list[str] = []
                for dependency in node.depends_on:
                    seeds.extend(candidate.memory_id for candidate in executed[dependency])
                effective = node
                if seeds:
                    effective = replace(node, filters={**node.filters, "seed_ids": seeds})
                candidates, cached = self._retrieve_node(effective, frame, ctx, budget)
                executed[node.node_id] = candidates
                pending.remove(node)
                progressed = True
                trace.add("retrieve", f"channel:{node.channel}",
                          f"{len(candidates)} candidates{' (cache hit)' if cached else ''}")
            if not progressed:
                raise ValueError("cyclic retrieval plan")

        merged: list[Candidate] = []
        by_id: dict[str, Candidate] = {}
        by_node = {node.node_id: executed[node.node_id] for node in plan.nodes}
        depth = max((len(candidates) for candidates in by_node.values()), default=0)
        for position in range(depth):
            for node in plan.nodes:
                candidates = by_node[node.node_id]
                if position >= len(candidates):
                    continue
                candidate = candidates[position]
                if candidate.memory_id in by_id:
                    existing = by_id[candidate.memory_id]
                    existing.stage_scores[candidate.channel] = candidate.score or 0.0
                    channels = existing.provenance.setdefault("channels", [existing.channel])
                    if candidate.channel not in channels:
                        channels.append(candidate.channel)
                    continue
                candidate.rank = len(merged) + 1
                merged.append(candidate)
                by_id[candidate.memory_id] = candidate
                if len(merged) >= budget:
                    break
            if len(merged) >= budget:
                break
        trace.add("retrieve", "merge", f"{len(merged)} unique candidates across "
                                        f"{len(plan.nodes)} node(s); fusion is M/S4")
        by_channel: dict[str, list[Candidate]] = {}
        for node in plan.nodes:
            by_channel.setdefault(node.channel, []).extend(executed[node.node_id])
        return RetrievalResult(frame=frame, plan=plan, candidates=merged, trace=trace.to_list(),
                               k=budget, by_channel=by_channel)

    def _retrieve_node(self, node: PlanNode, frame: QueryFrame, ctx: Any,
                       k: int) -> tuple[list[Candidate], bool]:
        store = _store(ctx)
        cache = getattr(ctx, "cache", None)
        key = None
        if cache is not None:
            client = getattr(ctx, "embedding", None)
            key = cache.key(
                "retrieve",
                {"query": node.query, "index_hash": store.index_hash, "filters": node.filters,
                 "as_of": frame.as_of.isoformat() if frame.as_of else None},
                impl=node.channel,
                params={
                    "k": k,
                    # The graph impl/params are part of the cache identity: without
                    # them every graph impl would replay the first impl's candidates.
                    "graph_repr": _config_impl(ctx, "graph.repr") if node.channel == "graph_khop" else None,
                    "graph_impl": _graph_impl_name(ctx) if node.channel == "graph_khop" else None,
                    "graph_params": _graph_params(ctx) if node.channel == "graph_khop" else None,
                },
                prompt_hash=None,
                model_fingerprint=client.fingerprint() if node.channel == "dense" and client is not None else None,
                schema_version=model.SCHEMA_VERSION,
            )
            cached = cache.get(key)
            if cached is not None:
                return [Candidate(**item) for item in cached], True
        candidates = build_impl(AXIS_CHANNEL, node.channel).retrieve(frame, node, k, ctx)
        if cache is not None and key is not None:
            cache.put(key, [asdict(candidate) for candidate in candidates])
        return candidates, False
