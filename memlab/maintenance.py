"""K module: maintenance actions and long-term health metrics.

Minimal but executable S4 implementation:

* ``update`` applies a W resolver decision to the store;
* ``forget`` implements archive / TTL (nothing is deleted without an explicit policy);
* ``consolidate`` deduplicates exact/near duplicates;
* ``scan`` reports staleness, contradictions and duplicates, plus the three K metrics
  (staleness, contradiction rate, update correctness).

Archiving keeps the removed units in the returned result: maintenance may take a
memory out of active retrieval, but it does not silently destroy it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from memwb import retrieval as legacy_retrieval

from . import model
from .contracts import MemoryUnit, WriteDecision
from .registry import build as build_impl
from .write import AXIS_RESOLVER, fact_fields


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return model.parse_time(value)


def _key(unit: MemoryUnit) -> tuple[Any, Any]:
    fields = fact_fields(unit)
    return fields.get("entity"), fields.get("attribute")


def _value(unit: MemoryUnit) -> Any:
    return fact_fields(unit).get("value")


def _latest(units: Sequence[MemoryUnit]) -> MemoryUnit:
    return max(units, key=lambda unit: (
        unit.t_ingest.start.isoformat() if unit.t_ingest and unit.t_ingest.start else "",
        unit.memory_id,
    ))


def _similarity(left: Any, right: Any) -> float:
    a = set(legacy_retrieval.tokens(str(left)))
    b = set(legacy_retrieval.tokens(str(right)))
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if a | b else 0.0


@dataclass(frozen=True)
class ScanReport:
    stale: tuple[str, ...]
    contradictions: tuple[tuple[str, str], ...]
    duplicates: tuple[str, ...]
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "stale": list(self.stale),
            "contradictions": [list(pair) for pair in self.contradictions],
            "duplicates": list(self.duplicates),
            "metrics": dict(self.metrics),
        }


def facts(store: Any) -> list[MemoryUnit]:
    return [unit for unit in store.units if unit.kind == "fact"]


def contradiction_pairs(store: Any) -> list[tuple[str, str]]:
    groups: dict[tuple[Any, Any], list[MemoryUnit]] = {}
    for unit in facts(store):
        groups.setdefault(_key(unit), []).append(unit)
    pairs: list[tuple[str, str]] = []
    for group in groups.values():
        # Different values over time are versions, not contradictions.  Only two
        # simultaneously-active values, or an explicit CONFLICT state, disagree.
        active = [unit for unit in group if fact_fields(unit).get("state") == "ACTIVE"]
        conflicted = [unit for unit in group if fact_fields(unit).get("state") == "CONFLICT"]
        for index, left in enumerate(active):
            for right in active[index + 1:]:
                if str(_value(left)) != str(_value(right)):
                    pairs.append((left.memory_id, right.memory_id))
        for unit in conflicted:
            for other in group:
                if other.memory_id != unit.memory_id and str(_value(other)) != str(_value(unit)):
                    pair = (unit.memory_id, other.memory_id)
                    if pair not in pairs and pair[::-1] not in pairs:
                        pairs.append(pair)
    for pair in getattr(store, "conflicts", []):
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def duplicate_pairs(store: Any, threshold: float = 0.9) -> list[tuple[str, str]]:
    groups: dict[tuple[Any, Any], list[MemoryUnit]] = {}
    for unit in facts(store):
        groups.setdefault(_key(unit), []).append(unit)
    pairs: list[tuple[str, str]] = []
    for group in groups.values():
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                if _similarity(_value(left), _value(right)) >= threshold:
                    pairs.append((left.memory_id, right.memory_id))
    return pairs


def staleness(store: Any, as_of: Any = None) -> float | None:
    all_facts = facts(store)
    if not all_facts:
        return None
    reference = _as_datetime(as_of)
    if reference is None:
        moments = [unit.t_ingest.start for unit in all_facts
                   if unit.t_ingest is not None and unit.t_ingest.start is not None]
        reference = max(moments) if moments else None
    if reference is None:
        return None
    stale = 0
    for unit in all_facts:
        state = fact_fields(unit).get("state")
        interval = unit.valid_interval
        endpoint = interval.end if interval is not None else None
        if state == "HISTORICAL" and (endpoint is None or endpoint <= reference):
            stale += 1
    return round(stale / len(all_facts), 4)


def update_correctness(store: Any) -> float | None:
    groups: dict[tuple[Any, Any], list[MemoryUnit]] = {}
    for unit in facts(store):
        groups.setdefault(_key(unit), []).append(unit)
    if not groups:
        return None
    correct = 0
    for group in groups.values():
        latest = _latest(group)
        if fact_fields(latest).get("state") == "ACTIVE":
            correct += 1
    return round(correct / len(groups), 4)


def metrics(store: Any, as_of: Any = None) -> dict[str, Any]:
    contradictions = contradiction_pairs(store)
    all_facts = facts(store)
    involved = {memory_id for pair in contradictions for memory_id in pair}
    return {
        "staleness": staleness(store, as_of),
        "contradiction_rate": round(len(involved) / len(all_facts), 4) if all_facts else None,
        "contradictions": len(contradictions),
        "update_correctness": update_correctness(store),
    }


def scan(store: Any, as_of: Any = None, threshold: float = 0.9) -> ScanReport:
    reference = _as_datetime(as_of)
    if reference is None:
        moments = [unit.t_ingest.start for unit in facts(store)
                   if unit.t_ingest is not None and unit.t_ingest.start is not None]
        reference = max(moments) if moments else None
    stale = []
    if reference is not None:
        for unit in facts(store):
            if fact_fields(unit).get("state") != "HISTORICAL":
                continue
            interval = unit.valid_interval
            endpoint = interval.end if interval is not None else None
            if endpoint is None or endpoint <= reference:
                stale.append(unit.memory_id)
    return ScanReport(
        stale=tuple(stale),
        contradictions=tuple(contradiction_pairs(store)),
        duplicates=tuple(sorted({memory_id for pair in duplicate_pairs(store, threshold) for memory_id in pair})),
        metrics=metrics(store, reference),
    )


@dataclass
class MaintenanceResult:
    action: str
    removed: list[str]
    archived: list[MemoryUnit]
    decision: WriteDecision | None = None
    report: ScanReport | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "removed": list(self.removed),
            "archived": len(self.archived),
            "report": self.report.as_dict() if self.report is not None else None,
            "decision": {
                "add": len(self.decision.add), "update": len(self.decision.update),
                "delete": len(self.decision.delete), "noop": len(self.decision.noop),
            } if self.decision is not None else None,
        }


def update(store: Any, incoming: Sequence[MemoryUnit], resolver: str = "mem0_4action",
           *, params: Mapping[str, Any] | None = None, ctx: Any = None) -> MaintenanceResult:
    implementation = build_impl(AXIS_RESOLVER, resolver, params)
    decision = implementation.resolve(list(incoming), store, ctx)
    store.apply(decision)
    return MaintenanceResult(action=f"update:{resolver}", removed=list(decision.delete),
                             archived=[], decision=decision)


def forget(store: Any, policy: str = "none", *, params: Mapping[str, Any] | None = None,
           as_of: Any = None) -> MaintenanceResult:
    options = dict(params or {})
    reference = _as_datetime(as_of)
    if reference is None:
        moments = [unit.t_ingest.start for unit in store.units
                   if unit.t_ingest is not None and unit.t_ingest.start is not None]
        reference = max(moments) if moments else None
    if policy in ("none", "time_decay") or reference is None:
        return MaintenanceResult(action=f"forget:{policy}", removed=[], archived=[])
    if policy == "archive":
        days = int(options.get("age_days", options.get("archive_after_days", 180)) or 180)
        cutoff = reference - timedelta(days=days)
        removed = [unit for unit in store.units
                   if unit.t_ingest is not None and unit.t_ingest.start is not None
                   and unit.t_ingest.start < cutoff]
    elif policy == "ttl":
        days = int(options.get("ttl_days", 365) or 365)
        cutoff = reference - timedelta(days=days)
        removed = [unit for unit in store.units
                   if unit.t_ingest is not None and unit.t_ingest.start is not None
                   and unit.t_ingest.start < cutoff]
    else:
        raise ValueError(f"unknown forget policy: {policy!r}")
    for unit in removed:
        store.remove(unit.memory_id)
    return MaintenanceResult(action=f"forget:{policy}", removed=[unit.memory_id for unit in removed],
                             archived=removed)


def consolidate(store: Any, strategy: str = "dedupe", *, params: Mapping[str, Any] | None = None) -> MaintenanceResult:
    options = dict(params or {})
    if strategy in ("none", "summarize", "reflect"):
        return MaintenanceResult(action=f"consolidate:{strategy}", removed=[], archived=[])
    if strategy != "dedupe":
        raise ValueError(f"unknown consolidate strategy: {strategy!r}")
    threshold = float(options.get("threshold", 0.9))
    groups: dict[tuple[Any, Any], list[MemoryUnit]] = {}
    for unit in facts(store):
        groups.setdefault(_key(unit), []).append(unit)
    removed: list[MemoryUnit] = []
    for group in groups.values():
        kept: list[MemoryUnit] = []
        for unit in group:
            if any(_similarity(_value(unit), _value(other)) >= threshold for other in kept):
                removed.append(unit)
            else:
                kept.append(unit)
    for unit in removed:
        store.remove(unit.memory_id)
    return MaintenanceResult(action="consolidate:dedupe", removed=[unit.memory_id for unit in removed],
                             archived=removed)


def scan_action(store: Any, *, as_of: Any = None, threshold: float = 0.9) -> MaintenanceResult:
    report = scan(store, as_of, threshold)
    return MaintenanceResult(action="scan", removed=[], archived=[], report=report)
