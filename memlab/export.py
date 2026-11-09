"""Memory export v2, with the legacy v1 exporter kept intact.

``memory-export@2`` exports :class:`~memlab.contracts.MemoryUnit` records plus
typed relations, so downstream code never has to read a prompt-specific shape.
``schema="v1"`` delegates to :func:`memwb.export.export` unchanged: old exports,
old clients and the existing Web endpoint keep working while the v2 path is
rolled out (S5/Lab UI).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from memwb import config as legacy_config
from memwb import dataset
from memwb import export as legacy_export

from . import model
from .contracts import INTERVAL_PRECISIONS, MEMORY_KINDS

SCHEMA_V1 = legacy_export.SCHEMA
SCHEMA_V2 = "dynamic-memory-workbench/memory-export@2"

_REQUIRED_MEMORY_FIELDS = (
    "memory_id", "kind", "text", "structured", "entity_ids", "t_event", "t_ingest",
    "valid_interval", "evidence", "confidence", "provenance", "schema_version",
)
_REQUIRED_RELATION_FIELDS = ("relation_id", "head_id", "tail_id", "type")


def export_v1(sample: Mapping[str, Any]) -> dict[str, Any]:
    """The untouched legacy export (``dynamic-memory-workbench/memory-export@1``)."""
    return legacy_export.export(sample)


def export_v2(sample: Mapping[str, Any]) -> dict[str, Any]:
    """The canonical v2 export of one conversation."""
    view = model.from_sample(sample)
    counts = Counter(unit.kind for unit in view.units)
    return {
        "schema": SCHEMA_V2,
        "conversation": sample["sample_id"],
        "split": legacy_config.split_of(sample["sample_id"]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "schema_version": model.SCHEMA_VERSION,
        "extraction_model": legacy_config.extraction_model(),
        "notes": [
            "t_ingest is the session recording time; t_event is only set when the record carries a resolvable date.",
            "An unknown time is exported as precision='unknown' with null bounds; it is never guessed.",
            "Facts, slots, states and relations are machine-generated and unverified; evidence points to the source turn.",
        ],
        "counts": {
            "memories": len(view.units),
            "by_kind": dict(sorted(counts.items())),
            "relations": len(view.relations),
        },
        "memories": [model.unit_to_dict(unit) for unit in view.units],
        "relations": [model.relation_to_dict(relation) for relation in view.relations],
    }


_SCHEMAS = {
    "1": "v1", "v1": "v1", SCHEMA_V1: "v1",
    "2": "v2", "v2": "v2", SCHEMA_V2: "v2",
}


def export(sample: Mapping[str, Any], schema: str = "v2") -> dict[str, Any]:
    """Export one conversation; ``schema`` is ``v1`` or ``v2`` (default v2)."""
    key = _SCHEMAS.get(str(schema).strip())
    if key is None:
        raise ValueError(f"unknown export schema: {schema!r}; expected one of {sorted({'v1', 'v2'})}")
    return export_v1(sample) if key == "v1" else export_v2(sample)


def export_all(sample_ids: list[str] | None = None, schema: str = "v2") -> dict[str, dict[str, Any]]:
    store = dataset.store()
    return {sid: export(store.get(sid), schema) for sid in (sample_ids or legacy_config.COURSE_SAMPLES)}


def _interval_problems(value: Any, path: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return [f"{path} must be an object or null"]
    problems = []
    if value.get("precision") not in INTERVAL_PRECISIONS:
        problems.append(f"{path}.precision must be one of {list(INTERVAL_PRECISIONS)}")
    for side in ("start", "end"):
        bound = value.get(side)
        if bound is None:
            continue
        if not isinstance(bound, str) or model.parse_time(bound) is None:
            problems.append(f"{path}.{side} must be an ISO datetime string or null")
    return problems


def validate_v2(document: Any) -> None:
    """Assert the shape of an export document; raises ``ValueError`` with every problem.

    This is deliberately dependency-free: S2 only needs a strict contract check,
    not a JSON-Schema runtime.
    """
    if not isinstance(document, Mapping):
        raise ValueError("invalid memory-export@2: document must be an object")
    problems: list[str] = []
    if document.get("schema") != SCHEMA_V2:
        problems.append(f"schema must be {SCHEMA_V2!r}")
    if not isinstance(document.get("conversation"), str) or not document.get("conversation"):
        problems.append("conversation must be a non-empty string")
    if document.get("schema_version") != model.SCHEMA_VERSION:
        problems.append(f"schema_version must be {model.SCHEMA_VERSION!r}")

    memories = document.get("memories")
    if not isinstance(memories, list):
        problems.append("memories must be a list")
        memories = []
    memory_ids: set[str] = set()
    for index, item in enumerate(memories):
        path = f"memories[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{path} must be an object")
            continue
        missing = [field for field in _REQUIRED_MEMORY_FIELDS if field not in item]
        if missing:
            problems.append(f"{path} missing {missing}")
            continue
        memory_ids.add(str(item["memory_id"]))
        if item["kind"] not in MEMORY_KINDS:
            problems.append(f"{path}.kind must be one of {list(MEMORY_KINDS)}")
        if not isinstance(item["entity_ids"], list):
            problems.append(f"{path}.entity_ids must be a list")
        if not isinstance(item["structured"], Mapping):
            problems.append(f"{path}.structured must be an object")
        problems.extend(_interval_problems(item["t_event"], f"{path}.t_event"))
        problems.extend(_interval_problems(item["t_ingest"], f"{path}.t_ingest"))
        problems.extend(_interval_problems(item["valid_interval"], f"{path}.valid_interval"))
        evidence = item["evidence"]
        if not isinstance(evidence, list):
            problems.append(f"{path}.evidence must be a list")
        else:
            for span_index, span in enumerate(evidence):
                if not isinstance(span, Mapping) or not span.get("turn_id") or not isinstance(span.get("quote"), str):
                    problems.append(f"{path}.evidence[{span_index}] needs turn_id and quote")

    relations = document.get("relations")
    if not isinstance(relations, list):
        problems.append("relations must be a list")
        relations = []
    for index, item in enumerate(relations):
        path = f"relations[{index}]"
        if not isinstance(item, Mapping):
            problems.append(f"{path} must be an object")
            continue
        missing = [field for field in _REQUIRED_RELATION_FIELDS if field not in item]
        if missing:
            problems.append(f"{path} missing {missing}")
            continue
        for side in ("head_id", "tail_id"):
            if item[side] not in memory_ids:
                problems.append(f"{path}.{side} references an unknown memory_id")
        problems.extend(_interval_problems(item.get("t_valid"), f"{path}.t_valid"))

    counts = document.get("counts")
    if not isinstance(counts, Mapping):
        problems.append("counts must be an object")
    else:
        if counts.get("memories") != len(memories):
            problems.append("counts.memories does not match memories")
        by_kind = Counter(item.get("kind") for item in memories if isinstance(item, Mapping))
        if counts.get("by_kind") != dict(sorted(by_kind.items())):
            problems.append("counts.by_kind does not match memories")
        if counts.get("relations") != len(relations):
            problems.append("counts.relations does not match relations")

    if problems:
        raise ValueError("invalid memory-export@2: " + "; ".join(problems[:20]))


def read(path: str) -> dict[str, Any]:
    """Read an exported JSON file and validate it when it claims to be v2."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(document, Mapping) and document.get("schema") == SCHEMA_V2:
        validate_v2(document)
    return document
