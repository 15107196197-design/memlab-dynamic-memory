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
from .write import Parametrised

AXIS_ANALYZER = "planner.analyzer"
AXIS_PLANNER = "planner"
AXIS_CHANNEL = "retrieval.channel"


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


def _channels_for(frame: QueryFrame) -> list[str]:
    if frame.intent == "temporal" or frame.as_of is not None:
        return ["temporal", "bm25"]
    if frame.intent == "multi_hop" or frame.complexity >= 0.5:
        return ["bm25", "graph_khop"]
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
        channels = _channels_for(frame)
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
            nodes = [_node("n1", frame, "bm25", k),
                     _node("n2", frame, "graph_khop", k, depends_on=["n1"])]
            groups = [["n1"], ["n2"]]
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


@register(AXIS_CHANNEL, "graph_khop")
class GraphKHopRetriever(ChannelRetriever):
    def retrieve(self, frame: QueryFrame, node: PlanNode, k: int, ctx: Any) -> list[Candidate]:
        store = _store(ctx)
        config = _config(ctx)
        params = config.params("graph.retrieval") if config is not None and hasattr(config, "params") else {}
        k_hop = int(node.filters.get("k_hop", params.get("k_hop", 2)) or 2)
        seeds = list(node.filters.get("seed_ids") or [])
        if not seeds:
            scores = store.bm25_scores(node.query or frame.query)
            seeds = [memory_id for memory_id, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:3]]
        representation = _config_impl(ctx, "graph.repr") or "state_slot"
        graph = store.ensure_graph(representation)
        candidates = []
        for node_id, distance in graph.expand(seeds, k_hop):
            unit = store.get(node_id)
            if unit is None:
                continue
            score = 1.0 / (1 + distance)
            candidates.append(Candidate(
                memory_id=unit.memory_id, channel="graph_khop", rank=len(candidates) + 1,
                raw_score=score, score=score, stage_scores={"graph_khop": score},
                provenance={"retriever": "graph_khop", "representation": representation,
                            "distance": distance, "seeds": seeds[:5]},
            ))
            if len(candidates) >= k:
                break
        return candidates


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
                params={"k": k, "graph_repr": _config_impl(ctx, "graph.repr") if node.channel == "graph_khop" else None},
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
