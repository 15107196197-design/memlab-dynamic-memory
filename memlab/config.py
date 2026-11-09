"""Run configuration: loading, validation and canonical hashing.

A run config says *what* to run (modules, implementations, parameters, environment)
and never contains code paths.  Its stable identity is

    config_hash = sha256(canonical_json(config))

which is written into every run manifest and, from S2 on, into every cache key.
Validation has three jobs, in this order:

1. structural checks (an object where an object is expected, a string where a
   string is expected);
2. catalogue checks - every selected implementation must exist in
   ``configs/variants.json``; an unknown name reports the available ones;
3. capability checks - combinations that cannot work are rejected instead of
   failing halfway through an experiment (e.g. ``graph.repr=none`` with a
   non-vector graph retriever).

The catalogue is intentionally wider than the implementations registered so far:
S1 ships only legacy methods, while the configs already select R0 modules that
later sessions implement.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE = ROOT / "configs" / "variants.json"
CONFIG_SCHEMA = "memlab/run-config@1"

DEFAULT_METHOD = "legacy_dynamic"

# Top-level blocks that must be objects when present.
MODULE_BLOCKS = (
    "schema", "write", "graph", "planner", "retrieval", "fusion", "rerank",
    "post", "temporal", "logic", "answer", "forgetting", "environment", "dataset",
    "evaluation", "method", "pipeline",
)


class ConfigError(ValueError):
    """One or more configuration problems; ``problems`` keeps every reason."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("invalid run config: " + "; ".join(self.problems))


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"value is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    """``sha256:<hex>`` of the canonical JSON encoding of ``value``."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def get_path(data: Mapping[str, Any], path: str, default: Any = None) -> Any:
    """Read a dotted path, returning ``default`` when any segment is missing."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


@dataclass(frozen=True)
class CatalogueEntry:
    path: str
    kind: str  # "impl" for {"impl": name, "params": ...}; "value" for a bare string
    names: frozenset[str]


# Bare-string roots whose config key differs from the catalogue id.
_VALUE_LIST_AXES = {"forgetting": "forgetting.policy"}
# Nested catalogue axes that hold bare strings rather than {"impl": ...} blocks.
_VALUE_SUB_AXES = {"temporal", "logic"}


@lru_cache(maxsize=None)
def _catalogue(str_path: str) -> dict[str, CatalogueEntry]:
    document = json.loads(Path(str_path).read_text(encoding="utf-8"))
    entries: dict[str, CatalogueEntry] = {}
    for axis, spec in document.get("axes", {}).items():
        root = spec.get("config_root", axis)
        variants = spec.get("variants", [])
        if isinstance(variants, Mapping):
            kind = "value" if axis in _VALUE_SUB_AXES else "impl"
            for sub, items in variants.items():
                path = f"{root}.{sub}"
                entries[path] = CatalogueEntry(path, kind, frozenset(x["id"] for x in items))
        else:
            path = _VALUE_LIST_AXES.get(axis, root)
            kind = "value" if axis in _VALUE_LIST_AXES else "impl"
            entries[path] = CatalogueEntry(path, kind, frozenset(x["id"] for x in variants))
    return entries


def load_catalogue(path: str | Path | None = None) -> dict[str, CatalogueEntry]:
    """The implementation catalogue keyed by dotted config path."""
    return _catalogue(str(Path(path) if path is not None else DEFAULT_CATALOGUE))


def _impl_value(data: Mapping[str, Any], path: str) -> Any:
    """Implementation name at ``path``; tolerates both impl blocks and bare strings."""
    value = get_path(data, path)
    if isinstance(value, Mapping):
        return value.get("impl")
    if value is not None:
        return value
    # Older R0 files keep the conflict policy inside temporal.params.
    if path == "temporal.conflict_policy":
        return get_path(data, "temporal.params.conflict_policy")
    return None


def _structure_problems(data: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for key in MODULE_BLOCKS:
        if key in data and not isinstance(data[key], Mapping):
            problems.append(f"{key} must be an object, got {type(data[key]).__name__}")
    for block in ("write", "graph", "post"):
        value = data.get(block)
        if isinstance(value, Mapping):
            for sub, item in value.items():
                if not isinstance(item, Mapping):
                    problems.append(f"{block}.{sub} must be an object, got {type(item).__name__}")
    environment = data.get("environment")
    if isinstance(environment, Mapping):
        for sub in ("llm", "embedding", "judge"):
            item = environment.get(sub)
            if item is not None and not isinstance(item, Mapping):
                problems.append(f"environment.{sub} must be an object")
        llm = environment.get("llm")
        if isinstance(llm, Mapping) and not (isinstance(llm.get("model"), str) and llm["model"].strip()):
            problems.append("environment.llm.model must be a non-empty string")
        embedding = environment.get("embedding")
        if isinstance(embedding, Mapping) and not (isinstance(embedding.get("model"), str) and embedding["model"].strip()):
            problems.append("environment.embedding.model must be a non-empty string")
        seed = environment.get("seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            problems.append("environment.seed must be an integer")
    retrieval = data.get("retrieval")
    if isinstance(retrieval, Mapping):
        channels = retrieval.get("channels")
        if channels is not None and not (isinstance(channels, list) and all(isinstance(x, str) for x in channels)):
            problems.append("retrieval.channels must be a list of strings")
        k = retrieval.get("k")
        if k is not None and (not isinstance(k, int) or isinstance(k, bool) or k <= 0):
            problems.append("retrieval.k must be a positive integer")
    return problems


def _catalogue_problems(data: Mapping[str, Any], catalogue: Mapping[str, CatalogueEntry]) -> list[str]:
    problems: list[str] = []
    for path, entry in sorted(catalogue.items()):
        if entry.kind == "value":
            value = _impl_value(data, path)
            if value is None:
                continue
            if not isinstance(value, str):
                problems.append(f"{path} must be a string, got {type(value).__name__}")
            elif value not in entry.names:
                problems.append(f"unknown {path}={value!r}; available={sorted(entry.names)}")
            continue
        block = get_path(data, path)
        if block is None:
            continue
        if not isinstance(block, Mapping):
            problems.append(f"{path} must be an object with impl/params")
            continue
        impl = block.get("impl")
        if impl is None:
            continue
        if not isinstance(impl, str):
            problems.append(f"{path}.impl must be a string")
        elif impl not in entry.names:
            problems.append(f"unknown {path}.impl={impl!r}; available={sorted(entry.names)}")
        params = block.get("params")
        if params is not None and not isinstance(params, Mapping):
            problems.append(f"{path}.params must be an object")
    return problems


def _capability_problems(data: Mapping[str, Any]) -> list[str]:
    """Combinations that cannot be executed (docs/optimization/02-architecture.md 2.8)."""
    problems: list[str] = []
    graph_repr = _impl_value(data, "graph.repr")
    graph_retrieval = _impl_value(data, "graph.retrieval")

    if graph_repr == "none" and graph_retrieval not in (None, "vector_only"):
        problems.append(
            f"graph.repr=none disables the graph, so graph.retrieval must be 'vector_only' (got {graph_retrieval!r})"
        )
    if graph_retrieval == "slot_expand" and graph_repr not in (None, "state_slot"):
        problems.append(
            f"graph.retrieval=slot_expand requires graph.repr=state_slot (got {graph_repr!r})"
        )

    if _impl_value(data, "temporal.model") == "bitemporal":
        if _impl_value(data, "schema") != "meta_schema" or get_path(data, "schema.params.bitemporal") is not True:
            problems.append(
                "temporal.model=bitemporal requires schema.impl=meta_schema and schema.params.bitemporal=true"
            )
    if _impl_value(data, "temporal.conflict_policy") == "invalidate_edge":
        if graph_repr in (None, "none") and _impl_value(data, "write.resolver") != "bitemporal_invalidate":
            problems.append(
                "temporal.conflict_policy=invalidate_edge requires graph.repr!=none or "
                "write.resolver=bitemporal_invalidate"
            )

    if _impl_value(data, "planner") == "dag":
        analyzer = get_path(data, "planner.analyzer") or get_path(data, "planner.params.analyzer")
        if analyzer in (None, "none"):
            problems.append("planner.impl=dag requires planner.analyzer (or planner.params.analyzer) to be enabled")

    if _impl_value(data, "answer") == "evidence_chain" and get_path(data, "logic.evidence_chain") is not True:
        problems.append("answer.impl=evidence_chain requires logic.evidence_chain=true")

    rerank = _impl_value(data, "rerank")
    if rerank not in (None, "none"):
        channels = get_path(data, "retrieval.channels") or []
        if not channels:
            problems.append("rerank requires at least one retrieval channel")
    return problems


def problems(data: Any, catalogue: Mapping[str, CatalogueEntry] | None = None) -> list[str]:
    """Every validation problem in ``data``; empty means valid."""
    if not isinstance(data, Mapping):
        return [f"config must be a JSON object, got {type(data).__name__}"]
    found = _structure_problems(data)
    try:
        entries = load_catalogue() if catalogue is None else catalogue
    except (OSError, ValueError, KeyError):
        entries = {}
    found.extend(_catalogue_problems(data, entries))
    found.extend(_capability_problems(data))
    return found


def validate(data: Any, catalogue: Mapping[str, CatalogueEntry] | None = None) -> None:
    """Raise :class:`ConfigError` when the configuration cannot be executed."""
    found = problems(data, catalogue)
    if found:
        raise ConfigError(found)


def as_config(value: Any) -> "RunConfig":
    if isinstance(value, RunConfig):
        return value
    return RunConfig.from_dict(value, validate=False)


@dataclass(frozen=True)
class RunConfig:
    """A validated, hashable view over one run configuration."""

    data: dict[str, Any]
    source: str | None = None
    config_hash: str = field(init=False)

    def __post_init__(self):
        if not isinstance(self.data, Mapping):
            raise ConfigError([f"config must be a JSON object, got {type(self.data).__name__}"])
        payload = copy.deepcopy(dict(self.data))
        object.__setattr__(self, "data", payload)
        object.__setattr__(self, "config_hash", digest(payload))

    # ---- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, data: Any, *, validate: bool = True, source: str | None = None,
                  catalogue: Mapping[str, CatalogueEntry] | None = None) -> "RunConfig":
        if validate:
            found = problems(data, catalogue)
            if found:
                raise ConfigError(found)
        if not isinstance(data, Mapping):
            raise ConfigError(["config must be a JSON object"])
        return cls(data=dict(data), source=source)

    @classmethod
    def loads(cls, text: str, *, source: str | None = None,
              catalogue: Mapping[str, CatalogueEntry] | None = None) -> "RunConfig":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError([f"invalid JSON: {exc}"]) from exc
        return cls.from_dict(data, source=source, catalogue=catalogue)

    @classmethod
    def load(cls, path: str | Path, *, catalogue: Mapping[str, CatalogueEntry] | None = None) -> "RunConfig":
        file = Path(path)
        try:
            text = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError([f"cannot read {file}: {exc}"]) from exc
        return cls.loads(text, source=str(file), catalogue=catalogue)

    # ---- access -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)

    def get(self, path: str, default: Any = None) -> Any:
        return get_path(self.data, path, default)

    def impl(self, path: str) -> str | None:
        value = _impl_value(self.data, path)
        return value if isinstance(value, str) else None

    def params(self, path: str) -> dict[str, Any]:
        block = get_path(self.data, path)
        params = block.get("params") if isinstance(block, Mapping) else None
        return copy.deepcopy(dict(params)) if isinstance(params, Mapping) else {}

    @property
    def preset(self) -> str | None:
        preset = self.data.get("preset")
        return preset if isinstance(preset, str) else None

    @property
    def split(self) -> str | None:
        split = self.get("dataset.split")
        return split if isinstance(split, str) else None

    @property
    def seed(self) -> int | None:
        seed = self.get("environment.seed")
        return seed if isinstance(seed, int) and not isinstance(seed, bool) else None

    def _method_root(self) -> str:
        for root in ("method", "pipeline"):
            if isinstance(self.data.get(root), Mapping):
                return root
        return "method"

    @property
    def method(self) -> str:
        root = self._method_root()
        name = self.get(f"{root}.impl")
        return name if isinstance(name, str) and name else DEFAULT_METHOD

    @property
    def method_params(self) -> dict[str, Any]:
        return self.params(self._method_root())
