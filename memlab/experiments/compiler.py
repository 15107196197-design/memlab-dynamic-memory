"""Compile an experiment spec into concrete run plans.

The compiler is deliberately pure: it reads the spec and reference JSON, applies
one factor at a time (or a factorial/grid), then applies the spec's
``derived_rules`` to close dependencies (for example graph.repr=none forces
graph.retrieval=vector_only).  It never calls a model.
"""
from __future__ import annotations

import copy
import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .. import config as lab_config
from .. import registry
from . import spec as spec_module


def get_path(data: Mapping[str, Any], path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = copy.deepcopy(value)


def set_impl(config: dict[str, Any], path: str, value: Any, *,
             keep_params: bool = False) -> None:
    """Set an ``*.impl`` path and drop params the new implementation cannot accept."""
    axis = path[:-5] if path.endswith(".impl") else path
    old = get_path(config, path)
    if not keep_params and old != value and axis != "planner":
        params_path = f"{axis}.params"
        params = get_path(config, params_path)
        if isinstance(params, Mapping):
            try:
                impl = registry.get(axis, str(value))
                allowed = getattr(impl, "params_allowed", frozenset())
                set_path(config, params_path, {key: item for key, item in params.items() if key in allowed})
            except Exception:
                pass
    set_path(config, path, value)


def apply_overrides(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-copy base and apply dotted-path overrides."""
    out = copy.deepcopy(dict(base))
    impl_paths = {str(path) for path in overrides if str(path).endswith(".impl")}
    explicit_params = {path[:-5] + ".params" for path in impl_paths}
    for path, value in overrides.items():
        path = str(path)
        if path.endswith(".impl"):
            set_impl(out, path, value, keep_params=path[:-5] + ".params" in overrides)
        else:
            set_path(out, path, value)
    return out


def normalize_environment(environment: Mapping[str, Any]) -> dict[str, Any]:
    """Accept the short spec form (``llm: model``) as well as the config form.

    Experiment specs use ``environment.llm = "qwen..."`` for readability, while a
    RunConfig requires ``environment.llm = {"model": ...}``.  Normalize here so a
    compiled plan is always a valid run config.
    """
    out = copy.deepcopy(dict(environment))
    for key in ("llm", "embedding", "judge"):
        value = out.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = {"model": value}
    return out


def merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _matches(config: Mapping[str, Any], condition: Mapping[str, Any]) -> bool:
    for path, expected in condition.items():
        actual = get_path(config, path)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def apply_derived_rules(config: dict[str, Any], rules: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    out = copy.deepcopy(config)
    applied: list[str] = []
    for _ in range(10):  # closure; bounded to catch cycles
        changed = False
        for rule in rules:
            when = rule.get("when")
            if not isinstance(when, Mapping) or not _matches(out, when):
                continue
            target = rule.get("set")
            if not isinstance(target, Mapping):
                continue
            for path, value in target.items():
                if get_path(out, path) != value:
                    set_path(out, path, value)
                    changed = True
                    applied.append(f"{rule.get('reason') or 'derived'}: {path}={value}")
        if not changed:
            break
    return out, applied


def capability_closure(config: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply generic fallbacks that keep a compiled plan executable.

    Experiment specs should express the dependency; this is a safety net so a
    matrix never contains a plan that ``RunConfig`` rejects.  It only downgrades a
    policy when the structure that policy needs is absent.
    """
    out = copy.deepcopy(config)
    notes: list[str] = []
    if get_path(out, "graph.repr.impl") == "none" and get_path(out, "temporal.params.conflict_policy") == "invalidate_edge":
        if get_path(out, "write.resolver.impl") != "bitemporal_invalidate":
            set_path(out, "temporal.params.conflict_policy", "keep_both")
            notes.append("capability closure: no graph -> conflict_policy=keep_both")
    return out, notes


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", str(value).lower()).strip("-")
    return slug[:40] or "run"


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    spec_id: str
    design: str
    config: dict[str, Any]
    requested_config: dict[str, Any]
    effective_config: dict[str, Any]
    config_hash: str
    environment: dict[str, Any]
    dataset: dict[str, Any]
    factors: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "spec_id": self.spec_id,
            "design": self.design,
            "config_hash": self.config_hash,
            "environment": self.environment,
            "dataset": self.dataset,
            "factors": self.factors,
            "notes": list(self.notes),
            "config": self.effective_config,
            "requested_config": self.requested_config,
            "effective_config": self.effective_config,
        }


class Compiler:
    def __init__(self, spec: spec_module.Spec):
        self.spec = spec
        self.rules = self.spec.protocol.get("derived_rules") or []

    # ------------------------------------------------------------- helpers
    def _base(self, which: str = "default") -> dict[str, Any]:
        return self.spec.reference_config(which)

    def _plan(self, index: int, config: dict[str, Any], *, requested: dict[str, Any] | None = None,
              factors: Mapping[str, Any] | None = None, environment: Mapping[str, Any] | None = None,
              dataset: Mapping[str, Any] | None = None, notes: Iterable[str] = ()) -> RunPlan:
        requested = copy.deepcopy(requested or config)
        env = normalize_environment(merge(self.spec.environment, environment or {}))
        data = merge(self.spec.dataset, dataset or {})
        effective, applied = apply_derived_rules(config, self.rules)
        effective, closure = capability_closure(effective)
        applied += closure
        effective = merge(effective, {"environment": env, "dataset": data})
        problems = lab_config.problems(effective)
        if problems:
            raise spec_module.SpecError([
                f"plan {index} is not a valid run config: " + "; ".join(problems[:5])
            ])
        digest = lab_config.digest(effective)
        run_id = f"r-{_slug(self.spec.id)}-{index:03d}-{digest.split(':')[-1][:8]}"
        all_notes = list(notes) + applied
        return RunPlan(
            run_id=run_id, spec_id=self.spec.id, design=self.spec.design,
            config=effective, requested_config=requested, effective_config=effective,
            config_hash=digest, environment=env, dataset=data,
            factors=dict(factors or {}), notes=tuple(all_notes),
        )

    @staticmethod
    def _factor_path(factor: Mapping[str, Any]) -> str:
        return str(factor.get("path") or factor["id"])

    def _applies(self, config: Mapping[str, Any], factor: Mapping[str, Any]) -> bool:
        condition = factor.get("applies_when")
        return not isinstance(condition, Mapping) or _matches(config, condition)

    # ------------------------------------------------------------- designs
    def _single_factor(self) -> list[RunPlan]:
        plans: list[RunPlan] = []
        base = self._base()
        for factor in self.spec.factors:
            path = self._factor_path(factor)
            for level in factor.get("levels") or []:
                requested = copy.deepcopy(base)
                if path.endswith(".impl"):
                    set_impl(requested, path, level)
                else:
                    set_path(requested, path, level)
                if not self._applies(requested, factor):
                    continue
                plans.append(self._plan(len(plans), requested, factors={factor["id"]: level}))
        return plans

    def _adoption(self) -> list[RunPlan]:
        plans: list[RunPlan] = []
        off = self._base("off") if self.spec.reference_off else self._base()
        on = self._base("on") if self.spec.reference_on else off
        for module in self.spec.modules:
            mid = module["id"]
            if module.get("add_baseline") != "R0_only":
                # add from B0: off baseline + module.on
                requested = apply_overrides(off, module.get("on") or {})
                plans.append(self._plan(len(plans), requested, requested=requested,
                                        factors={"module": mid, "baseline": "add_from_B0"},
                                        notes=[f"module {mid} on"]))
            if self.spec.reference_on is not None:
                # remove from R0: on baseline + module.off
                requested = apply_overrides(on, module.get("off") or {})
                plans.append(self._plan(len(plans), requested, requested=requested,
                                        factors={"module": mid, "baseline": "remove_from_R0"},
                                        notes=[f"module {mid} off"]))
        return plans

    def _factorial(self) -> list[RunPlan]:
        factors = self.spec.factors
        if not factors:
            raise spec_module.SpecError(["factorial design requires factors"])
        levels = []
        for factor in factors:
            if isinstance(factor.get("levels"), list):
                levels.append([(factor["id"], level) for level in factor["levels"]])
            else:
                levels.append([(factor["id"], factor.get("low")), (factor["id"], factor.get("high"))])
        plans: list[RunPlan] = []
        base = self._base()
        for combination in itertools.product(*levels):
            requested = copy.deepcopy(base)
            values = {}
            for factor, (_, value) in zip(factors, combination):
                path = self._factor_path(factor)
                if path.endswith(".impl"):
                    set_impl(requested, path, value)
                else:
                    set_path(requested, path, value)
                values[factor["id"]] = value
            plans.append(self._plan(len(plans), requested, factors=values,
                                    notes=["fractional spec compiled as full factorial; generator not implemented"]
                                    if self.spec.design == "fractional_factorial" else ()))
        return plans

    def _fractional(self) -> list[RunPlan]:
        """Half-fraction 2^(k-1): the last factor is the parity of the others."""
        factors = self.spec.factors
        k = len(factors)
        if k < 2:
            raise spec_module.SpecError(["fractional design requires at least 2 factors"])
        fraction = str((self.spec.data.get("generator") or {}).get("fraction") or "")
        if fraction != f"2^({k}-1)":
            raise spec_module.SpecError([
                f"only the 2^({k}-1) half-fraction is implemented; spec asks {fraction or 'unknown'}"
            ])
        base = factors[:-1]
        last = factors[-1]
        values_for = []
        for factor in factors:
            if isinstance(factor.get("levels"), list) and len(factor["levels"]) >= 2:
                values_for.append(list(factor["levels"][:2]))
            else:
                values_for.append([factor.get("low"), factor.get("high")])
        plans: list[RunPlan] = []
        for bits in itertools.product((0, 1), repeat=k - 1):
            chosen = {factor["id"]: values_for[i][bit] for i, (factor, bit) in enumerate(zip(base, bits))}
            chosen[last["id"]] = values_for[-1][sum(bits) % 2]
            requested = copy.deepcopy(self._base())
            for factor in factors:
                path = self._factor_path(factor)
                if path.endswith(".impl"):
                    set_impl(requested, path, chosen[factor["id"]])
                else:
                    set_path(requested, path, chosen[factor["id"]])
            plans.append(self._plan(len(plans), requested, factors=chosen))
        return plans

    def _environment_grid(self) -> list[RunPlan]:
        grid = self.spec.data.get("grid") or {}
        candidates = self.spec.data.get("candidates") or [{"id": "default", "config": "default"}]
        llms = grid.get("llm") or [{}]
        scales = grid.get("data_scale") or [{}]
        scenes = grid.get("scene") or [{}]
        plans: list[RunPlan] = []
        for llm, scale, scene, candidate in itertools.product(llms, scales, scenes, candidates):
            which = "on" if str(candidate.get("config", "")).upper().startswith("R0") else "default"
            try:
                base = self._base(which)
            except spec_module.SpecError:
                base = self._base()
            env: dict[str, Any] = {}
            if isinstance(llm, Mapping) and llm.get("model"):
                env = merge(env, {"llm": {"model": llm["model"], "provider": llm.get("provider", "ollama")}})
            if isinstance(scale, Mapping):
                env["data_scale"] = scale.get("id") or scale.get("name")
            if isinstance(scene, Mapping):
                env["scene"] = scene.get("id") or scene.get("name")
            dataset = {}
            if isinstance(scale, Mapping):
                if scale.get("samples"):
                    dataset["samples"] = list(scale["samples"])
                if scale.get("question_limit"):
                    dataset["question_limit"] = int(scale["question_limit"])
            values = {
                "llm": llm.get("id") if isinstance(llm, Mapping) else str(llm),
                "data_scale": scale.get("id") if isinstance(scale, Mapping) else str(scale),
                "scene": scene.get("id") if isinstance(scene, Mapping) else str(scene),
                "candidate": candidate.get("id") if isinstance(candidate, Mapping) else str(candidate),
            }
            plans.append(self._plan(len(plans), base, factors=values, environment=env, dataset=dataset))
        return plans

    # ------------------------------------------------------------- public
    def compile(self) -> list[RunPlan]:
        design = self.spec.design
        if design.startswith("single_factor"):
            if self.spec.modules and design == "single_factor_adoption":
                return self._adoption()
            return self._single_factor()
        if design == "full_factorial":
            return self._factorial()
        if design == "fractional_factorial":
            return self._fractional()
        if design == "environment_grid":
            return self._environment_grid()
        if design == "coupling_analysis":
            raise spec_module.SpecError([
                "coupling_analysis is analysis-only; use memlab.experiments.coupling_cli"
            ])
        raise spec_module.SpecError([f"design {design!r} is not supported by the S5 compiler"])


def compile_spec(spec: spec_module.Spec) -> list[RunPlan]:
    return Compiler(spec).compile()


def write_matrix(plans: Iterable[RunPlan], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [plan.to_dict() for plan in plans]
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
