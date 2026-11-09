"""Legacy memory records -> MemoryUnit v2 (docs/optimization/02-architecture 2.5).

The legacy store keeps two record shapes produced by ``memwb.memory.build``:

* turns - one utterance, the retrieval unit and raw evidence;
* facts - machine-extracted ``(entity, attribute, value)`` records, already
  linked to offline state slots and version chains by ``memwb.states``.

This module is a read-only adapter: it never mutates ``data/facts`` or
``data/states`` and never invents a timestamp.  A missing event time becomes an
``Interval`` with ``precision="unknown"``; ``t_ingest`` is the session recording
time, which is why facts usually have a known ingest time and an unknown event
time.  A turn is different: it is observed exactly when it is spoken, so its
``t_event`` and ``t_ingest`` are the same session interval (precision
``"session"``).

Validity is derived only from evidence that is already in the store: when a
later UPDATE/SUPERSEDE relation points at a fact, the earlier fact's
``valid_interval`` closes at the later fact's event time, falling back to its
ingest time.  The source of that endpoint is recorded in ``provenance``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from memwb import memory as legacy_memory

from .contracts import (
    MEMORY_KINDS,
    Interval,
    MemoryUnit,
    Relation,
    Span,
)

SCHEMA_VERSION = "2.0"
LEGACY_EXTRACTOR = "legacy_flat"
INVALIDATING_RELATIONS = frozenset({"UPDATE", "SUPERSEDE"})


def entity_id(name: Any) -> str:
    """Stable, case-insensitive entity key (same rule as ``memwb.states``)."""
    return " ".join(str(name or "").split()).casefold()


def parse_time(value: Any) -> datetime | None:
    """Parse the ISO-like strings used by the legacy store; never guesses."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _session_interval(value: Any) -> Interval:
    start = parse_time(value)
    return Interval(start=start, precision="session") if start else Interval(precision="unknown")


def _event_interval(resolved_date: Any) -> Interval:
    """Facts carry only a date for event time; an absent date stays ``unknown``."""
    start = parse_time(resolved_date)
    return Interval(start=start, precision="day") if start else Interval(precision="unknown")


def _superseder(fact: Mapping[str, Any], facts_by_id: Mapping[str, Mapping[str, Any]]) -> tuple[Mapping[str, Any] | None, str | None]:
    """The later fact that closes this fact's validity, if the chain has one."""
    for relation in fact.get("relations") or []:
        if relation.get("direction") != "to" or relation.get("type") not in INVALIDATING_RELATIONS:
            continue
        target = facts_by_id.get(relation.get("memory_id"))
        if target is not None and target.get("memory_id") != fact.get("memory_id"):
            return target, relation.get("type")
    return None, None


def _valid_interval(fact: Mapping[str, Any], t_event: Interval,
                    facts_by_id: Mapping[str, Mapping[str, Any]]) -> tuple[Interval, dict[str, Any]]:
    """Derive validity from the event time plus the recorded invalidation, if any."""
    target, relation_type = _superseder(fact, facts_by_id)
    start = t_event.start
    end = None
    endpoint = "unknown"
    basis: dict[str, Any] = {"legacy_state": fact.get("state")}
    if target is not None:
        basis.update(invalidated_by=target.get("memory_id"), relation=relation_type)
        target_event = _event_interval(target.get("resolved_date"))
        target_ingest = _session_interval(target.get("session_time"))
        if target_event.start is not None:
            end, endpoint = target_event.start, "t_event"
        elif target_ingest.start is not None:
            end, endpoint = target_ingest.start, "t_ingest"
    elif fact.get("state") != "HISTORICAL":
        endpoint = "not_invalidated"
    basis.update(endpoint=endpoint, end_known=end is not None)
    if start is not None:
        precision = "day"
    elif endpoint == "t_event":
        precision = "day"
    elif endpoint == "t_ingest":
        precision = "session"
    else:
        precision = "unknown"
    return Interval(start=start, end=end, precision=precision), basis


def _span(turn_id: str, quote: str, source_text: str | None) -> Span:
    if not source_text:
        return Span(turn_id=turn_id, quote=quote)
    start = source_text.find(quote) if isinstance(quote, str) else -1
    if start < 0 and isinstance(quote, str):
        lowered = source_text.casefold().find(quote.casefold())
        start = lowered if lowered >= 0 else -1
    if start < 0:
        return Span(turn_id=turn_id, quote=quote)
    return Span(turn_id=turn_id, quote=quote, start=start, end=start + len(quote))


