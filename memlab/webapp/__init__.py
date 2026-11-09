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
import socket
import threading
import time
import urllib.error
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
CATEGORY_LABELS = {
    1: "多跳",
    2: "时间",
    3: "常识推断",
    4: "单跳",
    5: "对抗",
}
MODEL_UNAVAILABLE = {
    "code": "model_unavailable",
    "message": "本地模型不可用：请勾选“离线演示”，或启动 Ollama / 配置 API。",
    "hint": "offline=true 或 OLLAMA_URL/API provider",
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


class ModelUnavailableError(WebError):
    """Friendly 502 for a missing local model / unreachable provider."""

    code = "model_unavailable"

    def __init__(self, cause: BaseException | None = None):
        self.cause = cause
        super().__init__(MODEL_UNAVAILABLE["message"], 502)

    def as_payload(self) -> dict[str, Any]:
        return dict(MODEL_UNAVAILABLE)


def _is_model_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, (urllib.error.URLError, ConnectionRefusedError, TimeoutError, socket.timeout)):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (ConnectionRefusedError, TimeoutError, socket.timeout))


def _model_unavailable_error(exc: BaseException) -> ModelUnavailableError:
    return ModelUnavailableError(exc)


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
    event = structured.get("event") or ""
    display_kind = "event" if unit.kind == "fact" and event else unit.kind
    return {
        "memory_id": unit.memory_id,
        "kind": unit.kind,
        "display_kind": display_kind,
        "text": unit.text,
        "entity": entity,
        "state": structured.get("state") or "",
        "attribute": structured.get("attribute") or structured.get("slot") or "",
        "value": structured.get("value") or "",
        "event": event,
        "time_expression": structured.get("time_expression") or "",
        "resolved_date": structured.get("resolved_date") or "",
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
        "why_invalid": "后续会话（关系未接入）" if _unit_summary(unit)["state"] == "HISTORICAL" else None,
    }


