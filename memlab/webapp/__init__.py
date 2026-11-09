"""Course-facing Web API v2.

Additive to the legacy ``/api/*`` routes: the old UI keeps working, while the new
pages read ``MemoryUnit`` v2, download the unified JSON and run a module config
through the same E2E executor used by experiments.

W1 scope: memory explorer, v2 export, preset validation, single-question runs and
system status. Experiment jobs/queue and the four-tab report page are W2.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from functools import lru_cache
from typing import Any
from urllib.parse import unquote

from memlab import cache as lab_cache
from memlab import config as lab_config
from memlab import export as lab_export
from memlab import manifest as lab_manifest, model
from memlab.e2e import E2EPipeline
from memlab.experiments import compiler
from memlab.experiments import executor as e2e_executor
from memwb import config as legacy_config
from memwb import dataset, export as legacy_export

ROOT = lab_config.ROOT
PRESETS = {
    "B0": ROOT / "configs" / "reference-b0.json",
    "R0": ROOT / "configs" / "reference-r0.json",
    "CHEAP": ROOT / "configs" / "reference-cheap.json",
    "QUALITY": ROOT / "configs" / "reference-quality.json",
}
COURSE_IDS = legacy_config.SPLIT["development"] + legacy_config.SPLIT["test"]
_SHARED_CACHE = lab_cache.ArtifactCache(ROOT / "cache" / "web")
_CONTEXTS: dict[tuple[str, str, bool], Any] = {}
_PIPELINES: dict[tuple[str, str, bool], E2EPipeline] = {}


class WebError(ValueError):
    def __init__(self, message: str, status: int = 400, **details: Any):
        self.status = status
        self.details = details
        super().__init__(message)


def _one(args: Any, name: str, default: Any = None) -> Any:
    value = (args or {}).get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


@lru_cache(maxsize=16)
def _view(sample_id: str):
    return model.from_sample(dataset.store().get(sample_id))


@lru_cache(maxsize=16)
def _summary(sample_id: str) -> dict[str, Any]:
    sample = dataset.store().get(sample_id)
    data = legacy_export.summary(sample)
    try:
        view = _view(sample_id)
        data["v2"] = {
            "memories": len(view.units),
            "relations": len(view.relations),
            "by_kind": dict(Counter(unit.kind for unit in view.units)),
        }
    except Exception as exc:  # memory v2 must not break the legacy summary
        data["v2_error"] = str(exc)
    return data


@lru_cache(maxsize=8)
def _preset(name: str) -> lab_config.RunConfig:
    key = str(name).upper()
    path = PRESETS.get(key)
    if path is None:
        raise WebError(f"unknown preset: {name!r}; available={sorted(PRESETS)}", 404)
    if not path.is_file():
        raise WebError(f"preset file missing: {path}", 404)
    return lab_config.RunConfig.load(path)


def _sample(sample_id: str):
    if not sample_id:
        raise WebError("sample is required", 400)
    try:
        return dataset.store().get(sample_id)
    except KeyError as exc:
        raise WebError(str(exc).strip("'\""), 404) from exc


def _interval(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "start": value.start.isoformat() if value.start else None,
        "end": value.end.isoformat() if value.end else None,
        "precision": value.precision,
    }


def _unit_summary(unit) -> dict[str, Any]:
    structured = unit.structured or {}
    entity = structured.get("entity") or structured.get("speaker") or ""
    turn = unit.evidence[0].turn_id if unit.evidence else structured.get("turn")
    return {
        "memory_id": unit.memory_id,
        "kind": unit.kind,
        "text": unit.text,
        "entity": entity,
        "state": structured.get("state") or "",
        "attribute": structured.get("attribute") or structured.get("slot") or "",
        "t_event": _interval(unit.t_event),
        "t_ingest": _interval(unit.t_ingest),
        "valid_interval": _interval(unit.valid_interval),
        "source_turn": turn,
        "evidence_count": len(unit.evidence),
    }


def _detail(sample_id: str, memory_id: str) -> dict[str, Any]:
    view = _view(sample_id)
    by_id = view.by_id()
    unit = by_id.get(memory_id)
    if unit is None:
        raise WebError(f"unknown memory: {memory_id}", 404)
    turns = {
        str(item.structured.get("turn")): item
        for item in view.units
        if item.kind == "turn" and item.structured.get("turn")
    }
    source_turns = []
    for span in unit.evidence:
        turn = turns.get(span.turn_id)
        source_turns.append({
            "turn_id": span.turn_id,
            "quote": span.quote,
            "start": span.start,
            "end": span.end,
            "text": turn.text if turn else None,
        })
    relations = [
        model.relation_to_dict(relation)
        for relation in view.relations
        if relation.head_id == memory_id or relation.tail_id == memory_id
    ]
    return {
        "sample": sample_id,
        "memory": model.unit_to_dict(unit),
        "summary": _unit_summary(unit),
        "source_turns": source_turns,
        "relations": relations,
    }


def _validate(config_data: dict[str, Any]) -> dict[str, Any]:
    try:
        cfg = lab_config.RunConfig.from_dict(config_data)
    except lab_config.ConfigError as exc:
        return {"valid": False, "runnable": False, "problems": list(exc.problems), "warnings": []}
    problems, warnings = compiler.probe_config(cfg.to_dict())
    return {
        "valid": True,
        "runnable": not problems,
        "problems": list(problems),
        "warnings": list(warnings),
        "config_hash": cfg.config_hash,
        "effective_config": cfg.to_dict(),
        "requested_config": config_data,
    }


def _body_config(body: dict[str, Any]) -> tuple[dict[str, Any], lab_config.RunConfig]:
    if isinstance(body.get("config"), dict):
        data = body["config"]
    else:
        data = _preset(str(body.get("preset") or "B0")).to_dict()
    check = _validate(data)
    if not check["valid"]:
        raise WebError("invalid config", 422, problems=check["problems"])
    if not check["runnable"]:
        raise WebError("config is not runnable", 422, problems=check["problems"], warnings=check["warnings"])
    return data, lab_config.RunConfig.from_dict(data)


def _plan(cfg: lab_config.RunConfig, question_limit: int = 1):
    return compiler.RunPlan(
        run_id=f"web-{time.strftime('%Y%m%d-%H%M%S')}-{cfg.config_hash.split(':')[-1][:8]}",
        spec_id="WEB-W1", design="single_question",
        config=cfg.to_dict(), requested_config=cfg.to_dict(), effective_config=cfg.to_dict(),
        config_hash=cfg.config_hash,
        environment=cfg.get("environment") or {},
        dataset={"samples": [], "question_limit": question_limit},
        factors={},
        runnable=True,
    )


def _context(plan, sample_id: str, offline: bool):
    key = (plan.config_hash, sample_id, bool(offline))
    if key not in _CONTEXTS:
        _CONTEXTS[key] = e2e_executor.build_context(plan, sample_id, offline=offline, cache=_SHARED_CACHE)
        _PIPELINES[key] = E2EPipeline(_CONTEXTS[key])
    return _CONTEXTS[key], _PIPELINES[key]


def _run_module(sample_id: str, question: str, cfg: lab_config.RunConfig,
                offline: bool, k: int, as_of: str | None) -> dict[str, Any]:
    plan = _plan(cfg)
    ctx, pipeline = _context(plan, sample_id, offline)
    suffix = ""
    if as_of and " as of " not in question.lower():
        suffix = f" as of {as_of}"
    result = pipeline.run(question + suffix, k=k)
    store = ctx.store
    units = result.merge.units
    ids = {unit.memory_id for unit in units}
    ids.update(unit.memory_id for unit in result.answer.state.valid)
    relations = [model.relation_to_dict(relation) for relation in store.relations
                 if relation.head_id in ids or relation.tail_id in ids]
    run_id = plan.run_id
    payload = {
        "run_id": run_id,
        "mode": "module",
        "offline": bool(offline),
        "config_hash": cfg.config_hash,
        "preset": cfg.preset,
        "config": cfg.to_dict(),
        "question": question,
        "as_of": as_of,
        "answer": result.answer.as_dict(),
        "state": {
            "valid_ids": [unit.memory_id for unit in result.answer.state.valid],
            "superseded_ids": [unit.memory_id for unit in result.answer.state.superseded],
            "unresolved": list(result.answer.state.unresolved),
            "conflicts": [list(pair) for pair in result.answer.state.conflicts],
            "as_of": result.answer.state.as_of.isoformat() if result.answer.state.as_of else None,
            "explanation": result.answer.state.explanation,
        },
        "candidates": [_unit_summary(unit) for unit in units],
        "candidate_details": [model.unit_to_dict(unit) for unit in units],
        "relations": relations,
        "merge": result.merge.as_dict(),
        "trace": result.trace,
        "tokens": result.tokens,
        "latency_ms": result.latency_ms,
        "model": {
            "llm": getattr(ctx.llm, "effective_model", None) if not offline else "offline-extractive",
            "embedding": getattr(ctx.embedding, "effective_model", None) if not offline else "offline-hash",
            "offline": bool(offline),
        },
    }
    _persist(payload)
    return payload


def _run_legacy(sample_id: str, question: str, cfg: lab_config.RunConfig,
                method: str, k: int, as_of: str | None) -> dict[str, Any]:
    from memlab import runtime

    machine = runtime.Runtime(cfg)
    output = machine.answer(sample_id, question, method=method or None, k=k, as_of=as_of)
    run_id = f"web-{time.strftime('%Y%m%d-%H%M%S')}-{method or cfg.method}"
    payload = {
        "run_id": run_id, "mode": "legacy", "method": method or cfg.method,
        "offline": False, "config_hash": cfg.config_hash, "preset": cfg.preset,
        "config": cfg.to_dict(), "question": question, "as_of": as_of,
        "answer": {
            "answer": output.get("answer"), "citations": output.get("retrieved_turns", []),
            "refused": not bool(output.get("answer")), "conflicts": [],
        },
        "state": {"valid_ids": output.get("valid_memory_ids", [])},
        "candidates": [],
        "candidate_details": [],
        "relations": [],
        "legacy": output,
        "trace": output.get("steps", []),
        "tokens": None,
        "latency_ms": None,
        "model": {"llm": legacy_config.answer_model(), "offline": False},
    }
    return payload


def _persist(payload: dict[str, Any]) -> None:
    try:
        directory = ROOT / "runs" / "web"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{payload['run_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def _run(body: dict[str, Any]) -> dict[str, Any]:
    sample_id = str(body.get("sample") or "")
    _sample(sample_id)
    question = str(body.get("question") or "").strip()
    if not question:
        raise WebError("question is required", 400)
    cfg_data, cfg = _body_config(body)
    k = max(1, min(50, int(body.get("k", 15) or 15)))
    as_of = body.get("as_of") or None
    mode = str(body.get("mode") or "module").lower()
    if mode == "legacy":
        try:
            return _run_legacy(sample_id, question, cfg, str(body.get("method") or cfg.method), k, as_of)
        except Exception as exc:
            raise WebError(f"legacy run failed (is Ollama running?): {type(exc).__name__}: {exc}", 502) from exc
    return _run_module(sample_id, question, cfg, bool(body.get("offline", True)), k, as_of)


def get(path: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    route = path[len("/api/v2"):] if path.startswith("/api/v2") else path

    if route in ("/course", "/samples"):
        ids = COURSE_IDS if route == "/course" else dataset.store().ids()
        items = []
        for sample_id in ids:
            summary = dict(_summary(sample_id))
            summary["role"] = "test" if summary.get("split") == "test" else summary.get("split")
            items.append(summary)
        return {"ids": ids, "samples": items, "count": len(items)}

    if route == "/config/presets":
        presets = []
        for name in PRESETS:
            try:
                cfg = _preset(name)
                check = _validate(cfg.to_dict())
                presets.append({
                    "name": name, "preset": cfg.preset,
                    "description": cfg.get("description"),
                    "config_hash": cfg.config_hash,
                    "runnable": check["runnable"], "problems": check["problems"],
                    "config": cfg.to_dict(),
                })
            except Exception as exc:
                presets.append({"name": name, "error": str(exc)})
        return {"presets": presets}

    if route == "/export/all":
        schema = _one(args, "schema", "2")
        return {
            "schema": "memlab/web-export-bundle@1",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "documents": {sample_id: lab_export.export(_sample(sample_id), schema) for sample_id in COURSE_IDS},
        }

    if route == "/export":
        sample_id = str(_one(args, "sample", ""))
        schema = str(_one(args, "schema", "2"))
        return lab_export.export(_sample(sample_id), schema)

    match = re.fullmatch(r"/memories/([^/]+)", route)
    if match:
        sample_id = str(_one(args, "sample", ""))
        return _detail(sample_id, unquote(match.group(1)))

    if route == "/memories":
        sample_id = str(_one(args, "sample", ""))
        sample = _sample(sample_id)
        view = _view(sample_id)
        kind = str(_one(args, "kind", "") or "")
        state = str(_one(args, "state", "") or "")
        query = str(_one(args, "q", "") or "").strip().lower()
        page = max(1, int(_one(args, "page", 1) or 1))
        size = min(100, max(1, int(_one(args, "page_size", 50) or 50)))
        units = []
        for unit in view.units:
            if kind and unit.kind != kind:
                continue
            summary = _unit_summary(unit)
            if state and summary["state"].upper() != state.upper():
                continue
            haystack = f"{unit.memory_id} {unit.text} {summary['entity']} {unit.structured}".lower()
            if query and query not in haystack:
                continue
            units.append(summary)
        start = (page - 1) * size
        return {
            "sample": sample_id, "split": legacy_config.split_of(sample_id),
            "total": len(units), "page": page, "page_size": size,
            "memories": units[start:start + size],
        }

    if route == "/system":
        return {
            "commit": lab_manifest.git_commit(),
            "dataset": {
                "file": str(legacy_config.DATA_FILE),
                "hash": lab_manifest.dataset_hash(),
                "samples": len(dataset.store().samples),
                "course": COURSE_IDS,
            },
            "model": {
                "llm": legacy_config.answer_model(),
                "embedding": legacy_config.embed_model(),
                "offline_available": True,
                "ollama_url": legacy_config.ollama_url(),
            },
            "web": {"version": "w1", "api": "/api/v2", "legacy_api": "/api"},
            "gaps": [
                "W1: single-question runs; async experiment jobs and report tabs are W2.",
                "Legacy mode needs Ollama; module mode has offline extractive demo.",
                "The teacher-provided dynamic-state annotations are not bundled; state benchmark is project-built.",
            ],
        }

    raise WebError(f"unknown v2 route: {route}", 404)


def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    route = path[len("/api/v2"):] if path.startswith("/api/v2") else path
    if not isinstance(body, dict):
        raise WebError("JSON object expected", 400)
    if route == "/config/validate":
        if isinstance(body.get("config"), dict):
            data = body["config"]
        elif body.get("preset"):
            data = _preset(str(body["preset"])).to_dict()
        else:
            raise WebError("config or preset is required", 400)
        return _validate(data)
    if route == "/runs":
        return _run(body)
    raise WebError(f"unknown v2 route: {route}", 404)