def _provenance(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "origin": "memwb.memory.build",
        "extractor": LEGACY_EXTRACTOR,
        "extraction": record.get("extraction"),
        "timestamp": record.get("timestamp"),
        "session_time": record.get("session_time"),
        "source": dict(record.get("source") or {}),
        "resolved_time_expressions": list(record.get("resolved_time_expressions") or []),
        "dataset_observation_count": len(record.get("dataset_observations") or []),
        "legacy_state": record.get("state"),
        "legacy_slot_key": record.get("slot_key"),
    }


def from_turn(turn: Mapping[str, Any]) -> MemoryUnit:
    """Convert one legacy turn record."""
    source = turn.get("source") or {}
    turn_id = source.get("turn") or ""
    session = _session_interval(turn.get("session_time"))
    structured = {
        "speaker": turn.get("entity"),
        "session": source.get("session"),
        "turn": turn_id,
        "state": turn.get("state"),
        "fact_ids": list(turn.get("fact_ids") or []),
        "fact_extraction": turn.get("fact_extraction"),
    }
    return MemoryUnit(
        memory_id=turn["memory_id"],
        kind="turn",
        text=turn.get("content") or "",
        structured=structured,
        entity_ids=[entity_id(turn.get("entity"))] if turn.get("entity") else [],
        t_event=session,
        t_ingest=session,
        valid_interval=None,
        evidence=[_span(turn_id, turn.get("content") or "", turn.get("content"))] if turn_id else [],
        provenance=_provenance(turn),
        schema_version=SCHEMA_VERSION,
    )


def from_fact(fact: Mapping[str, Any], *, facts_by_id: Mapping[str, Mapping[str, Any]] | None = None,
              turn_text: Mapping[str, str] | None = None) -> MemoryUnit:
    """Convert one legacy fact record, deriving times and validity from evidence."""
    by_id = facts_by_id or {}
    source = fact.get("source") or {}
    turn_id = source.get("turn") or ""
    t_event = _event_interval(fact.get("resolved_date"))
    t_ingest = _session_interval(fact.get("session_time"))
    valid_interval, validity = _valid_interval(fact, t_event, by_id)
    structured = {
        "entity": fact.get("entity"),
        "attribute": fact.get("attribute"),
        "value": fact.get("value"),
        "event": fact.get("event"),
        "time_expression": fact.get("time_expression"),
        "resolved_date": fact.get("resolved_date"),
        "slot": fact.get("slot"),
        "kind": fact.get("kind"),
        "state": fact.get("state"),
        "source_memory_id": fact.get("source_memory_id"),
    }
    provenance = _provenance(fact)
    provenance["validity"] = validity
    quote = str(fact.get("value") or "")
    text = (turn_text or {}).get(fact.get("source_memory_id") or "")
    return MemoryUnit(
        memory_id=fact["memory_id"],
        kind="fact",
        text=fact.get("content") or "",
        structured=structured,
        entity_ids=[entity_id(fact.get("entity"))] if fact.get("entity") else [],
        t_event=t_event,
        t_ingest=t_ingest,
        valid_interval=valid_interval,
        evidence=[_span(turn_id, quote, text)] if turn_id and quote else [],
        provenance=provenance,
        schema_version=SCHEMA_VERSION,
    )


def relations_from_legacy(facts: Sequence[Mapping[str, Any]]) -> list[Relation]:
    """Project the offline version chains onto typed :class:`Relation` edges."""
    by_id = {fact["memory_id"]: fact for fact in facts}
    output: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for fact in facts:
        for relation in fact.get("relations") or []:
            if relation.get("direction") != "to":
                continue
            tail_id = relation.get("memory_id")
            kind = relation.get("type")
            if not tail_id or tail_id not in by_id or tail_id == fact["memory_id"] or not kind:
                continue
            key = (fact["memory_id"], tail_id, str(kind))
            if key in seen:
                continue
            seen.add(key)
            head_event = _event_interval(fact.get("resolved_date"))
            tail_event = _event_interval(by_id[tail_id].get("resolved_date"))
            output.append(Relation(
                relation_id="rel:" + ":".join(key),
                head_id=key[0],
                tail_id=key[1],
                type=str(kind),
                t_valid=Interval(start=head_event.start, end=tail_event.start, precision="day")
                if head_event.start or tail_event.start else None,
                provenance={
                    "origin": "memwb.states.version_chain",
                    "reason": relation.get("reason", ""),
                    "slot_key": fact.get("slot_key"),
                },
            ))
    return output


