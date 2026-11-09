"""S module: memory store, graph representations and retrieval indexes.

The store holds :class:`MemoryUnit` records and exposes four index families:

* lexical (BM25 over unit text + structured fields);
* dense (vectors supplied by a client; cached by text in :class:`ArtifactCache`);
* graph (``state_slot`` / ``entity_triple`` / ``event_sparse`` / ``three_layer``
  representations);
* temporal (``valid_interval`` filtering for as-of queries).

It also computes the retrieval ceiling: whether the gold evidence turns are even
represented in the index, before any retriever quality is considered.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from memwb import retrieval as legacy_retrieval

from . import config as lab_config
from . import model
from .contracts import MemoryUnit, Relation, WriteDecision
from .registry import build as build_impl
from .registry import register
from .write import fact_fields

MAX_GRAPH_NODES = 2_000_000


def _flatten(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        out.append(str(value))
    elif isinstance(value, Mapping):
        for item in value.values():
            _flatten(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _flatten(item, out)


def search_text(unit: MemoryUnit) -> str:
    """Text indexed for one unit: utterance/fact plus its structured fields."""
    parts = [unit.text]
    if unit.kind == "turn":
        parts.append(str(unit.structured.get("speaker") or ""))
    _flatten(unit.structured, parts)
    return " ".join(part for part in parts if part)


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


class GraphIndex:
    """Undirected adjacency over unit nodes and auxiliary layer nodes."""

    def __init__(self, representation: str):
        self.representation = representation
        self.adj: dict[str, set[str]] = defaultdict(set)
        self.nodes: set[str] = set()

    def add_node(self, node: str) -> None:
        self.nodes.add(node)
        self.adj.setdefault(node, set())

    def link(self, left: str, right: str) -> None:
        if not left or not right or left == right:
            return
        self.add_node(left)
        self.add_node(right)
        self.adj[left].add(right)
        self.adj[right].add(left)

    def neighbors(self, node: str) -> list[str]:
        return sorted(self.adj.get(node, ()))

    def expand(self, seeds: Iterable[str], k_hop: int = 1) -> list[tuple[str, int]]:
        """Return ``(node, distance)`` reachable within ``k_hop``, seeds first."""
        distances: dict[str, int] = {}
        frontier: list[str] = []
        for seed in seeds:
            if seed in self.nodes and seed not in distances:
                distances[seed] = 0
                frontier.append(seed)
        for depth in range(1, max(0, int(k_hop)) + 1):
            next_frontier: list[str] = []
            for node in frontier:
                for neighbor in sorted(self.adj.get(node, ())):
                    if neighbor not in distances:
                        distances[neighbor] = depth
                        next_frontier.append(neighbor)
                        if len(distances) > MAX_GRAPH_NODES:
                            raise ValueError("graph expansion exceeded the node cap")
            frontier = next_frontier
            if not frontier:
                break
        return sorted(distances.items(), key=lambda item: (item[1], item[0]))

    def stats(self) -> dict[str, Any]:
        edges = sum(len(neighbors) for neighbors in self.adj.values()) // 2
        return {"representation": self.representation, "nodes": len(self.nodes), "edges": edges}


def _turn_lookup(units: Sequence[MemoryUnit]) -> dict[str, str]:
    return {
        str(unit.structured.get("turn")): unit.memory_id
        for unit in units
        if unit.kind == "turn" and unit.structured.get("turn")
    }


def _link_evidence(graph: GraphIndex, unit: MemoryUnit, turns: Mapping[str, str]) -> None:
    for span in unit.evidence:
        turn_memory_id = turns.get(span.turn_id)
        if turn_memory_id:
            graph.link(unit.memory_id, turn_memory_id)


def _link_relations(graph: GraphIndex, relations: Sequence[Relation], unit_ids: set[str]) -> None:
    for relation in relations:
        if relation.head_id in unit_ids and relation.tail_id in unit_ids:
            graph.link(relation.head_id, relation.tail_id)


@register("graph.repr", "state_slot")
class StateSlotGraph:
    """Fact versions grouped by (entity, slot); facts link to their evidence turn."""

    def build(self, units: Sequence[MemoryUnit], relations: Sequence[Relation]) -> GraphIndex:
        graph = GraphIndex("state_slot")
        units = list(units)
        turns = _turn_lookup(units)
        unit_ids = {unit.memory_id for unit in units}
        slots: dict[tuple[str, str], list[MemoryUnit]] = defaultdict(list)
        for unit in units:
            graph.add_node(unit.memory_id)
            if unit.kind == "fact":
                fields = fact_fields(unit)
                entity = str(fields.get("entity") or "").casefold()
                slot = str(fields.get("slot") or fields.get("attribute") or "")
                slots[(entity, slot)].append(unit)
            _link_evidence(graph, unit, turns)
        for group in slots.values():
            group.sort(key=lambda unit: ((unit.t_ingest.start.isoformat() if unit.t_ingest and unit.t_ingest.start else ""),
                                         unit.memory_id))
            for earlier, later in zip(group, group[1:]):
                graph.link(earlier.memory_id, later.memory_id)
        _link_relations(graph, relations, unit_ids)
        return graph


@register("graph.repr", "entity_triple")
class EntityTripleGraph:
    """Entity nodes connected to every memory that mentions them."""

    def build(self, units: Sequence[MemoryUnit], relations: Sequence[Relation]) -> GraphIndex:
        graph = GraphIndex("entity_triple")
        units = list(units)
        turns = _turn_lookup(units)
        unit_ids = {unit.memory_id for unit in units}
        for unit in units:
            graph.add_node(unit.memory_id)
            entity_ids = list(unit.entity_ids)
            if not entity_ids and unit.kind == "fact":
                entity = fact_fields(unit).get("entity")
                if entity:
                    entity_ids = [" ".join(str(entity).split()).casefold()]
            for entity_id in entity_ids:
                graph.link(unit.memory_id, f"entity:{entity_id}")
            _link_evidence(graph, unit, turns)
        _link_relations(graph, relations, unit_ids)
        return graph


@register("graph.repr", "three_layer")
class ThreeLayerGraph:
    """Entity, event and topic layers, all attached to the memory units."""

    def build(self, units: Sequence[MemoryUnit], relations: Sequence[Relation]) -> GraphIndex:
        graph = GraphIndex("three_layer")
        units = list(units)
        turns = _turn_lookup(units)
        unit_ids = {unit.memory_id for unit in units}
        for unit in units:
            graph.add_node(unit.memory_id)
            for entity_id in unit.entity_ids:
                graph.link(unit.memory_id, f"entity:{entity_id}")
            if unit.kind == "fact":
                fields = fact_fields(unit)
                slot = fields.get("slot")
                if slot:
                    graph.link(unit.memory_id, f"topic:{slot}")
                event = fields.get("event")
                if event:
                    graph.link(unit.memory_id, f"event:{str(event)[:80]}")
            _link_evidence(graph, unit, turns)
        _link_relations(graph, relations, unit_ids)
        return graph


@register("graph.repr", "event_sparse")
class EventSparseGraph:
    """Sparse event nodes: facts that share an event meet through one node.

    This is the offline, deterministic half of the ``event_sparse`` variant in
    ``docs/optimization/03-variants.md`` §3.3.1: the event string already present
    in the extracted records is the node key, and an event node is created only
    when at least two facts share it (hence *sparse*).  There is no LLM event
    extraction, no ``event_window``/``link_threshold`` parameter and no community
    summary; those remain unimplemented and must not be treated as consumed.
    Evidence-turn links are the same as in the other representations, so the
    graph is still traceable when a fact has no event.
    """

    def build(self, units: Sequence[MemoryUnit], relations: Sequence[Relation]) -> GraphIndex:
        graph = GraphIndex("event_sparse")
        units = list(units)
        turns = _turn_lookup(units)
        unit_ids = {unit.memory_id for unit in units}
        events: dict[str, list[MemoryUnit]] = defaultdict(list)
        for unit in units:
            graph.add_node(unit.memory_id)
            if unit.kind == "fact":
                fields = fact_fields(unit)
                event = fields.get("event")
                if event not in (None, ""):
                    key = " ".join(str(event).split()).casefold()
                    if key:
                        events[key].append(unit)
            _link_evidence(graph, unit, turns)
        for key, group in events.items():
            if len(group) < 2:
                # A single-fact event node only adds a dangling hub; leave the
                # fact linked to its evidence turns instead.
                continue
            event_node = f"event:{key[:80]}"
            graph.add_node(event_node)
            for unit in group:
                graph.link(event_node, unit.memory_id)
        _link_relations(graph, relations, unit_ids)
        return graph


class MemoryStore:
    """Ordered unit store with lazy indexes."""

    def __init__(self, units: Iterable[MemoryUnit] = ()):
        self._units: dict[str, MemoryUnit] = {}
        self.relations: list[Relation] = []
        self.conflicts: list[tuple[str, str]] = []
        self._vectors: dict[str, list[float]] = {}
        self._lexical: dict[str, Any] | None = None
        self._hash: str | None = None
        self._graph: GraphIndex | None = None
        self._graph_name: str | None = None
        self.extend(units)

    # ---- units --------------------------------------------------------
    @property
    def units(self) -> list[MemoryUnit]:
        return list(self._units.values())

    def __len__(self) -> int:
        return len(self._units)

    def __contains__(self, memory_id: str) -> bool:
        return memory_id in self._units

    def add(self, unit: MemoryUnit) -> MemoryUnit:
        if not isinstance(unit, MemoryUnit):
            raise TypeError("MemoryStore only stores MemoryUnit records")
        if unit.memory_id in self._units:
            self._vectors.pop(unit.memory_id, None)
        self._units[unit.memory_id] = unit
        self._invalidate()
        return unit

    def extend(self, units: Iterable[MemoryUnit]) -> None:
        for unit in units:
            self.add(unit)

    def remove(self, memory_id: str) -> None:
        if memory_id in self._units:
            del self._units[memory_id]
            self._vectors.pop(memory_id, None)
            self._invalidate()

    def get(self, memory_id: str) -> MemoryUnit | None:
        return self._units.get(memory_id)

    def by_kind(self, kind: str) -> list[MemoryUnit]:
        return [unit for unit in self.units if unit.kind == kind]

    @property
    def turns(self) -> list[MemoryUnit]:
        return self.by_kind("turn")

    @property
    def facts(self) -> list[MemoryUnit]:
        return self.by_kind("fact")

    def add_relation(self, relation: Relation) -> None:
        if not any(existing.relation_id == relation.relation_id for existing in self.relations):
            self.relations.append(relation)
            self._invalidate()

    def apply(self, decision: WriteDecision) -> None:
        """Apply a write decision; adds are applied before updates of those adds."""
        for unit in decision.add:
            self.add(unit)
        for old_id, unit in decision.update:
            self.remove(old_id)
            self.add(unit)
        for memory_id in decision.delete:
            self.remove(memory_id)
        for relation in decision.relations:
            self.add_relation(relation)
        self.conflicts.extend(decision.conflicts)

    def _invalidate(self) -> None:
        self._lexical = None
        self._hash = None
        self._graph = None
        self._graph_name = None

    # ---- lexical index ------------------------------------------------
    def _build_lexical(self) -> dict[str, Any]:
        docs: dict[str, Counter] = {}
        lengths: dict[str, int] = {}
        document_frequency: Counter = Counter()
        for unit in self.units:
            tokens = legacy_retrieval.tokens(search_text(unit))
            counts = Counter(tokens)
            docs[unit.memory_id] = counts
            lengths[unit.memory_id] = len(tokens)
            for token in set(tokens):
                document_frequency[token] += 1
        total = len(docs)
        average = sum(lengths.values()) / total if total else 0.0
        self._lexical = {
            "docs": docs,
            "lengths": lengths,
            "df": document_frequency,
            "average": average,
            "total": total,
        }
        return self._lexical

    def bm25_scores(self, query: str, k1: float = 1.2, b: float = 0.75) -> dict[str, float]:
        index = self._lexical or self._build_lexical()
        terms = legacy_retrieval.tokens(query)
        total = index["total"]
        if not total or not terms:
            return {}
        scores: dict[str, float] = {}
        for memory_id, counts in index["docs"].items():
            length = index["lengths"][memory_id]
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (total - index["df"][term] + 0.5) / (index["df"][term] + 0.5))
                score += idf * frequency * (k1 + 1) / (
                    frequency + k1 * (1 - b + b * length / max(index["average"], 1.0))
                )
            if score:
                scores[memory_id] = score
        return scores

    def lexical_stats(self) -> dict[str, Any]:
        index = self._lexical or self._build_lexical()
        return {"units": index["total"], "terms": len(index["df"]), "avg_tokens": round(index["average"], 2)}

    # ---- dense index --------------------------------------------------
    def ensure_embeddings(self, client: Any, cache: Any | None = None) -> int:
        missing = [unit for unit in self.units if unit.memory_id not in self._vectors]
        if not missing:
            return 0
        pending: list[tuple[MemoryUnit, str, Any]] = []
        for unit in missing:
            text = search_text(unit)
            key = None
            if cache is not None:
                key = cache.key("embed", {"text": text}, impl="dense", params={}, prompt_hash=None,
                                model_fingerprint=client.fingerprint(), schema_version=model.SCHEMA_VERSION)
                cached = cache.get(key)
                if cached is not None:
                    self._vectors[unit.memory_id] = list(cached)
                    continue
            pending.append((unit, text, key))
        if pending:
            vectors = client.embed([text for _, text, _ in pending])
            if len(vectors) != len(pending):
                raise ValueError("embedding client returned the wrong number of vectors")
            for (unit, _text, key), vector in zip(pending, vectors):
                self._vectors[unit.memory_id] = list(vector)
                if cache is not None and key is not None:
                    cache.put(key, list(vector))
        return len(missing)

    def dense_scores(self, query: str, client: Any, cache: Any | None = None) -> dict[str, float]:
        if not self.units:
            return {}
        self.ensure_embeddings(client, cache)
        key = None
        query_vector = None
        if cache is not None:
            key = cache.key("embed_query", {"text": query}, impl="dense", params={}, prompt_hash=None,
                            model_fingerprint=client.fingerprint(), schema_version=model.SCHEMA_VERSION)
            cached = cache.get(key)
            if cached is not None:
                query_vector = list(cached)
        if query_vector is None:
            query_vector = client.embed([query])[0]
            if cache is not None and key is not None:
                cache.put(key, list(query_vector))
        return {memory_id: cosine(query_vector, vector) for memory_id, vector in self._vectors.items()}

    # ---- temporal index ----------------------------------------------
    def temporal_units(self, as_of: Any = None) -> list[MemoryUnit]:
        if as_of is None:
            return self.units
        if isinstance(as_of, str):
            parsed = model.parse_time(as_of)
            if parsed is None:
                raise ValueError(f"unparseable as_of date: {as_of!r}")
            as_of = parsed
        return [unit for unit in self.units if valid_at(unit, as_of)]

    def evidence_turns(self) -> set[str]:
        evidence: set[str] = set()
        for unit in self.units:
            if unit.kind == "turn" and unit.structured.get("turn"):
                evidence.add(str(unit.structured["turn"]))
            for span in unit.evidence:
                evidence.add(span.turn_id)
        return evidence

    def ceiling(self, gold_turn_ids: Iterable[str]) -> dict[str, Any]:
        """Retrieval ceiling: fraction of gold evidence turns represented in the index."""
        gold = {str(turn) for turn in gold_turn_ids}
        indexed = gold & self.evidence_turns()
        return {
            "gold": len(gold),
            "indexed": len(indexed),
            "recall": round(len(indexed) / len(gold), 4) if gold else None,
            "missing": sorted(gold - indexed),
        }

    # ---- graph index --------------------------------------------------
    def ensure_graph(self, representation: str | None = None) -> GraphIndex:
        name = representation or self._graph_name or "state_slot"
        if self._graph is None or self._graph_name != name:
            builder = build_impl("graph.repr", name)
            self._graph = builder.build(self.units, self.relations)
            self._graph_name = name
        return self._graph

    @property
    def graph(self) -> GraphIndex | None:
        return self._graph

    @property
    def index_hash(self) -> str:
        if self._hash is None:
            self._hash = lab_config.digest({
                "units": [model.unit_to_dict(unit) for unit in self.units],
                "relations": [model.relation_to_dict(relation) for relation in self.relations],
            })
        return self._hash


def valid_at(unit: MemoryUnit, moment: Any) -> bool:
    """Half-open validity test; unknown validity is treated as not valid.

    A HISTORICAL fact with no recorded invalidating relation has ``end=None`` in
    its interval; reading that as "open-ended" would keep stale facts alive.  The
    three-valued :func:`memlab.model.is_valid_at` distinguishes True/False/unknown,
    and this conservative wrapper maps unknown to False for retrieval filtering.
    """
    if isinstance(moment, str):
        parsed = model.parse_time(moment)
        if parsed is None:
            return False
        moment = parsed
    decided = model.is_valid_at(unit, moment)
    # Unknown validity is not evidence of validity: exclude it from as-of results.
    return bool(decided) if decided is not None else False