def _graph(sample_id: str, limit: int = 120) -> dict[str, Any]:
    """Small, deterministic relation graph for the memory page.

    Facts (and event-bearing facts) are selected first because they are the
    structured memory users need to see; turns are only added as relation
    neighbours.  The UI renders this as SVG without a JS graph library.
    """
    view = _view(sample_id)
    limit = max(10, min(240, int(limit)))
    facts = [unit for unit in view.units if unit.kind == "fact"]
    selected = facts[:limit]
    ids = {unit.memory_id for unit in selected}
    # Add one-hop neighbours (often turns) up to the limit.
    for relation in view.relations:
        if len(selected) >= limit:
            break
        if relation.head_id in ids or relation.tail_id in ids:
            for candidate in (relation.head_id, relation.tail_id):
                if candidate not in ids and len(selected) < limit:
                    unit = view.by_id().get(candidate)
                    if unit is not None:
                        selected.append(unit)
                        ids.add(candidate)
    nodes = []
    for unit in selected:
        summary = _unit_summary(unit)
        label = (f"{summary['entity']} · {summary['attribute']} = {summary['value']}"
                 if summary["kind"] == "fact" and summary["attribute"] else
                 (summary["event"] or summary["text"])[:80])
        nodes.append({
            "id": unit.memory_id,
            "label": label,
            "kind": summary["display_kind"],
            "state": summary["state"],
            "entity": summary["entity"],
            "t_event": summary["t_event"],
        })
    edges = []
    for relation in view.relations:
        if relation.head_id in ids and relation.tail_id in ids:
            edges.append({
                "id": relation.relation_id,
                "source": relation.head_id,
                "target": relation.tail_id,
                "type": relation.type,
                "reason": str((relation.provenance or {}).get("reason", ""))[:200],
            })
    return {
        "sample": sample_id,
        "nodes": nodes,
        "edges": edges,
        "total_units": len(view.units),
        "total_relations": len(view.relations),
        "truncated": len(nodes) >= limit,
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
    graph_index = ctx.store.ensure_graph(cfg.impl("graph.repr") or "state_slot")
    payload = {
        "run_id": run_id,
        "graph": graph_index.stats(),
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
        "citation_details": [
            {"id": cid, "turn": (store_unit.evidence[0].turn_id if store_unit.evidence else None),
             "text": store_unit.text, "entity": (store_unit.structured or {}).get("entity") or (store_unit.structured or {}).get("speaker") or ""}
            for cid in result.answer.citations
            for store_unit in [({u.memory_id: u for u in store.units}).get(cid)]
            if store_unit is not None
        ],
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


def _category_label(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return f"category {value}" if value not in (None, "") else "category unknown"
    return CATEGORY_LABELS.get(number, f"category {number}")


def _question_items(sample_id: str, category: str = "", limit: int = 50,
                    seed: int | str | None = None) -> dict[str, Any]:
    """LoCoMo QA catalogue for the experiment workbench.

    Reuses the same ``data/locomo10.json`` store as the legacy ``/api/questions``
    route.  ``index`` is the original QA index, so ``qid`` stays stable across
    category filters, limits and shuffles.
    """
    sample = _sample(sample_id)
    wanted = str(category or "").strip()
    items: list[dict[str, Any]] = []
    for index, qa in enumerate(sample.get("qa", [])):
        if not qa.get("question"):
            continue
        raw_category = qa.get("category")
        if wanted and str(raw_category) != wanted:
            continue
        items.append({
            "qid": f"{sample_id}-q{index}",
            "index": index,
            "question": qa.get("question"),
            "answer": qa.get("answer"),
            "category": raw_category,
            "category_label": _category_label(raw_category),
            "evidence": list(qa.get("evidence") or []),
        })
    total = len(items)
    if seed not in (None, ""):
        try:
            random.Random(int(seed)).shuffle(items)
        except (TypeError, ValueError):
            random.Random(str(seed)).shuffle(items)
    size = max(1, min(500, int(limit if limit not in (None, "") else 50)))
    questions = items[:size]
    return {
        "sample": sample_id,
        "split": legacy_config.split_of(sample_id),
        "category": wanted or None,
        "seed": seed if seed not in (None, "") else None,
        "total": total,
        "count": len(questions),
        "questions": questions,
    }


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
        "graph": ctx.store.ensure_graph(cfg.impl("graph.repr") or "state_slot").stats(),
    }
    _persist(payload)
    return payload


def _run(body: dict[str, Any]) -> dict[str, Any]:
    """Run boundary: translate network/model failures into a friendly 502."""
    try:
        return _run_impl(body)
    except (ModelUnavailableError, WebError):
        raise
    except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, socket.timeout) as exc:
        raise _model_unavailable_error(exc) from exc


def _run_impl(body: dict[str, Any]) -> dict[str, Any]:
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
            if _is_model_unavailable(exc):
                raise _model_unavailable_error(exc) from exc
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
    except ModelUnavailableError as exc:
        detail = exc.as_payload()
        with _JOBS_LOCK:
            _JOBS[job_id].update({
                "status": "error", "error": detail["message"],
                "error_code": detail["code"], "error_detail": detail,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            })
    except Exception as exc:  # noqa: BLE001 - job boundary must report, not kill the queue
        detail = _model_unavailable_error(exc).as_payload() if _is_model_unavailable(exc) else None
        with _JOBS_LOCK:
            update = {
                "status": "error",
                "error": (detail["message"] if detail else f"{type(exc).__name__}: {exc}"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            if detail is not None:
                update.update({"error_code": detail["code"], "error_detail": detail})
            _JOBS[job_id].update(update)


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


def _run_errors(run: dict[str, Any]) -> int:
    if run.get("kind") == "batch":
        errors = 0
        for row in run.get("rows") or []:
            if row.get("error"):
                errors += 1
            elif row.get("refused") and not str(row.get("prediction") or "").strip():
                errors += 1
        return errors
    answer = run.get("answer") or {}
    return 1 if answer.get("refused") else 0


def _report_metrics(run: dict[str, Any]) -> dict[str, Any]:
    """Normalise single-question and batch runs to the same metric keys."""
    metrics = dict(run.get("metrics") or {})
    if run.get("kind") != "batch":
        answer = run.get("answer") or {}
        metrics.setdefault("answer_f1", None)
        metrics.setdefault("evidence_recall", None)
        metrics.setdefault("state_accuracy", None)
        metrics["tokens"] = run.get("tokens", metrics.get("tokens"))
        metrics["p95_latency_ms"] = run.get("latency_ms", metrics.get("p95_latency_ms"))
        metrics["error_rate"] = 1.0 if answer.get("refused") else 0.0
        metrics["questions"] = 1
    metrics["errors"] = _run_errors(run)
    return metrics


def _row_index(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if run.get("kind") != "batch":
        return {}
    return {str(row.get("qid")): row for row in run.get("rows") or [] if row.get("qid") is not None}


def _paired_values(baseline: dict[str, Any], candidate: dict[str, Any],
                   key: str) -> list[tuple[float, float]]:
    bindex, cindex = _row_index(baseline), _row_index(candidate)
    pairs: list[tuple[float, float]] = []
    for qid in sorted(set(bindex) & set(cindex)):
        bvalue, cvalue = bindex[qid].get(key), cindex[qid].get(key)
        if bvalue is None or cvalue is None:
            continue
        pairs.append((float(bvalue), float(cvalue)))
    return pairs


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _comparison(baseline: dict[str, Any], candidate: dict[str, Any], key: str,
                bmetrics: dict[str, Any], cmetrics: dict[str, Any],
                *, pair: bool = True) -> dict[str, Any]:
    pairs = _paired_values(baseline, candidate, key) if pair else []
    paired = bool(pairs)
    if pairs:
        bvalue = round(_mean([pair[0] for pair in pairs]), 4)
        cvalue = round(_mean([pair[1] for pair in pairs]), 4)
        delta = round(cvalue - bvalue, 4)
        count = len(pairs)
    else:
        bvalue, cvalue = bmetrics.get(key), cmetrics.get(key)
        if bvalue is None or cvalue is None:
            bvalue, cvalue, delta = bvalue, cvalue, None
        else:
            bvalue, cvalue = round(float(bvalue), 4), round(float(cvalue), 4)
            delta = round(cvalue - bvalue, 4)
        count = 0
    return {
        "baseline": baseline.get("run_id"),
        "candidate": candidate.get("run_id"),
        "metric": key,
        "baseline_value": bvalue,
        "candidate_value": cvalue,
        "delta": delta,
        "ci95": None,
        "paired": paired,
        "pairs": count,
        "significant": None,
        "note": ("Descriptive candidate - baseline; paired by qid; no bootstrap CI."
                 if paired else "Descriptive candidate - baseline; run-level (no per-qid pair)."),
    }


def _report_by_category(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    bindex, cindex = _row_index(baseline), _row_index(candidate)
    if not bindex or not cindex:
        return list(candidate.get("by_category") or [])
    categories = sorted({str(row.get("category")) for row in bindex.values()
                         if row.get("category") is not None})
    rows: list[dict[str, Any]] = []
    for category in categories:
        qids = sorted(qid for qid in set(bindex) & set(cindex)
                      if str(bindex[qid].get("category")) == category)
        if not qids:
            continue
        entry: dict[str, Any] = {
            "category": category,
            "category_label": _category_label(category),
            "n": len(qids),
        }
        for side, index in (("baseline", bindex), ("candidate", cindex)):
            entry[side] = {}
            for metric in ("answer_f1", "evidence_recall", "tokens"):
                values = [float(index[qid][metric]) for qid in qids
                          if index[qid].get(metric) is not None]
                entry[side][metric] = round(_mean(values), 4) if values else None
        entry["delta"] = {
            metric: (None if entry["baseline"].get(metric) is None
                     or entry["candidate"].get(metric) is None
                     else round(entry["candidate"][metric] - entry["baseline"][metric], 4))
            for metric in ("answer_f1", "evidence_recall", "tokens")
        }
        rows.append(entry)
    return rows


def _stage_totals(run: dict[str, Any]) -> dict[str, float]:
    totals: dict[str, float] = {}
    waterfall = run.get("stage_waterfall")
    if waterfall:
        for item in waterfall:
            stage = str(item.get("stage") or "unknown")
            totals[stage] = round(totals.get(stage, 0.0) + float(item.get("ms") or 0.0), 3)
        return totals
    for step in run.get("trace") or []:
        if step.get("ms") is None:
            continue
        stage = str(step.get("stage") or "unknown")
        totals[stage] = round(totals.get(stage, 0.0) + float(step["ms"]), 3)
    return totals


def _report_stage_waterfall(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    btotals, ctotals = _stage_totals(baseline), _stage_totals(candidate)
    if not btotals and not ctotals:
        return []
    rows = []
    for stage in sorted(set(btotals) | set(ctotals)):
        bvalue, cvalue = btotals.get(stage), ctotals.get(stage)
        delta = None if bvalue is None or cvalue is None else round(cvalue - bvalue, 3)
        rows.append({"stage": stage, "baseline_ms": bvalue, "candidate_ms": cvalue,
                     "ms": cvalue, "delta_ms": delta})
    return rows


def _report_conclusion(baseline: dict[str, Any], candidate: dict[str, Any],
                       comparisons: list[dict[str, Any]],
                       bmetrics: dict[str, Any], cmetrics: dict[str, Any]) -> dict[str, Any]:
    f1 = next((item for item in comparisons if item.get("metric") == "answer_f1"), {})
    delta = f1.get("delta")
    pairs = int(f1.get("pairs") or 0)
    n = pairs or min(int(bmetrics.get("questions") or 1), int(cmetrics.get("questions") or 1))
    limitations = [
        "single-question/batch; no bootstrap CI; offline/online labeled.",
        "No paired bootstrap interval is computed, so the status remains descriptive.",
        "Offline extractive runs are not LLM-quality claims.",
        "Only the two supplied runs are compared; no seed or provider sweep.",
    ]
    conclusion: dict[str, Any] = {
        "status": "inconclusive",
        "direction": "flat",
        "f1_delta": delta,
        "paired_questions": pairs,
        "ci95": None,
        "claims": [],
        "conditions": [
            "Same question set/qids and the same seed are required for a paired comparison.",
            "Candidate and baseline are read from the persisted runs/web JSON; nothing is re-run.",
        ],
        "limitations": limitations,
        "next_actions": [
            "Run at least 10 paired questions (20+ recommended) per configuration.",
            "Repeat with 2–3 seeds and add a paired bootstrap CI before a causal claim.",
        ],
    }
    if n < 10:
        conclusion["claims"] = [f"Only {n} paired question(s) (<10); no comparison claim."]
        conclusion["status_reason"] = "sample_too_small"
        return conclusion
    if delta is None:
        conclusion["claims"] = ["answer_f1 delta unavailable (gold-free run or no matched qids)."]
        conclusion["status_reason"] = "delta_unavailable"
        return conclusion
    delta = float(delta)
    if abs(delta) < 0.02:
        conclusion["claims"] = [f"answer_f1 delta {delta:+.4f} is within the ±0.02 descriptive band."]
        conclusion["status_reason"] = "delta_below_threshold"
        return conclusion
    direction = "candidate_better" if delta > 0 else "candidate_worse"
    conclusion.update({
        "status": "partial",
        "direction": direction,
        "status_reason": "no_bootstrap_ci",
        "claims": [
            f"answer_f1 delta {delta:+.4f} on {n} paired questions; direction={direction}; "
            "no bootstrap CI, so status=partial."
        ],
    })
    return conclusion


def _unique_report_path(experiment_id: str) -> tuple[str, Any]:
    directory = _report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{experiment_id}.json"
    if not path.exists():
        return experiment_id, path
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report_id = f"{experiment_id}-{stamp}"
    path = directory / f"{report_id}.json"
    counter = 2
    while path.exists():
        report_id = f"{experiment_id}-{stamp}-{counter}"
        path = directory / f"{report_id}.json"
        counter += 1
    return report_id, path


def _dataset_from_runs(baseline: dict[str, Any], candidate: dict[str, Any],
                       bmetrics: dict[str, Any], cmetrics: dict[str, Any]) -> dict[str, Any]:
    samples = sorted({str(run.get("sample")) for run in (baseline, candidate) if run.get("sample")})
    splits = {legacy_config.split_of(sample) for sample in samples}
    seeds = sorted({run.get("seed") for run in (baseline, candidate)
                    if run.get("seed") is not None})
    is_batch = baseline.get("kind") == "batch" and candidate.get("kind") == "batch"
    return {
        "split": next(iter(splits)) if len(splits) == 1 else ("mixed" if splits else "single_question"),
        "mode": "batch" if is_batch else "single_question",
        "samples": samples,
        "questions": min(int(bmetrics.get("questions") or 1), int(cmetrics.get("questions") or 1)),
        "questions_per_run": {"baseline": bmetrics.get("questions"),
                              "candidate": cmetrics.get("questions")},
        "seeds": seeds,
        "test_only": bool(samples) and all(split == "test" for split in splits),
    }


def _report_from_runs(body: dict[str, Any]) -> dict[str, Any]:
    baseline_id = body.get("baseline_run_id")
    candidate_id = body.get("candidate_run_id")
    run_ids = body.get("run_ids")
    if (not baseline_id or not candidate_id) and isinstance(run_ids, list) and len(run_ids) >= 2:
        baseline_id, candidate_id = run_ids[0], run_ids[-1]
    if not baseline_id or not candidate_id:
        raise WebError("baseline_run_id and candidate_run_id are required", 422)
    baseline, candidate = _load_runs([str(baseline_id), str(candidate_id)])
    bmetrics, cmetrics = _report_metrics(baseline), _report_metrics(candidate)
    comparisons = [
        _comparison(baseline, candidate, key, bmetrics, cmetrics, pair=key in ("answer_f1", "evidence_recall", "tokens"))
        for key in ("answer_f1", "evidence_recall", "state_accuracy", "tokens", "p95_latency_ms", "errors")
    ]
    commit = lab_manifest.git_commit()

    def run_entry(run: dict[str, Any], role: str) -> dict[str, Any]:
        metrics = _report_metrics(run)
        entry = {
            "run_id": run.get("run_id"),
            "role": role,
            "kind": run.get("kind") or "single_question",
            "sample": run.get("sample"),
            "preset": run.get("preset"),
            "config_hash": run.get("config_hash"),
            "offline": bool(run.get("offline")),
            "model": run.get("model"),
            "git_commit": run.get("git_commit") or commit,
            "questions": metrics.get("questions") or 1,
            "metrics": {
                "answer_f1": metrics.get("answer_f1"),
                "evidence_recall": metrics.get("evidence_recall"),
                "state_accuracy": metrics.get("state_accuracy"),
                "tokens": metrics.get("tokens"),
                "p95_latency_ms": metrics.get("p95_latency_ms"),
                "errors": metrics.get("errors"),
                "error_rate": metrics.get("error_rate"),
                "questions": metrics.get("questions") or 1,
            },
        }
        for key in ("answer_f1", "evidence_recall", "state_accuracy", "tokens",
                    "p95_latency_ms", "errors", "error_rate"):
            entry[key] = entry["metrics"][key]
        if run.get("kind") != "batch":
            entry["question"] = run.get("question")
        return entry

    def metadata_entry(run: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run.get("run_id"),
            "config_hash": run.get("config_hash"),
            "preset": run.get("preset"),
            "offline": bool(run.get("offline")),
            "model": run.get("model"),
            "git_commit": run.get("git_commit") or commit,
        }

    experiment_id = _safe_id(str(body.get("experiment_id") or f"lab-{time.strftime('%Y%m%d-%H%M%S')}"))
    report_id, path = _unique_report_path(experiment_id)
    web_path = f"#/experiments/{report_id}"
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": report_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "module": body.get("module"),
        "stage": body.get("stage"),
        "title": body.get("title") or report_id,
        "dataset": _dataset_from_runs(baseline, candidate, bmetrics, cmetrics),
        "results": {
            "runs": [run_entry(baseline, "baseline"), run_entry(candidate, "candidate")],
            "metrics": cmetrics,
            "baseline_metrics": bmetrics,
            "candidate_metrics": cmetrics,
        },
        "comparisons": comparisons,
        "analysis": {
            "main_effects": [],
            "interactions": [],
            "pareto": [],
            "by_category": _report_by_category(baseline, candidate),
            "stage_waterfall": _report_stage_waterfall(baseline, candidate),
            "failure_breakdown": [],
        },
        "conclusion": _report_conclusion(baseline, candidate, comparisons, bmetrics, cmetrics),
        "metadata": {
            "git_commit": commit,
            "dataset_hash": lab_manifest.dataset_hash(),
            "baseline": metadata_entry(baseline),
            "candidate": metadata_entry(candidate),
        },
        "manifest": {
            "git_commit": commit,
            "config_hashes": {
                "baseline": baseline.get("config_hash"),
                "candidate": candidate.get("config_hash"),
            },
            "dataset_hash": lab_manifest.dataset_hash(),
            "model": {"baseline": baseline.get("model"), "candidate": candidate.get("model")},
            "offline": {"baseline": bool(baseline.get("offline")),
                        "candidate": bool(candidate.get("offline"))},
        },
        "web": {"route": web_path, "published": True},
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report_id": report_id, "web_path": web_path, "report": report}


def _report_list() -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    for directory in (_report_dir(), _archive_report_dir()):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            if path.name.startswith("._"):
                continue  # macOS AppleDouble metadata copied by tar/Finder
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                experiment_id = data.get("experiment_id", path.stem)
                items[experiment_id] = {"experiment_id": experiment_id,
                                        "created_at": data.get("created_at"),
                                        "status": (data.get("conclusion") or {}).get("status"),
                                        "schema": data.get("schema")}
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
    ordered = sorted(items.values(), key=lambda item: item.get("created_at") or "", reverse=True)
    return {"experiments": ordered, "count": len(ordered)}


def _report_get(experiment_id: str) -> dict[str, Any]:
    name = f"{_safe_id(experiment_id)}.json"
    for path in (_report_dir() / name, _archive_report_dir() / name):
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise WebError(f"unknown experiment report: {experiment_id}", 404)


GRAPH_LABELS = {
    "state_slot": "状态槽（state_slot）",
    "entity_triple": "实体三元组（entity_triple）",
    "three_layer": "三层图（three_layer）",
    "event_sparse": "稀疏事件图（event_sparse）",
}


def graph_options() -> dict[str, Any]:
    impls = registry.list_implementations().get("graph.repr", [])
    return {"representations": [{"id": name, "label_zh": GRAPH_LABELS.get(name, name)} for name in impls]}


def _catalog() -> dict[str, Any]:
    path = ROOT / "configs" / "experiment-catalog.json"
    if not path.is_file():
        return {"schema": "memlab/experiment-catalog@1", "items": [], "count": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    counts = Counter(str(item.get("status") or "unknown") for item in items)
    return {**data, "items": items, "count": len(items), "status_counts": dict(counts)}


def _graph_view(sample_id: str, mode: str = "changed", limit: int = 400) -> dict[str, Any]:
    """Semantic entity -> slot -> fact graph used by the legacy-style force view.

    Nodes: entity / slot / fact.  Edges: member plus the real relation types from
    ``store.relations``.  ``mode=changed`` keeps entity/slot groups with more than
    one fact or any relation endpoint; ``mode=all`` keeps every fact.
    """
    _sample(sample_id)
    cfg = _preset("B0")
    plan = _plan(cfg)
    ctx, _ = _context(plan, sample_id, True)
    facts = [unit for unit in ctx.store.units if unit.kind == "fact"]
    fact_by_id = {unit.memory_id: unit for unit in facts}
    groups: dict[tuple[str, str], list[Any]] = {}
    for unit in facts:
        s = _unit_summary(unit)
        groups.setdefault((s["entity"] or "未知人物", s["attribute"] or "event"), []).append(unit)
    relation_types = {"RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT"}
    source_relations = list(ctx.store.relations) or list(_view(sample_id).relations)
    relations = [r for r in source_relations if r.head_id in fact_by_id and r.tail_id in fact_by_id
                 and str(r.type).upper() in relation_types]
    if str(mode).lower() == "changed":
        changed_ids = set()
        for relation in relations:
            if str(relation.type).upper() != "RETAIN":
                changed_ids.add(relation.head_id)
                changed_ids.add(relation.tail_id)
        for key, units in groups.items():
            if len(units) > 1 and any((_unit_summary(unit)["state"] or "") == "HISTORICAL" for unit in units):
                changed_ids.update(unit.memory_id for unit in units)
        included_groups = {key for key, units in groups.items() if any(unit.memory_id in changed_ids for unit in units)}
        facts = [unit for key, units in groups.items() if key in included_groups for unit in units]
    else:
        included_groups = set(groups)
    facts = facts[:max(1, min(800, limit))]
    included_ids = {unit.memory_id for unit in facts}
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    edges: list[dict[str, Any]] = []
    edge_keys: set[tuple[str, str, str]] = set()

    def add_node(node: dict[str, Any]) -> None:
        if node["id"] not in node_ids:
            node_ids.add(node["id"])
            nodes.append(node)

    versions_by_slot: dict[str, int] = {}
    for unit in facts:
        summary = _unit_summary(unit)
        slot_id = f"s:{summary['entity']}::{summary['attribute']}"
        versions_by_slot[slot_id] = versions_by_slot.get(slot_id, 0) + 1
    for unit in facts:
        summary = _unit_summary(unit)
        entity = summary["entity"] or "未知人物"
        slot = summary["attribute"] or "event"
        ent_id = f"e:{entity.casefold()}"
        slot_id = f"s:{entity}::{slot}"
        add_node({"id": ent_id, "kind": "entity", "label": entity, "state": None, "r": 11})
        slot_units = [u for u in facts if _unit_summary(u)["entity"] == entity and (_unit_summary(u)["attribute"] or "event") == slot]
        active = [u for u in slot_units if (_unit_summary(u)["state"] or "") == "ACTIVE"]
        latest = max(active, key=lambda u: ((_unit_summary(u)["t_ingest"] or {}).get("start") or ""), default=None)
        add_node({"id": slot_id, "kind": "slot", "label": slot, "state": None,
                  "entity": entity, "attribute": slot,
                  "memory_id": latest.memory_id if latest is not None else None,
                  "r": 5 + min(5, versions_by_slot.get(slot_id, 1) / 2)})
        add_node({"id": unit.memory_id, "kind": "fact", "label": f"{summary['value'] or summary['event'] or unit.text}",
                  "state": summary["state"] or "UNRESOLVED", "r": 3.6,
                  "entity": summary["entity"], "attribute": summary["attribute"] or "event",
                  "source_turn": summary["source_turn"], "t_ingest": summary["t_ingest"]})
        for source, target, kind in ((ent_id, slot_id, "member"), (slot_id, unit.memory_id, "member")):
            key = (source, target, kind)
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append({"source": source, "target": target, "type": kind})
    for relation in relations:
        if relation.head_id not in included_ids or relation.tail_id not in included_ids:
            continue
        kind = str(relation.type).upper()
        key = (relation.head_id, relation.tail_id, kind)
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append({"source": relation.head_id, "target": relation.tail_id, "type": kind})
    facts_model = legacy_config.extraction_model()
    facts_file = getattr(legacy_config, "FACTS_DIR", ROOT / "data" / "facts") / f"{sample_id}--{legacy_config.model_slug(facts_model)}.json"
    states_file = getattr(legacy_config, "STATES_DIR", ROOT / "data" / "states") / f"{sample_id}--{legacy_config.model_slug(facts_model)}.json"
    return {
        "sample": sample_id, "mode": str(mode).lower(), "offline": True,
        "source": {
            "kind": "cached_fact_artifacts", "facts_model": facts_model,
            "facts_file": str(facts_file) if facts_file.exists() else None,
            "states_file": str(states_file) if states_file.exists() else None,
            "note": "图由已缓存的 facts/states 构图；页面不会实时调用 LLM 重新抽取。换模型后需重跑 scripts/extract.py / scripts/build_states.py。",
        },
        "stats": {"facts_total": len(fact_by_id), "groups_total": len(groups),
                  "facts_shown": len(facts), "groups_shown": len(included_groups),
                  "nodes": len(nodes), "edges": len(edges),
                  "relations_total": len(relations)},
        "nodes": nodes, "edges": edges,
        "legend": [
            {"kind": "data", "label": "当前有效"},
            {"kind": "history", "label": "已过时"},
            {"kind": "progress", "label": "推进·替换"},
            {"kind": "conflict", "label": "矛盾"},
        ],
    }


def _timeline(sample_id: str) -> dict[str, Any]:
    view = _view(sample_id)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for unit in view.units:
        if unit.kind != "fact":
            continue
        summary = _unit_summary(unit)
        entity = summary["entity"] or "未知人物"
        attribute = summary["attribute"] or "event"
        groups.setdefault((entity, attribute), []).append(summary)
    out = []
    for (entity, attribute), versions in groups.items():
        versions.sort(key=lambda x: ((x["t_ingest"] or {}).get("start") or "", x["memory_id"]))
        out.append({"entity": entity, "attribute": attribute, "versions": versions})
    out.sort(key=lambda group: (group["entity"], group["attribute"]))
    stamps = [v["t_ingest"]["start"] for group in out for v in group["versions"] if v["t_ingest"] and v["t_ingest"].get("start")]
    return {
        "sample": sample_id, "split": legacy_config.split_of(sample_id),
        "axis": "t_ingest", "axis_label": "写入/会话时间",
        "min": min(stamps) if stamps else None, "max": max(stamps) if stamps else None,
        "groups": out[:80], "group_count": len(out),
        "fact_count": sum(len(group["versions"]) for group in out),
    }


C_ARTIFACTS = {
    "state_accuracy": "eval/archive/state-accuracy.json",
    "e1_adoption": "eval/archive/e1-adoption-offline.json",
    "e3_offline": "eval/archive/e3-offline.json",
    "planner_k": "eval/archive/params-planner-k-corrected.json",
}


def _c_artifacts() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, rel in C_ARTIFACTS.items():
        path = ROOT / rel
        if not path.is_file():
            out[key] = {"available": False, "path": rel, "reason": "file not found"}
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out[key] = {"available": True, "path": rel, **data}
        except (OSError, json.JSONDecodeError) as exc:
            out[key] = {"available": False, "path": rel, "reason": str(exc)}
    return out


def _project_reports() -> list[dict[str, Any]]:
    out = []
    for item in _report_list()["experiments"]:
        try:
            report = _report_get(item["experiment_id"])
        except Exception:
            continue
        out.append({
            "experiment_id": report.get("experiment_id"),
            "dataset": report.get("dataset"),
            "results": report.get("results"),
            "conclusion": report.get("conclusion"),
            "manifest": report.get("manifest"),
            "created_at": report.get("created_at"),
        })
    return out


def get(path: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    args = args or {}
    route = path[len("/api/v2"):] if path.startswith("/api/v2") else path

    if route == "/questions":
        sample_id = str(_one(args, "sample", "") or "")
        category = str(_one(args, "category", "") or "")
        limit = _one(args, "limit", 50)
        try:
            limit = int(limit if limit not in (None, "") else 50)
        except (TypeError, ValueError) as exc:
            raise WebError("limit must be an integer", 400) from exc
        return _question_items(sample_id, category, limit, _one(args, "seed", None))

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

    if route == "/graph":
        sample_id = str(_one(args, "sample", ""))
        semantic = "mode" in args or _one(args, "view") == "semantic" or "repr" in args or "q" in args
        limit = int(_one(args, "limit", 400 if semantic else 120) or (400 if semantic else 120))
        if "mode" in args or _one(args, "view") == "semantic":
            return _graph_view(sample_id, str(_one(args, "mode", "changed") or "changed"), limit)
        if "repr" in args or "q" in args:
            return _graph_view(sample_id, "changed", limit)
        return _graph(sample_id, limit)

    match = re.fullmatch(r"/memories/([^/]+)", route)
    if match:
        sample_id = str(_one(args, "sample", ""))
        return _detail(sample_id, unquote(match.group(1)))

    if route == "/memories":
        sample_id = str(_one(args, "sample", ""))
        _sample(sample_id)
        view = _view(sample_id)
        type_filter = str(_one(args, "type", "") or "")
        kind = str(_one(args, "kind", "") or "")
        state = str(_one(args, "state", "") or "")
        entity_filter = str(_one(args, "entity", "") or "")
        attribute_filter = str(_one(args, "attribute", "") or "")
        query = str(_one(args, "q", "") or "").strip().lower()
        page = max(1, int(_one(args, "page", 1) or 1))
        size = min(100, max(1, int(_one(args, "page_size", 40) or 40)))
        all_facts = [_unit_summary(unit) for unit in view.units if unit.kind == "fact"]
        counts = {"turn": sum(1 for unit in view.units if unit.kind == "turn"),
                  "fact": len(all_facts),
                  "fact_only": sum(1 for x in all_facts if not x["event"]),
                  "event": sum(1 for x in all_facts if x["event"])}
        entity_counts = Counter(x["entity"] or "未知人物" for x in all_facts)
        base = [x for x in all_facts
                if (not entity_filter or (x["entity"] or "未知人物") == entity_filter)
                and (not attribute_filter or (x["attribute"] or "event") == attribute_filter)]
        status_counts = Counter(x["state"] or "UNRESOLVED" for x in base)
        units = []
        for summary in base:
            wanted = type_filter or kind
            if wanted == "event":
                if not summary["event"]:
                    continue
            elif wanted in ("fact", "事实"):
                if summary["event"]:
                    continue
            elif wanted == "turn":
                continue
            elif wanted not in ("all", "全部", ""):
                continue
            if state and summary["state"].upper() != state.upper():
                continue
            haystack = f"{summary['text']} {summary['entity']} {summary['attribute']} {summary['value']} {summary['event']}".lower()
            if query and query not in haystack:
                continue
            units.append(summary)
        start = (page - 1) * size
        entities = [{"name": name, "count": count} for name, count in entity_counts.most_common(20)]
        return {
            "sample": sample_id, "split": legacy_config.split_of(sample_id),
            "total": len(units), "page": page, "page_size": size,
            "counts": counts,
            "facets": {
                "status": {key: status_counts.get(key, 0) for key in ("ACTIVE", "HISTORICAL", "CONFLICT", "UNRESOLVED")},
                "kind": {"fact": len(base), "event": sum(1 for x in base if x["event"]),
                         "fact_only": sum(1 for x in base if not x["event"])},
                "entities": entities,
            },
            "memories": units[start:start + size],
        }

    if route == "/timeline":
        return _timeline(str(_one(args, "sample", "")))

    if route == "/artifacts":
        return {"available": True, "artifacts": _c_artifacts()}

    if route == "/graph/options":
        return graph_options()

    if route == "/experiments/plan":
        return _catalog()

    if route == "/evaluation":
        path = ROOT / "eval" / "results.json"
        if not path.is_file():
            return {"available": False, "reason": "eval/results.json not found"}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"available": True, "source": "eval/results.json", "reports": _report_list()["experiments"],
                "project_reports": _project_reports(), "hardware": HARDWARE, **data}

    if route == "/system":
        reports = _report_list()["experiments"]
        return {
            "commit": lab_manifest.git_commit(),
            "provenance": {
                "course": {
                    "label": "课程/搜集数据（不是本项目生成）",
                    "items": [
                        {"name": "LoCoMo 10 段对话 + QA/evidence", "path": "data/locomo10.json",
                         "origin": "课程提供 / LoCoMo 数据集"},
                    ],
                },
                "inherited": {
                    "label": "上一版继承（ff6c7a1 之前已存在）",
                    "items": [
                        {"name": "缓存 facts", "path": "data/facts/*.json",
                         "origin": "上一版 qwen3.8:27b 抽取产物"},
                        {"name": "缓存 states/relations", "path": "data/states/*.json",
                         "origin": "上一版状态链产物"},
                        {"name": "27B 评测归档", "path": "eval/results.json",
                         "origin": "上一版 Full/Vector/Hybrid/Dynamic 结果"},
                        {"name": "状态标注", "path": "eval/state_benchmark.json",
                         "origin": "上一版自建参考集（非课程官方标注）"},
                        {"name": "旧 Web/legacy pipeline", "path": "memwb/, web/, /api/*",
                         "origin": "上一版代码与页面"},
                    ],
                },
                "this_project": {
                    "label": "本项目新增",
                    "items": [
                        {"name": "memlab v2 + Web /api/v2", "path": "memlab/, server.py, web/v2.js",
                         "origin": "本项目实现"},
                        {"name": "S6 E1 离线筛选", "path": "runs/s6/e1.sqlite",
                         "origin": "本项目 36 runs offline（4 dev，80题×2 seeds）"},
                        {"name": "W3 test 离线最终评测", "path": "eval/archive/final-w3.json",
                         "origin": "本项目 B0/R0，test 2 段，80题/配置，2 seeds"},
                        {"name": "Web 实验报告", "path": "reports/experiments/*.json",
                         "origin": "本项目 Web 运行/报告；当前含 final-w3"},
                        {"name": "实验计划矩阵", "path": "configs/experiment-catalog.json",
                         "origin": "本项目按 04 整理的 24 项计划/状态"},
                    ],
                },
                "notes": [
                    "v2 记忆/图谱的内容仍来自继承的 facts/states；本项目新增的是映射、构图、检索、运行与展示。",
                    "本项目没有重新跑 27B 抽取；final-w3 的 F1/Recall 是新跑的 offline E2E，不是新 LLM 抽取。",
                    "Web 评测页上方的 Full/Vector/Hybrid/Dynamic 表是继承归档；下方 Web 报告才是本项目运行。",
                ],
            },
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
            "web": {"version": "w1", "api": "/api/v2", "legacy_api": "/api", "reports": reports},
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
    if route == "/reports/from-runs":
        return _report_from_runs(body)
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