@dataclass
class MemoryView:
    """A conversation as v2 units plus relation edges; read-only."""

    conversation: str
    units: list[MemoryUnit]
    relations: list[Relation] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def by_id(self) -> dict[str, MemoryUnit]:
        return {unit.memory_id: unit for unit in self.units}

    def of_kind(self, kind: str) -> list[MemoryUnit]:
        if kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {kind!r}")
        return [unit for unit in self.units if unit.kind == kind]


def from_legacy(turns: Sequence[Mapping[str, Any]], facts: Sequence[Mapping[str, Any]],
                *, conversation: str | None = None) -> MemoryView:
    """Convert records already produced by ``memwb.memory.build``."""
    facts_by_id = {fact["memory_id"]: fact for fact in facts}
    turn_text = {turn["memory_id"]: turn.get("content") or "" for turn in turns}
    units = [from_turn(turn) for turn in turns]
    units.extend(from_fact(fact, facts_by_id=facts_by_id, turn_text=turn_text) for fact in facts)
    sample_id = conversation or next(
        (turn.get("source", {}).get("conversation") for turn in turns if turn.get("source")), ""
    )
    return MemoryView(conversation=sample_id, units=units, relations=relations_from_legacy(facts))


def from_sample(sample: Mapping[str, Any]) -> MemoryView:
    """Build the v2 view of one conversation from the existing facts/state files."""
    turns, facts = legacy_memory.build(sample)
    return from_legacy(turns, facts, conversation=sample.get("sample_id"))


def load(sample_id: str) -> MemoryView:
    """Load a conversation through the shared dataset store."""
    from memwb import dataset

    return from_sample(dataset.store().get(sample_id))


# ---- serialisation -----------------------------------------------------

def interval_to_dict(value: Interval | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "start": value.start.isoformat() if value.start else None,
        "end": value.end.isoformat() if value.end else None,
        "precision": value.precision,
    }


def interval_from_dict(value: Mapping[str, Any] | None) -> Interval | None:
    if value is None:
        return None
    return Interval(start=parse_time(value.get("start")), end=parse_time(value.get("end")),
                    precision=value.get("precision", "unknown"))


def span_to_dict(value: Span) -> dict[str, Any]:
    return {"turn_id": value.turn_id, "quote": value.quote, "start": value.start, "end": value.end}


def span_from_dict(value: Mapping[str, Any]) -> Span:
    return Span(turn_id=value["turn_id"], quote=value["quote"],
                start=value.get("start"), end=value.get("end"))


def unit_to_dict(unit: MemoryUnit) -> dict[str, Any]:
    """The ``memory-export@2`` shape of one unit."""
    return {
        "memory_id": unit.memory_id,
        "kind": unit.kind,
        "text": unit.text,
        "structured": dict(unit.structured),
        "entity_ids": list(unit.entity_ids),
        "t_event": interval_to_dict(unit.t_event),
        "t_ingest": interval_to_dict(unit.t_ingest),
        "valid_interval": interval_to_dict(unit.valid_interval),
        "evidence": [span_to_dict(span) for span in unit.evidence],
        "confidence": unit.confidence,
        "provenance": dict(unit.provenance),
        "schema_version": unit.schema_version,
    }


def unit_from_dict(value: Mapping[str, Any]) -> MemoryUnit:
    version = value.get("schema_version")
    if version not in (None, SCHEMA_VERSION):
        raise ValueError(f"unsupported memory schema version: {version!r}")
    return MemoryUnit(
        memory_id=value["memory_id"],
        kind=value["kind"],
        text=value.get("text", ""),
        structured=dict(value.get("structured") or {}),
        entity_ids=list(value.get("entity_ids") or []),
        t_event=interval_from_dict(value.get("t_event")),
        t_ingest=interval_from_dict(value.get("t_ingest")),
        valid_interval=interval_from_dict(value.get("valid_interval")),
        evidence=[span_from_dict(span) for span in value.get("evidence") or []],
        confidence=value.get("confidence", 1.0),
        provenance=dict(value.get("provenance") or {}),
        schema_version=version or SCHEMA_VERSION,
    )


