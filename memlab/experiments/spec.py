"""Experiment specification loading and validation.

A spec is the *design* (factors, environment, dataset, protocol); a run config is
one concrete point in that design.  Keeping the two separate is what lets the
compiler produce a reproducible matrix and the runner store one row per point.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .. import config as lab_config

SPEC_SCHEMA = "memlab/experiment@1"
DESIGNS = {
    "single_factor", "single_factor_adoption", "single_factor_variant_and_parameter",
    "full_factorial", "fractional_factorial", "environment_grid", "nested_factorial",
    "coupling_analysis",
}


class SpecError(ValueError):
    """A spec cannot be compiled; the message names every problem found."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("invalid experiment spec: " + "; ".join(self.problems))


def _resolve(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


@dataclass(frozen=True)
class Spec:
    path: Path
    data: dict[str, Any]
    reference: Path | None
    reference_off: Path | None
    reference_on: Path | None
    references: dict[str, Path] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def design(self) -> str:
        return str(self.data["design"])

    @property
    def title(self) -> str:
        return str(self.data.get("title") or self.id)

    @property
    def deferred(self) -> list[dict[str, Any]]:
        """Factor levels removed from the executable matrix, with a reason.

        A level that cannot run must not silently disappear from a spec: the
        removed levels are recorded here so ``sweep`` can report them and the next
        session can decide when they re-enter.
        """
        return [dict(item) for item in self.data.get("deferred") or [] if isinstance(item, Mapping)]

    @property
    def environment(self) -> dict[str, Any]:
        value = self.data.get("environment")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def dataset(self) -> dict[str, Any]:
        value = self.data.get("dataset")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def protocol(self) -> dict[str, Any]:
        value = self.data.get("protocol")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def factors(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.data.get("factors") or [] if isinstance(item, Mapping)]

    @property
    def modules(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.data.get("modules") or [] if isinstance(item, Mapping)]

    @property
    def spec_hash(self) -> str:
        return lab_config.digest(self.data)

    def reference_config(self, which: str = "default") -> dict[str, Any]:
        path = self.references.get(which)
        if path is None:
            path = {"default": self.reference, "off": self.reference_off,
                    "on": self.reference_on}.get(which)
        if path is None:
            raise SpecError([f"spec has no reference config for {which!r}"])
        return json.loads(path.read_text(encoding="utf-8"))


def _check_factor(factor: Mapping[str, Any], index: int) -> list[str]:
    problems: list[str] = []
    name = factor.get("id")
    if not isinstance(name, str) or not name.strip():
        problems.append(f"factors[{index}].id must be a non-empty string")
    has_levels = isinstance(factor.get("levels"), list)
    has_low_high = "low" in factor and "high" in factor
    if not has_levels and not has_low_high:
        problems.append(f"factors[{index}] needs levels[] or low/high")
    if has_levels and not factor["levels"]:
        problems.append(f"factors[{index}].levels must not be empty")
    return problems


def validate(data: Any, *, base: Path | None = None) -> list[str]:
    if not isinstance(data, Mapping):
        return ["spec must be a JSON object"]
    problems: list[str] = []
    spec_id = data.get("id")
    if not isinstance(spec_id, str) or not spec_id.strip():
        problems.append("id must be a non-empty string")
    design = data.get("design")
    if design not in DESIGNS:
        problems.append(f"design must be one of {sorted(DESIGNS)}")
    if "reference_config" not in data and "reference_configs" not in data:
        problems.append("spec needs reference_config or reference_configs")
    if isinstance(data.get("factors"), list):
        for index, factor in enumerate(data["factors"]):
            if isinstance(factor, Mapping):
                problems.extend(_check_factor(factor, index))
            else:
                problems.append(f"factors[{index}] must be an object")
    if isinstance(data.get("modules"), list):
        for index, module in enumerate(data["modules"]):
            if not isinstance(module, Mapping) or not isinstance(module.get("id"), str):
                problems.append(f"modules[{index}] needs an id")
            elif "off" not in module or "on" not in module:
                problems.append(f"modules[{index}] needs off and on")
    if "deferred" in data:
        deferred = data.get("deferred")
        if not isinstance(deferred, list):
            problems.append("deferred must be a list")
        else:
            for index, item in enumerate(deferred):
                if not isinstance(item, Mapping):
                    problems.append(f"deferred[{index}] must be an object")
                    continue
                if not isinstance(item.get("id"), str) or not item["id"].strip():
                    problems.append(f"deferred[{index}] needs a non-empty id")
                levels = item.get("levels")
                if not isinstance(levels, list) or not levels:
                    problems.append(f"deferred[{index}].levels must be a non-empty list")
                if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                    problems.append(f"deferred[{index}] needs a reason")
                if not isinstance(item.get("status"), str) or not item["status"].strip():
                    problems.append(f"deferred[{index}] needs a status")
    if design == "environment_grid" and not isinstance(data.get("grid"), Mapping):
        problems.append("environment_grid requires grid")
    if base is not None:
        if data.get("reference_config"):
            target = _resolve(base, str(data["reference_config"]))
            if target is None or not target.is_file():
                problems.append(f"reference_config not found: {data['reference_config']}")
        refs = data.get("reference_configs")
        if isinstance(refs, Mapping):
            for key, value in refs.items():
                target = _resolve(base, str(value))
                if target is None or not target.is_file():
                    problems.append(f"reference_configs.{key} not found: {value}")
    return problems


def load(path: str | Path) -> Spec:
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SpecError([f"cannot read {path}: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise SpecError([f"invalid JSON in {path}: {exc}"]) from exc
    problems = validate(data, base=path.parent)
    if problems:
        raise SpecError(problems)
    refs = data.get("reference_configs") if isinstance(data.get("reference_configs"), Mapping) else {}
    references: dict[str, Path] = {}
    for key, value in refs.items():
        resolved = _resolve(path.parent, str(value))
        if resolved is not None:
            references[str(key)] = resolved
    default = _resolve(path.parent, data.get("reference_config"))
    if default is not None:
        references.setdefault("default", default)
    return Spec(
        path=path,
        data=dict(data),
        reference=_resolve(path.parent, data.get("reference_config")),
        reference_off=_resolve(path.parent, refs.get("off")),
        reference_on=_resolve(path.parent, refs.get("on")),
        references=references,
    )
