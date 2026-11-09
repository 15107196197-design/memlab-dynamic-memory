"""W module: extraction, write resolution and write-time audit.

S3 works from artifacts the legacy pipeline already produced (``data/facts`` plus
``data/states``): the extractors turn those records into :class:`MemoryUnit` v2
units, so the whole W -> S -> R loop runs offline and can be compared against B0
without an LLM.  ``meta_schema`` is the richer schema: it keeps the flat fields
the store needs and adds ``fact/temporal/relation/evidence`` dimensions.

Resolvers decide what happens to an incoming fact (append / keep_both / overwrite /
Mem0-style four actions).  They never mutate the store; they return a
:class:`WriteDecision` that :class:`memlab.store.MemoryStore` applies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from memwb import dataset as legacy_dataset
from memwb import memory as legacy_memory
from memwb import retrieval as legacy_retrieval

from . import model
from .contracts import MemoryUnit, Relation, WriteDecision
from .manifest import prompt_hash
from .registry import register
from .trace import Trace

AXIS_SCHEMA = "schema"
AXIS_RESOLVER = "write.resolver"
AXIS_AUDITOR = "write.auditor"

SCHEMA_VERSION = model.SCHEMA_VERSION


def fact_fields(unit: MemoryUnit) -> dict[str, Any]:
    """Flat fact fields regardless of whether the unit came from legacy_flat or meta_schema."""
    structured = unit.structured
    nested = structured.get("fact")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        for key in ("slot", "kind", "state"):
            merged.setdefault(key, structured.get(key))
        return merged
    return dict(structured)


class Parametrised:
    """Shared parameter validation; registry calls ``validate_params`` before construction."""

    params_allowed: frozenset[str] = frozenset()

    def __init__(self, **params: Any):
        unknown = set(params) - set(self.params_allowed)
        if unknown:
            raise TypeError(f"{getattr(self, 'name', '') or type(self).__name__} does not accept {sorted(unknown)}; "
                            f"allowed={sorted(self.params_allowed)}")
        self.params = dict(params)

    @classmethod
    def validate_params(cls, params: Mapping[str, Any]) -> None:
        unknown = set(params) - set(cls.params_allowed)
        if unknown:
            raise TypeError(f"{cls.__name__} does not accept {sorted(unknown)}; "
                            f"allowed={sorted(cls.params_allowed)}")


class LegacyRecords:
    """Per-conversation cache of legacy records, shared by both extractors."""

    def __init__(self, **params: Any):
        super().__init__(**params)
        self._records: dict[str, dict[str, Any]] = {}

    def _conversation(self, episode: MemoryUnit) -> str:
        source = episode.provenance.get("source") or {}
        conversation = source.get("conversation")
        if not conversation:
            raise ValueError("episode provenance has no source.conversation")
        return str(conversation)

    def records(self, conversation: str) -> dict[str, Any]:
        if conversation not in self._records:
            sample = legacy_dataset.store().get(conversation)
            turns, facts = legacy_memory.build(sample)
            by_turn: dict[str, list[Mapping[str, Any]]] = {}
            for fact in facts:
                by_turn.setdefault(fact["source_memory_id"], []).append(fact)
            self._records[conversation] = {
                "turn_text": {turn["memory_id"]: turn.get("content") or "" for turn in turns},
                "facts_by_id": {fact["memory_id"]: fact for fact in facts},
                "by_turn": by_turn,
            }
        return self._records[conversation]

    def raw_facts(self, episode: MemoryUnit) -> list[Mapping[str, Any]]:
        return list(self.records(self._conversation(episode))["by_turn"].get(episode.memory_id, []))


@register(AXIS_SCHEMA, "legacy_flat")
class LegacyFlatExtractor(LegacyRecords, Parametrised):
    """The B0 schema: entity/attribute/value/event/time_expression, nothing more."""

    params_allowed = frozenset({"extract_model"})

    def extract(self, episode: MemoryUnit, ctx: Any) -> list[MemoryUnit]:
        records = self.records(self._conversation(episode))
        return [model.from_fact(fact, facts_by_id=records["facts_by_id"],
                                turn_text=records["turn_text"])
                for fact in self.raw_facts(episode)]


@register(AXIS_SCHEMA, "meta_schema")
class MetaSchemaExtractor(LegacyRecords, Parametrised):
    """Rich schema view: fact + temporal + relation + evidence dimensions.

    S3 reuses the cached legacy facts instead of calling an extraction LLM; the
    added dimensions are derived from those facts, their v2 intervals and their
    existing version-chain links, and every field is traceable to evidence.
    """

    params_allowed = frozenset({
        "fields", "evidence", "bitemporal", "scene_plugin", "few_shot", "strict_json", "extract_model",
    })

    def extract(self, episode: MemoryUnit, ctx: Any) -> list[MemoryUnit]:
        records = self.records(self._conversation(episode))
        units = []
        for raw in self.raw_facts(episode):
            base = model.from_fact(raw, facts_by_id=records["facts_by_id"],
                                  turn_text=records["turn_text"])
            unit = self._enrich(base, raw)
            units.append(unit)
        return units

    def _enrich(self, unit: MemoryUnit, raw: Mapping[str, Any]) -> MemoryUnit:
        fields = fact_fields(unit)
        structured = dict(unit.structured)
        structured.update({
            "fact": {
                "entity": fields.get("entity"),
                "attribute": fields.get("attribute"),
                "value": fields.get("value"),
                "event": fields.get("event"),
            },
            "temporal": {
                "time_expression": fields.get("time_expression"),
                "resolved_date": fields.get("resolved_date"),
                "t_event": model.interval_to_dict(unit.t_event),
                "t_ingest": model.interval_to_dict(unit.t_ingest),
                "valid_interval": model.interval_to_dict(unit.valid_interval),
            },
            "relation": [
                {
                    "type": relation.get("type"),
                    "direction": relation.get("direction"),
                    "memory_id": relation.get("memory_id"),
                    "reason": relation.get("reason", ""),
                }
                for relation in raw.get("relations") or []
            ],
            "evidence": [model.span_to_dict(span) for span in unit.evidence],
            "schema": {
                "fields": int(self.params.get("fields", 6)),
                "bitemporal": bool(self.params.get("bitemporal", False)),
                "scene_plugin": self.params.get("scene_plugin"),
                "few_shot": int(self.params.get("few_shot", 0)),
                "strict_json": bool(self.params.get("strict_json", True)),
            },
        })
        unit.structured = structured
        unit.provenance = {**unit.provenance, "extractor": "meta_schema", "base_extractor": "legacy_flat"}
        return unit


# ---- write resolvers ---------------------------------------------------

def _fact_units(units: Sequence[MemoryUnit]) -> list[MemoryUnit]:
    return [unit for unit in units if unit.kind == "fact"]


def _key(unit: MemoryUnit) -> tuple[Any, Any]:
    fields = fact_fields(unit)
    return fields.get("entity"), fields.get("attribute")


def _value(unit: MemoryUnit) -> Any:
    return fact_fields(unit).get("value")


def _similarity(left: Any, right: Any) -> float:
    a = set(legacy_retrieval.tokens(str(left)))
    b = set(legacy_retrieval.tokens(str(right)))
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if a | b else 0.0


def _latest(units: Sequence[MemoryUnit]) -> MemoryUnit:
    return max(units, key=lambda unit: (unit.t_ingest.start.isoformat() if unit.t_ingest and unit.t_ingest.start else "",
                                       unit.memory_id))


@register(AXIS_RESOLVER, "append")
class AppendResolver(Parametrised):
    def resolve(self, incoming: Sequence[MemoryUnit], store: Any, ctx: Any) -> WriteDecision:
        units = list(incoming)
        return WriteDecision(add=units, update=[], delete=[], noop=[], relations=[], conflicts=[],
                             reasons={unit.memory_id: "append" for unit in units})


@register(AXIS_RESOLVER, "keep_both")
class KeepBothResolver(Parametrised):
    """Keep every version, but suppress exact repeats already in the store."""

    def resolve(self, incoming: Sequence[MemoryUnit], store: Any, ctx: Any) -> WriteDecision:
        existing = {unit.memory_id for unit in store.units}
        seen: set[tuple[Any, Any, Any]] = {(*_key(unit), _value(unit)) for unit in store.units}
        add, noop, reasons = [], [], {}
        for unit in incoming:
            key = (*_key(unit), _value(unit))
            if unit.memory_id in existing or key in seen:
                noop.append(unit)
                reasons[unit.memory_id] = "duplicate"
                continue
            seen.add(key)
            add.append(unit)
            reasons[unit.memory_id] = "keep_both"
        return WriteDecision(add=add, update=[], delete=[], noop=noop, relations=[], conflicts=[], reasons=reasons)


@register(AXIS_RESOLVER, "overwrite")
class OverwriteResolver(Parametrised):
    """New value replaces the latest existing value for the same entity+attribute."""

    params_allowed = frozenset({"match_key"})

    def resolve(self, incoming: Sequence[MemoryUnit], store: Any, ctx: Any) -> WriteDecision:
        current: dict[tuple[Any, Any], MemoryUnit] = {}
        for unit in _fact_units(store.units):
            key = _key(unit)
            current[key] = unit if key not in current else _latest([current[key], unit])
        add, update, noop, relations, reasons = [], [], [], [], {}
        for unit in incoming:
            key = _key(unit)
            previous = current.get(key)
            if previous is None:
                add.append(unit)
                current[key] = unit
                reasons[unit.memory_id] = "new key"
                continue
            if _value(previous) == _value(unit):
                noop.append(unit)
                reasons[unit.memory_id] = "same value"
                continue
            update.append((previous.memory_id, unit))
            relations.append(Relation(
                relation_id=f"rel:update:{previous.memory_id}:{unit.memory_id}",
                head_id=previous.memory_id, tail_id=unit.memory_id, type="UPDATE",
                provenance={"origin": "write.overwrite", "support": "rule", "reason": "same entity+attribute"},
            ))
            current[key] = unit
            reasons[unit.memory_id] = f"overwrite {previous.memory_id}"
        return WriteDecision(add=add, update=update, delete=[], noop=noop, relations=relations,
                             conflicts=[], reasons=reasons)


@register(AXIS_RESOLVER, "mem0_4action")
class Mem0FourActionResolver(Parametrised):
    """Rule-based Mem0: ADD / UPDATE / DELETE / NOOP.

    ``threshold`` compares token sets of same-attribute values; ``top_k`` limits
    how many existing versions are inspected.  DELETE is only emitted for units
    that are already present with identical content and a superseded state, so S3
    never silently drops a version it has no evidence for.
    """

    params_allowed = frozenset({"top_k", "threshold", "similarity"})

    def resolve(self, incoming: Sequence[MemoryUnit], store: Any, ctx: Any) -> WriteDecision:
        top_k = int(self.params.get("top_k", 8) or 8)
        threshold = float(self.params.get("threshold", 0.82) or 0.82)
        existing = _fact_units(store.units)
        add, update, delete, noop, relations, conflicts = [], [], [], [], [], []
        reasons: dict[str, str] = {}
        for unit in incoming:
            key = _key(unit)
            matches = [candidate for candidate in existing if _key(candidate) == key][-top_k:]
            if any(candidate.memory_id == unit.memory_id for candidate in matches):
                noop.append(unit)
                reasons[unit.memory_id] = "already stored"
                continue
            same_value = [candidate for candidate in matches if _value(candidate) == _value(unit)]
            if same_value:
                noop.append(unit)
                reasons[unit.memory_id] = f"identical to {same_value[-1].memory_id}"
                continue
            near = [candidate for candidate in matches if _similarity(_value(candidate), _value(unit)) >= threshold]
            if near:
                noop.append(unit)
                reasons[unit.memory_id] = f"near-duplicate of {near[-1].memory_id}"
                continue
            if matches:
                previous = _latest(matches)
                existing = [candidate for candidate in existing if candidate.memory_id != previous.memory_id] + [unit]
                update.append((previous.memory_id, unit))
                relations.append(Relation(
                    relation_id=f"rel:update:{previous.memory_id}:{unit.memory_id}",
                    head_id=previous.memory_id, tail_id=unit.memory_id, type="UPDATE",
                    provenance={"origin": "write.mem0_4action", "support": "rule", "reason": "same entity+attribute"},
                ))
                if fact_fields(unit).get("state") == "CONFLICT":
                    conflicts.append((previous.memory_id, unit.memory_id))
                reasons[unit.memory_id] = f"update {previous.memory_id}"
            else:
                add.append(unit)
                existing.append(unit)
                reasons[unit.memory_id] = "add"
        return WriteDecision(add=add, update=update, delete=delete, noop=noop, relations=relations,
                             conflicts=conflicts, reasons=reasons)


# ---- write auditors ----------------------------------------------------

@register(AXIS_AUDITOR, "none")
class NoAudit(Parametrised):
    def audit(self, decision: WriteDecision, ctx: Any) -> WriteDecision:
        return decision


@register(AXIS_AUDITOR, "llm_audit")
class LLMAudit(Parametrised):
    """Second opinion on resolver-proposed UPDATE/SUPERSEDE edges.

    Only edges marked ``support=rule`` are reviewed; graph-backed edges are kept.
    With no LLM client the decision is returned unchanged (S3 can run offline).
    """

    params_allowed = frozenset({"max_pairs"})

    def audit(self, decision: WriteDecision, ctx: Any) -> WriteDecision:
        llm = getattr(ctx, "llm", None)
        reviewed = [relation for relation in decision.relations if relation.provenance.get("support") != "memory_graph"]
        if llm is None or not reviewed or not hasattr(llm, "generate"):
            return decision
        max_pairs = int(self.params.get("max_pairs", 48) or 48)
        reviewed = reviewed[:max_pairs]
        pairs = [{"index": index, "type": relation.type,
                  "earlier": relation.head_id, "later": relation.tail_id}
                 for index, relation in enumerate(reviewed)]
        prompt = (
            "Audit these proposed memory relations. Accept UPDATE/SUPERSEDE only when both ids "
            "concern the same entity and attribute. Return JSON {\"accepted\":[indices]}.\n"
            f"Proposals: {pairs}"
        )
        try:
            result = llm.generate(prompt, json_mode=True)
        except Exception:  # an audit failure must not destroy an otherwise valid write
            return decision
        accepted = {item for item in result.get("accepted", []) if isinstance(item, int)} if isinstance(result, dict) else set()
        keep = []
        for relation in decision.relations:
            if relation in reviewed:
                if reviewed.index(relation) in accepted:
                    keep.append(relation)
            else:
                keep.append(relation)
        return WriteDecision(add=decision.add, update=decision.update, delete=decision.delete,
                             noop=decision.noop, relations=keep, conflicts=decision.conflicts,
                             reasons=decision.reasons)


# ---- pipeline ----------------------------------------------------------

@dataclass
class WriteResult:
    decision: WriteDecision
    added: list[MemoryUnit]
    trace: list[dict]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "add": len(self.decision.add),
            "update": len(self.decision.update),
            "delete": len(self.decision.delete),
            "noop": len(self.decision.noop),
            "relations": len(self.decision.relations),
            "conflicts": len(self.decision.conflicts),
        }


class WritePipeline:
    """Extract -> resolve -> audit -> apply, with optional artifact caching."""

    def __init__(self, extractor: str = "legacy_flat", resolver: str = "append",
                 auditor: str = "none", *, extractor_params: Mapping[str, Any] | None = None,
                 resolver_params: Mapping[str, Any] | None = None,
                 auditor_params: Mapping[str, Any] | None = None):
        from .registry import build  # local import keeps module import order simple

        self.extractor = build(AXIS_SCHEMA, extractor, extractor_params)
        self.resolver = build(AXIS_RESOLVER, resolver, resolver_params)
        self.auditor = build(AXIS_AUDITOR, auditor, auditor_params)
        self.extractor_name, self.resolver_name, self.auditor_name = extractor, resolver, auditor

    def _extract(self, episode: MemoryUnit, ctx: Any, counters: dict[str, int]) -> list[MemoryUnit]:
        cache = getattr(ctx, "cache", None)
        key = None
        if cache is not None:
            prompts = getattr(ctx, "prompts", {}) or {}
            llm = getattr(ctx, "llm", None)
            key = cache.key(
                "extract", model.unit_to_dict(episode), impl=self.extractor_name,
                params=self.extractor.params,
                prompt_hash=prompt_hash(prompts["extract"]) if prompts.get("extract") else None,
                model_fingerprint=llm.fingerprint() if llm is not None and hasattr(llm, "fingerprint") else None,
                schema_version=SCHEMA_VERSION,
            )
            cached = cache.get(key)
            if cached is not None:
                counters["hits"] += 1
                return [model.unit_from_dict(item) for item in cached]
            counters["misses"] += 1
        units = self.extractor.extract(episode, ctx)
        if cache is not None and key is not None:
            cache.put(key, [model.unit_to_dict(unit) for unit in units])
        return units

    def write(self, turns: Sequence[MemoryUnit], store: Any, ctx: Any) -> WriteResult:
        trace = Trace()
        counters = {"hits": 0, "misses": 0}
        incoming: list[MemoryUnit] = []
        for turn in turns:
            incoming.extend(self._extract(turn, ctx, counters))
        trace.add("write", "extract",
                  f"{len(turns)} turns -> {len(incoming)} facts "
                  f"(cache hit {counters['hits']}, miss {counters['misses']})")
        decision = self.resolver.resolve(incoming, store, ctx)
        trace.add("write", "resolve", f"{self.resolver_name}: {len(decision.add)} add, "
                                      f"{len(decision.update)} update, {len(decision.noop)} noop")
        decision = self.auditor.audit(decision, ctx)
        trace.add("write", "audit", f"{self.auditor_name}: {len(decision.relations)} relations kept")
        store.apply(decision)
        added = list(decision.add) + [unit for _, unit in decision.update]
        trace.add("write", "apply", f"store now has {len(store.units)} units")
        return WriteResult(decision=decision, added=added, trace=trace.to_list())
