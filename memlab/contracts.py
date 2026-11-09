"""Stage contracts (docs/optimization/02-architecture.md 2.5-2.6).

These dataclasses are the only data that crosses stage boundaries.  Implementations
may add fields inside ``structured`` / ``provenance``, but never invent a new shape
for the envelope.  S1 defines them and validates obvious invariants; migration of
legacy records into :class:`MemoryUnit` happens in S2.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

MEMORY_KINDS = ("turn", "fact", "event", "summary", "reflection")
INTERVAL_PRECISIONS = ("year", "month", "day", "hour", "session", "unknown")
RELATION_TYPES = ("RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT")


@dataclass(frozen=True)
class Span:
    """Evidence pointer back to the source turn."""

    turn_id: str
    quote: str
    start: int | None = None  # character offset in the turn text
    end: int | None = None

    def __post_init__(self):
        if not self.turn_id:
            raise ValueError("Span.turn_id must not be empty")
        for name in ("start", "end"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError(f"Span.{name} must be a non-negative integer")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("Span.start must not be after Span.end")


@dataclass(frozen=True)
class Interval:
    """A time interval; open ends are allowed and precision records certainty."""

    start: datetime | None = None
    end: datetime | None = None
    precision: Literal["year", "month", "day", "hour", "session", "unknown"] = "unknown"

    def __post_init__(self):
        if self.precision not in INTERVAL_PRECISIONS:
            raise ValueError(f"unknown interval precision: {self.precision!r}")
        if isinstance(self.start, datetime) and isinstance(self.end, datetime) and self.start > self.end:
            raise ValueError("Interval.start must not be after Interval.end")

    def contains(self, moment: datetime) -> bool:
        """Half-open test used by as-of filtering: start <= moment < end."""
        if self.start is not None and moment < self.start:
            return False
        return self.end is None or moment < self.end


@dataclass
class MemoryUnit:
    """One memory: a turn, an extracted fact, an event, a summary or a reflection."""

    memory_id: str
    kind: Literal["turn", "fact", "event", "summary", "reflection"]
    text: str
    structured: dict[str, Any]  # schema-specific fields, validated by the extractor
    entity_ids: list[str] = field(default_factory=list)
    t_event: Interval | None = None  # when it is true in the world
    t_ingest: Interval | None = None  # when the system observed it
    valid_interval: Interval | None = None  # derived from t_event + invalidation
    evidence: list[Span] = field(default_factory=list)
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "2.0"

    def __post_init__(self):
        if not isinstance(self.memory_id, str) or not self.memory_id:
            raise ValueError("MemoryUnit.memory_id must be a non-empty string")
        if self.kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind: {self.kind!r}; expected one of {MEMORY_KINDS}")
        if not isinstance(self.structured, dict):
            raise ValueError("MemoryUnit.structured must be an object")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("MemoryUnit.confidence must be within [0, 1]")


@dataclass
class Relation:
    """A typed, optionally time-bounded edge between two memories."""

    relation_id: str
    head_id: str
    tail_id: str
    type: str  # RETAIN / UPDATE / SUPERSEDE / CONFLICT / CAUSES / PART_OF / ...
    t_valid: Interval | None = None
    t_ingest: Interval | None = None
    invalidated_by: str | None = None  # relation_id or memory_id that kills this edge
    evidence: list[Span] = field(default_factory=list)
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.relation_id:
            raise ValueError("Relation.relation_id must not be empty")
        if not self.head_id or not self.tail_id:
            raise ValueError("Relation.head_id and Relation.tail_id must not be empty")
        if self.head_id == self.tail_id:
            raise ValueError("Relation must not be a self-link")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Relation.confidence must be within [0, 1]")


@dataclass
class QueryFrame:
    """Normalised question, produced by the query analyzer and consumed by the planner."""

    query: str
    as_of: datetime | None = None
    intent: str = "none"  # single_hop / multi_hop / temporal / aggregation / ...
    entity_ids: list[str] = field(default_factory=list)
    temporal: dict[str, Any] = field(default_factory=dict)
    complexity: float = 0.0
    sub_questions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("QueryFrame.query must be a non-empty string")


@dataclass
class PlanNode:
    """One retrieval sub-query; ``depends_on`` turns the plan into a DAG."""

    node_id: str
    query: str
    channel: str
    depends_on: list[str] = field(default_factory=list)
    k: int = 15
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    nodes: list[PlanNode]
    parallel_groups: list[list[str]]
    rationale: str = ""
    estimated_cost: dict[str, float] = field(default_factory=dict)


@dataclass
class Candidate:
    """A retrieved memory with its provenance through the merge pipeline."""

    memory_id: str
    channel: str
    rank: int
    raw_score: float | None = None
    score: float | None = None
    stage_scores: dict[str, float] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class StateView:
    """The temporal/consistency result the answerer is allowed to use."""

    valid: list[MemoryUnit]
    superseded: list[MemoryUnit]
    conflicts: list[tuple[str, str]]
    evidence_chain: list[Relation]
    unresolved: list[str]
    as_of: datetime | None = None
    explanation: str = ""


@dataclass
class WriteDecision:
    """What the resolver decided to do with an incoming batch (02-architecture 2.6.2)."""

    add: list[MemoryUnit]
    update: list[tuple[str, MemoryUnit]]  # (old memory_id, new unit)
    delete: list[str]
    noop: list[MemoryUnit]
    relations: list[Relation]
    conflicts: list[tuple[str, str]]
    reasons: dict[str, str]