def relation_to_dict(relation: Relation) -> dict[str, Any]:
    return {
        "relation_id": relation.relation_id,
        "head_id": relation.head_id,
        "tail_id": relation.tail_id,
        "type": relation.type,
        "t_valid": interval_to_dict(relation.t_valid),
        "t_ingest": interval_to_dict(relation.t_ingest),
        "invalidated_by": relation.invalidated_by,
        "evidence": [span_to_dict(span) for span in relation.evidence],
        "confidence": relation.confidence,
        "provenance": dict(relation.provenance),
    }


def relation_from_dict(value: Mapping[str, Any]) -> Relation:
    return Relation(
        relation_id=value["relation_id"],
        head_id=value["head_id"],
        tail_id=value["tail_id"],
        type=value["type"],
        t_valid=interval_from_dict(value.get("t_valid")),
        t_ingest=interval_from_dict(value.get("t_ingest")),
        invalidated_by=value.get("invalidated_by"),
        evidence=[span_from_dict(span) for span in value.get("evidence") or []],
        confidence=value.get("confidence", 1.0),
        provenance=dict(value.get("provenance") or {}),
    )


def to_legacy(unit: MemoryUnit, relations: Iterable[Relation] = ()) -> dict[str, Any]:
    """Reconstruct the legacy record shape for regression checks.

    Fields that only exist in v2 (entity ids, canonical intervals) are dropped;
    everything that came from ``memwb.memory.build`` is restored from
    ``structured`` and ``provenance``.
    """
    data, provenance = unit.structured, unit.provenance
    record: dict[str, Any] = {
        "memory_id": unit.memory_id,
        "type": unit.kind,
        "content": unit.text,
        "entity": data.get("speaker") if unit.kind == "turn" else data.get("entity"),
        "timestamp": provenance.get("timestamp"),
        "session_time": provenance.get("session_time"),
        "source": dict(provenance.get("source") or {}),
        "state": data.get("state"),
    }
    if unit.kind == "turn":
        record["resolved_time_expressions"] = list(provenance.get("resolved_time_expressions") or [])
        record["fact_ids"] = list(data.get("fact_ids") or [])
        return record
    record.update(
        attribute=data.get("attribute"),
        value=data.get("value"),
        event=data.get("event"),
        time_expression=data.get("time_expression"),
        resolved_date=data.get("resolved_date"),
        slot=data.get("slot"),
        kind=data.get("kind"),
        slot_key=provenance.get("legacy_slot_key"),
        source_memory_id=data.get("source_memory_id"),
    )
    links = []
    for relation in relations:
        if relation.head_id == unit.memory_id:
            links.append({"type": relation.type, "direction": "to", "memory_id": relation.tail_id,
                          "reason": relation.provenance.get("reason", "")})
        elif relation.tail_id == unit.memory_id:
            links.append({"type": relation.type, "direction": "from", "memory_id": relation.head_id,
                          "reason": relation.provenance.get("reason", "")})
    record["relations"] = links
    return record


def validity_known(unit: MemoryUnit) -> bool:
    """Whether the unit's validity endpoint is actually known.

    A HISTORICAL fact with no recorded invalidating relation has ``end=None`` in
    its interval, which :meth:`Interval.contains` would read as "open-ended".
    That is not evidence that the fact is still true; it is missing evidence.
    Consumers doing as-of filtering must check this helper instead of treating
    ``end is None`` as "valid forever".
    """
    if unit.kind != "fact":
        return True
    validity = unit.provenance.get("validity")
    if not isinstance(validity, Mapping):
        return unit.valid_interval is not None
    if validity.get("endpoint") == "unknown" and unit.structured.get("state") == "HISTORICAL":
        return False
    return True


def is_valid_at(unit: MemoryUnit, moment: datetime) -> bool | None:
    """Three-valued as-of test: True, False, or None when validity is unknown."""
    if not validity_known(unit):
        return None
    interval = unit.valid_interval
    if interval is not None and interval.start is not None:
        return interval.contains(moment)
    # An active fact with no event time is observed at ingest time; this preserves
    # the legacy temporal filter while never treating an unknown endpoint as valid.
    ingest = unit.t_ingest
    if ingest is not None and ingest.start is not None:
        return ingest.start <= moment
    return True
