"""Course-facing Web API v2.

Additive to the legacy ``/api/*`` routes: the old UI keeps working, while the new
pages read ``MemoryUnit`` v2, download the unified JSON and run a module config
through the same E2E executor used by experiments.

W1 scope: memory explorer, v2 export, preset validation, single-question runs and
system status. Experiment jobs/queue and the four-tab report page are W2.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Any
from urllib.parse import unquote

from memlab import cache as lab_cache
from memwb import evaluation
from memlab import registry
from memlab import config as lab_config
from memlab import export as lab_export
from memlab import manifest as lab_manifest, model
from memlab.e2e import E2EPipeline
from memlab.merge import unit_turns as merge_unit_turns
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
HARDWARE = {
    "machine": "MacBook Air M2 (2022)",
    "memory_gb": 8,
    "disk_free_gb": 6,
    "os": "macOS",
    "local_llm_scale": {
        "status": "hardware_blocked",
        "label_zh": "GPU/内存受限",
        "reason": "8GB unified memory and no usable discrete GPU: local 7B/27B/72B scale runs are not executable at experiment scale.",
        "design_retained": True,
        "alternative": "API tier grid (API_T1_cheap / API_T2_mid / API_T3_strong)",
    },
    "cross_encoder": {
        "status": "hardware_limited",
        "label_zh": "正式重排 GPU 受限",
        "reason": "CPU cross-encoder is only viable for small smoke tests, not 36-cell M2/M3 experiments.",
        "alternative": "small-sample CPU rerank or future API rerank adapter",
    },
}
STATUS_LEGEND = {
    "ready": "当前可运行",
    "hardware_blocked": "硬件原因不可执行；设计保留",
    "hardware_limited": "可小样本/回退；正式实验受限",
    "not_implemented": "代码未实现（不是硬件原因）",
    "deferred": "按计划延后（不是硬件原因）",
}
COURSE_IDS = legacy_config.SPLIT["development"] + legacy_config.SPLIT["test"]
_SHARED_CACHE = lab_cache.ArtifactCache(ROOT / "cache" / "web")
_CONTEXTS: dict[tuple[str, str, bool], Any] = {}
_PIPELINES: dict[tuple[str, str, bool], E2EPipeline] = {}
_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.RLock()
_JOBS_EXECUTOR = ThreadPoolExecutor(max_workers=1)
MODULES = [
    {"id": "W", "name": "Write", "label_zh": "写入",
     "question": "原始对话如何变成可追溯、可冲突消解的 Memory？",
     "stages": ["E1.1 实现选型", "E1.2 参数", "E1.3 模块 LLM"]},
    {"id": "S", "name": "Store", "label_zh": "存储",
     "question": "同样的内容如何组织，才能被检索到且不丢状态？",
     "stages": ["E1.1 图表示", "E1.2 图参数", "E1.4 模块内组合"]},
    {"id": "R", "name": "Retrieve", "label_zh": "检索",
     "question": "问题如何变成检索动作：规划、通道与 K？",
     "stages": ["E1.1 规划器", "E1.2 通道/K", "E1.3 规划 LLM"]},
    {"id": "M", "name": "Merge", "label_zh": "合并",
     "question": "多路候选如何融合、重排并控制 token 成本？",
     "stages": ["E1.1 融合/重排", "E1.2 阈值/λ", "E1.4 顺序"],
     "hardware_note": "M2/M3 的真实 cross-encoder 重排在 8GB CPU 上不可做；这是 GPU/内存限制，不是未实现。可小样本回退，或等 API rerank adapter。",
     "hardware_status": "hardware_limited"},
    {"id": "U", "name": "Use", "label_zh": "使用",
     "question": "哪些 Memory 当前有效，最终如何回答与引用？",
     "stages": ["E1.1 状态解析", "E1.1 回答器", "E1.3 回答 LLM"]},
    {"id": "K", "name": "Maintenance", "label_zh": "维护",
     "question": "长期运行如何更新、去重、归档而不丢历史？",
     "stages": ["K 单独执行", "维护指标", "不在单题 E2E 内"],
     "note": "K 维护作用于长期存储，不在单题 Web 运行中执行；其指标见 maintenance 实验。"},
]

AXES = [
    {"id": "schema", "module": "W", "label": "Schema", "label_zh": "记忆结构",
     "path": "schema.impl", "kind": "impl",
     "desc": "flat facts / meta schema：字段、证据与双时间结构"},
    {"id": "write.resolver", "module": "W", "label": "Resolver", "label_zh": "写入冲突策略",
     "path": "write.resolver.impl", "kind": "impl",
     "desc": "append / overwrite / keep_both / mem0_4action"},
    {"id": "write.auditor", "module": "W", "label": "Auditor", "label_zh": "写入审计",
     "path": "write.auditor.impl", "kind": "impl",
     "desc": "none / llm_audit：写入后是否复核冲突"},
    {"id": "graph.repr", "module": "S", "label": "Graph representation", "label_zh": "图表示",
     "path": "graph.repr.impl", "kind": "impl",
     "desc": "state_slot / entity_triple / three_layer / event_sparse：存储图结构"},
    {"id": "planner", "module": "R", "label": "Planner", "label_zh": "查询规划",
     "path": "planner.impl", "kind": "impl",
     "desc": "none / rule_router / dag：是否拆子问题、如何路由"},
    {"id": "retrieval.channels", "module": "R", "label": "Channels", "label_zh": "检索通道",
     "path": "retrieval.channels", "kind": "channels",
     "available": ["dense", "bm25", "graph", "temporal"],
     "desc": "dense 稠密 / bm25 词法 / graph 图 / temporal 时序：多路召回"},
    {"id": "retrieval.k", "module": "R", "label": "Top K", "label_zh": "检索数量 K",
     "path": "retrieval.k", "kind": "number", "min": 1, "max": 50,
     "desc": "每路保留的候选数量（影响召回与成本）"},
    {"id": "fusion", "module": "M", "label": "Fusion", "label_zh": "融合",
     "path": "fusion.impl", "kind": "impl",
     "desc": "rrf / weighted_rrf / linear / query_adaptive_weights"},
    {"id": "rerank", "module": "M", "label": "Rerank", "label_zh": "重排",
     "path": "rerank.impl", "kind": "impl",
     "desc": "none / cross_encoder：语义重排，缺依赖时回退",
     "status": "hardware_limited",
     "status_note": "正式 M2/M3 需要 GPU；CPU 只能小样本/回退，不是未实现。",
     "option_status": {"cross_encoder": {
         "status": "hardware_limited",
         "label_zh": "GPU 受限（正式）",
         "note": "8GB CPU 只适合小样本；正式重排结论暂不可得"}}},
    {"id": "post.filter", "module": "M", "label": "Filter", "label_zh": "后过滤",
     "path": "post.filter.impl", "kind": "impl",
     "desc": "none / threshold：按相关性/时效过滤"},
    {"id": "post.mmr", "module": "M", "label": "MMR", "label_zh": "多样性选择",
     "path": "post.mmr.impl", "kind": "impl",
     "desc": "none / mmr：在相关性与多样性间取舍"},
    {"id": "post.decay", "module": "M", "label": "Time decay", "label_zh": "时间衰减",
     "path": "post.decay.impl", "kind": "impl",
     "desc": "none / time_decay：按时间降低旧候选权重"},
    {"id": "post.compress", "module": "M", "label": "Compress", "label_zh": "压缩",
     "path": "post.compress.impl", "kind": "impl",
     "desc": "none / extractive：控制进入回答的 token 预算"},
    {"id": "logic.state_resolver", "module": "U", "label": "State resolver", "label_zh": "状态解析",
     "path": "logic.state_resolver", "kind": "string",
     "desc": "none / offline_slot / query_llm / bitemporal：判断当前有效 Memory"},
    {"id": "answer", "module": "U", "label": "Answerer", "label_zh": "回答器",
     "path": "answer.impl", "kind": "impl",
     "desc": "direct / valid_history / evidence_chain / citation_required"},
]

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


def _select_questions(sample_id: str, limit: int, seed: int) -> list[tuple[int, dict[str, Any]]]:
    sample = _sample(sample_id)
    eligible = evaluation.answerable(sample.get("qa", []))
    groups: dict[int, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, qa in eligible:
        groups[qa.get("category")].append((index, qa))
    rng = random.Random(seed)
    for values in groups.values():
        rng.shuffle(values)
    chosen: list[tuple[int, dict[str, Any]]] = []
    categories = sorted(groups)
    while len(chosen) < min(limit, len(eligible)):
        progressed = False
        for category in categories:
            if groups[category] and len(chosen) < min(limit, len(eligible)):
                chosen.append(groups[category].pop(0))
                progressed = True
        if not progressed:
            break
    return sorted(chosen)


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(round(0.95 * (len(values) - 1))))]


def _run_batch(sample_id: str, cfg: lab_config.RunConfig, offline: bool,
               limit: int, seed: int) -> dict[str, Any]:
    plan = _plan(cfg, question_limit=limit)
    ctx, pipeline = _context(plan, sample_id, offline)
    questions = _select_questions(sample_id, limit, seed)
    rows: list[dict[str, Any]] = []
    f1s: list[float] = []
    recalls: list[float] = []
    latencies: list[float] = []
    by_category: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "f1": [], "recall": []})
    stages: dict[str, list[float]] = defaultdict(list)
    for index, qa in questions:
        started = time.perf_counter()
        gold_turns = evaluation.evidence_turns(qa)
        result = pipeline.run(qa.get("question", ""), k=15, gold_turns=gold_turns)
        latency = round((time.perf_counter() - started) * 1000, 3)
        prediction = result.answer.answer
        f1 = evaluation.answer_f1(prediction, qa.get("answer"), qa.get("category"))
        turns: set[str] = set()
        for unit in result.merge.units:
            turns |= merge_unit_turns(unit)
        rec = evaluation.recall(gold_turns, sorted(turns))
        category = str(qa.get("category") or "unknown")
        row = {
            "qid": f"{sample_id}:{index}", "category": category,
            "question": qa.get("question"), "gold": qa.get("answer"),
            "prediction": prediction, "answer_f1": f1, "evidence_recall": rec,
            "tokens": result.tokens, "latency_ms": latency,
            "candidates": len(result.merge.units), "refused": int(result.answer.refused),
        }
        rows.append(row)
        if f1 is not None:
            f1s.append(float(f1))
            by_category[category]["f1"].append(float(f1))
        if rec is not None:
            recalls.append(float(rec))
            by_category[category]["recall"].append(float(rec))
        latencies.append(latency)
        by_category[category]["n"] += 1
        for step in result.trace:
            if step.get("ms") is not None:
                stages[str(step.get("stage") or "unknown")].append(float(step["ms"]))
    metrics = {
        "answer_f1": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "evidence_recall": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "state_accuracy": None,
        "tokens": round(sum(float(r["tokens"] or 0) for r in rows) / len(rows), 2) if rows else None,
        "p95_latency_ms": _p95(latencies),
        "error_rate": round(sum(1 for r in rows if r["refused"] and not r["prediction"]) / len(rows), 4) if rows else 0.0,
        "questions": len(rows),
    }
    categories = []
    for name, values in sorted(by_category.items()):
        categories.append({
            "category": name, "n": values["n"],
            "answer_f1": round(sum(values["f1"]) / len(values["f1"]), 4) if values["f1"] else None,
            "evidence_recall": round(sum(values["recall"]) / len(values["recall"]), 4) if values["recall"] else None,
        })
    run_id = (f"batch-{time.strftime('%Y%m%d-%H%M%S')}-"
              f"{cfg.config_hash.split(':')[-1][:8]}-{sample_id}-s{seed}")
    payload = {
        "kind": "batch", "run_id": run_id, "sample": sample_id, "preset": cfg.preset,
        "config_hash": cfg.config_hash, "offline": bool(offline), "seed": seed,
        "questions": len(rows), "metrics": metrics, "rows": rows,
        "by_category": categories,
        "config": cfg.to_dict(),
        "stage_waterfall": [{"stage": k, "ms": round(sum(v) / len(v), 3)} for k, v in sorted(stages.items())],
        "model": {"llm": "offline-extractive" if offline else getattr(ctx.llm, "effective_model", None),
                  "embedding": "offline-hash" if offline else getattr(ctx.embedding, "effective_model", None),
                  "offline": bool(offline)},
        "trace": [],
    }
    _persist(payload)
    return payload


def _run(body: dict[str, Any]) -> dict[str, Any]:
    sample_id = str(body.get("sample") or "")
    _sample(sample_id)
    cfg_data, cfg = _body_config(body)
    if body.get("batch"):
        limit = max(1, min(50, int(body.get("questions", 10) or 10)))
        seed = int(body.get("seed", 13) or 13)
        return _run_batch(sample_id, cfg, bool(body.get("offline", True)), limit, seed)
    question = str(body.get("question") or "").strip()
    if not question:
        raise WebError("question is required", 400)
    k = max(1, min(50, int(body.get("k", 15) or 15)))
    as_of = body.get("as_of") or None
    mode = str(body.get("mode") or "module").lower()
    if mode == "legacy":
        try:
            return _run_legacy(sample_id, question, cfg, str(body.get("method") or cfg.method), k, as_of)
        except Exception as exc:
            raise WebError(f"legacy run failed (is Ollama running?): {type(exc).__name__}: {exc}", 502) from exc
    return _run_module(sample_id, question, cfg, bool(body.get("offline", True)), k, as_of)


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def axes() -> dict[str, Any]:
    impls = registry.list_implementations()
    out = []
    for axis in AXES:
        names = axis.get("available") or impls.get(axis["id"], [])
        if axis.get("kind") not in ("number", "channels") and not names:
            continue
        out.append({**axis, "available": names, "status": axis.get("status", "ready")})
    modules = []
    for module in MODULES:
        modules.append({**module, "axes": [axis for axis in out if axis.get("module") == module["id"]]})
    return {"modules": modules, "axes": out, "count": len(out),
            "hardware": HARDWARE, "status_legend": STATUS_LEGEND}


def _job_submit(body: dict[str, Any]) -> dict[str, Any]:
    job_id = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{len(_JOBS) + 1:03d}"
    with _JOBS_LOCK:
        _JOBS[job_id] = {"job_id": job_id, "status": "queued", "created_at": datetime.now().isoformat(timespec="seconds"),
                         "updated_at": datetime.now().isoformat(timespec="seconds"), "body": body, "result": None,
                         "error": None, "cancel": False}
    _JOBS_EXECUTOR.submit(_job_work, job_id, body)
    return _job_get(job_id)


def _job_work(job_id: str, body: dict[str, Any]) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job or job.get("cancel"):
            return
        job["status"] = "running"
        job["updated_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        result = _run(body)
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "done", "result": result, "updated_at": datetime.now().isoformat(timespec="seconds")})
    except Exception as exc:  # noqa: BLE001 - job boundary must report, not kill the queue
        with _JOBS_LOCK:
            _JOBS[job_id].update({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                                  "updated_at": datetime.now().isoformat(timespec="seconds")})


def _job_get(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise WebError(f"unknown job: {job_id}", 404)
        data = {key: value for key, value in job.items() if key != "body"}
        return data


def _job_cancel(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            raise WebError(f"unknown job: {job_id}", 404)
        job["cancel"] = True
        if job["status"] == "queued":
            job["status"] = "cancelled"
        job["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return _job_get(job_id)


def _safe_id(value: str) -> str:
    value = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
        raise WebError("invalid experiment id", 400)
    return value


def _report_dir() -> Any:
    return ROOT / "reports" / "experiments"


def _archive_report_dir() -> Any:
    return ROOT / "eval" / "archive" / "experiments"


def _load_runs(run_ids: list[str]) -> list[dict[str, Any]]:
    runs = []
    for run_id in run_ids:
        path = ROOT / "runs" / "web" / f"{_safe_id(run_id)}.json"
        if not path.is_file():
            raise WebError(f"unknown web run: {run_id}", 404)
        runs.append(json.loads(path.read_text(encoding="utf-8")))
    return runs


def _run_metrics(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("kind") == "batch":
        return dict(run.get("metrics") or {})
    return {
        "answer_f1": None, "evidence_recall": None, "state_accuracy": None,
        "tokens": run.get("tokens"), "p95_latency_ms": run.get("latency_ms"),
        "error_rate": 0.0, "questions": 1,
    }


def _derive_conclusion(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    b, c = _run_metrics(baseline), _run_metrics(candidate)
    n = min(int(c.get("questions") or 1), int(b.get("questions") or 1))
    f1b, f1c = b.get("answer_f1"), c.get("answer_f1")
    rb, rc = b.get("evidence_recall"), c.get("evidence_recall")
    base = {
        "status": "inconclusive", "claims": [], "conditions": [],
        "limitations": [], "next_actions": [],
    }
    if baseline.get("kind") != "batch" or candidate.get("kind") != "batch":
        base["claims"] = ["Single-question Web smoke; no statistical conclusion."]
        base["limitations"] = ["Only one question; no F1/Recall or CI."]
        base["next_actions"] = ["Run a fixed multi-question batch (W2b) and rebuild the report."]
        return base
    if n < 10:
        base["claims"] = [f"Only {n} questions; too small for a comparison claim."]
        base["limitations"] = ["Small sample; no CI."]
        base["next_actions"] = ["Increase to at least 20 questions per config."]
        return base
    if f1b is None or f1c is None:
        base["claims"] = ["F1 unavailable (gold-free or empty answers)."]
        base["limitations"] = ["Cannot compare quality without gold answers."]
        return base
    df1 = round(float(f1c) - float(f1b), 4)
    drec = None if rb is None or rc is None else round(float(rc) - float(rb), 4)
    if df1 > 0.02 and (drec is None or drec >= -0.02):
        status = "supported"
        claims = [f"F1 +{df1:.4f} over baseline on {n} questions" + (f"; Recall {drec:+.4f}" if drec is not None else "")]
    elif df1 < -0.02:
        status = "not_supported"
        claims = [f"Candidate F1 {df1:+.4f} vs baseline on {n} questions"]
    else:
        status = "inconclusive"
        claims = [f"F1 delta {df1:+.4f} is within the ±0.02 descriptive band"]
    return {
        "status": status,
        "claims": claims,
        "conditions": ["Same fixed question set, seed and provider for both runs.",
                       "Offline extractive runs are not LLM-quality claims."],
        "limitations": ["Descriptive comparison; no bootstrap CI or significance test yet."],
        "next_actions": ["Repeat with 2–3 seeds and add paired bootstrap CI (W3)."],
    }


def _build_report(experiment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    run_ids = body.get("run_ids") or []
    if not isinstance(run_ids, list) or len(run_ids) < 2:
        raise WebError("run_ids must contain at least a baseline and a candidate", 422)
    runs = _load_runs([str(r) for r in run_ids])
    baseline, candidate = runs[0], runs[-1]
    bmetrics, cmetrics = _run_metrics(baseline), _run_metrics(candidate)
    comparisons = []
    for key in ("answer_f1", "evidence_recall", "tokens", "p95_latency_ms"):
        b, c = bmetrics.get(key), cmetrics.get(key)
        delta = None if b is None or c is None else round(float(c) - float(b), 4)
        comparisons.append({"baseline": baseline.get("run_id"), "candidate": candidate.get("run_id"),
                            "metric": key, "baseline_value": b, "candidate_value": c,
                            "delta": delta, "paired": False, "significant": False})
    if candidate.get("kind") == "batch":
        split = legacy_config.split_of(str(candidate.get("sample")))
        dataset = {"split": split, "samples": [candidate.get("sample")],
                   "questions": candidate.get("questions"), "seeds": [candidate.get("seed")],
                   "test_only": split == "test"}
        run_rows = [{"run_id": r.get("run_id"), "sample": r.get("sample"), "questions": r.get("questions"),
                     "metrics": _run_metrics(r), "config_hash": r.get("config_hash")} for r in runs]
        analysis = {"main_effects": [], "interactions": [], "pareto": [],
                    "by_category": candidate.get("by_category") or [],
                    "stage_waterfall": candidate.get("stage_waterfall") or [],
                    "failure_breakdown": []}
    else:
        dataset = {"split": "single_question", "samples": [candidate.get("question")],
                   "questions": 1, "seeds": [], "test_only": False}
        run_rows = [{"run_id": r.get("run_id"), "question": r.get("question"),
                     "config_hash": r.get("config_hash"), "tokens": r.get("tokens"),
                     "latency_ms": r.get("latency_ms"), "candidates": len(r.get("candidates") or []),
                     "answer": (r.get("answer") or {}).get("answer")} for r in runs]
        stages: dict[str, float] = {}
        for step in candidate.get("trace") or []:
            stage = str(step.get("stage") or "unknown")
            stages[stage] = round(stages.get(stage, 0.0) + float(step.get("ms") or 0.0), 3)
        analysis = {"main_effects": [], "interactions": [], "pareto": [],
                    "by_category": [], "stage_waterfall": [{"stage": k, "ms": v} for k, v in stages.items()],
                    "failure_breakdown": []}
    conclusion = body.get("conclusion") if isinstance(body.get("conclusion"), dict) else _derive_conclusion(baseline, candidate)
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": _safe_id(experiment_id),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "manifest": {"git_commit": lab_manifest.git_commit(), "config_hash": candidate.get("config_hash"),
                     "model": candidate.get("model"), "offline": candidate.get("offline")},
        "dataset": dataset,
        "results": {"runs": run_rows, "metrics": cmetrics},
        "comparisons": comparisons,
        "analysis": analysis,
        "conclusion": conclusion,
        "web": {"route": f"#/experiments/{_safe_id(experiment_id)}", "published": True},
    }
    directory = _report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{_safe_id(experiment_id)}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _report_list() -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for directory in (_report_dir(), _archive_report_dir()):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                experiment_id = data.get("experiment_id", path.stem)
                items[experiment_id] = {"experiment_id": experiment_id,
                                        "created_at": data.get("created_at"),
                                        "status": (data.get("conclusion") or {}).get("status"),
                                        "schema": data.get("schema")}
            except (OSError, json.JSONDecodeError):
                continue
    ordered = sorted(items.values(), key=lambda item: item.get("created_at") or "", reverse=True)
    return {"experiments": ordered, "count": len(ordered)}


def _report_get(experiment_id: str) -> dict[str, Any]:
    name = f"{_safe_id(experiment_id)}.json"
    for path in (_report_dir() / name, _archive_report_dir() / name):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise WebError(f"unknown experiment report: {experiment_id}", 404)


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

    if route == "/config/axes":
        return axes()

    if route == "/experiments":
        return _report_list()

    match = re.fullmatch(r"/jobs/([^/]+)", route)
    if match:
        return _job_get(unquote(match.group(1)))

    match = re.fullmatch(r"/experiments/([^/]+)/report", route)
    if match:
        return _report_get(unquote(match.group(1)))

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

    if route == "/evaluation":
        path = ROOT / "eval" / "results.json"
        if not path.is_file():
            return {"available": False, "reason": "eval/results.json not found"}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"available": True, "source": "eval/results.json", "reports": _report_list()["experiments"],
                "hardware": HARDWARE, **data}

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
            "hardware": HARDWARE,
            "gaps": [
                "本地 7B/27B/72B 规模实验：硬件受限（8GB 内存/无独显），设计保留但当前不可执行；用 API 档位替代。",
                "M2/M3 真实 cross-encoder 重排：CPU 只适合小样本；这是硬件限制，不是未实现。",
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
    if route == "/jobs":
        return _job_submit(body)
    match = re.fullmatch(r"/jobs/([^/]+)/cancel", route)
    if match:
        return _job_cancel(unquote(match.group(1)))
    match = re.fullmatch(r"/experiments/([^/]+)/report", route)
    if match:
        return _build_report(unquote(match.group(1)), body)
    raise WebError(f"unknown v2 route: {route}", 404)
