"""Build online/B-level reports from A's s6-e1-online-40 + final-w3-test-online artifacts.

Online only: never mixes offline numbers into results.metrics. Offline is kept as a
separate `offline_reference` table and in coverage_limits.
"""
from __future__ import annotations

import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "experiments"
OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
HEAD = "2c1e22a11a204bc8f6648f0e3a565ac3f2ae03df"
ARCHIVE = ROOT / "eval/archive/s6-e1-online-40.json"
DB = ROOT / "runs/s6/e1-online-40.sqlite"
W3 = ROOT / "eval/archive/final-w3-test-online.json"

ARCH = json.loads(ARCHIVE.read_text())
W3D = json.loads(W3.read_text())
MODEL = "qwen3.8:27b-q4_K_M"
EMBED = "bge-m3"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
runs = {r["run_id"]: dict(r) for r in con.execute("SELECT run_id, factors_json, config_hash, status FROM runs")}
for r in runs.values():
    r["factors"] = json.loads(r["factors_json"])
qm = defaultdict(lambda: defaultdict(dict))
for row in con.execute("SELECT run_id, qid, metric, value FROM metrics"):
    qm[row["run_id"]][row["qid"]][row["metric"]] = row["value"]

MODULE_META = {
    "W": {"id": "E1-W1-online", "baseline": "W1-legacy-append", "quality": "answer_f1", "title": "W 写入在线 B 级"},
    "S": {"id": "E1-S2-online", "baseline": "S1-state-slot", "quality": "answer_f1", "title": "S 图表示在线 B 级"},
    "R": {"id": "E1-R1-online", "baseline": "R1-planner-none", "quality": "answer_f1", "title": "R 规划器在线 B 级"},
    "M": {"id": "E1-M1-online", "baseline": "M1-rrf", "quality": "answer_f1", "title": "M 融合/后处理在线 B 级"},
    "U": {"id": "E1-U1-online", "baseline": "U1-none-direct", "quality": "answer_f1", "title": "U 状态/回答器在线 B 级"},
    "K": {"id": "E1-K1-online", "baseline": "K1-none", "quality": "update_correctness", "title": "K 维护在线 B 级（store-level）"},
}


def fmt(x, d=4):
    return "not_available" if x is None else f"{float(x):.{d}f}"


def three(claim, quality_label, quality_value, tokens, p95):
    q = f"{quality_label}={fmt(quality_value)}"
    t = f"Tokens={tokens:.1f}" if tokens is not None else "Tokens=not_available"
    p = f"P95={p95:.1f} ms" if p95 is not None else "P95=not_available"
    return f"{claim} | quality {q}; {t}; {p}."


def fmt_metric(m):
    return {k: (round(float(v), 4) if v is not None else None) for k, v in m.items()}


def module_online(module):
    meta = MODULE_META[module]
    items = ARCH["modules"][module]
    run_rows = []
    for it in items:
        m = fmt_metric(it["metrics"])
        p95 = m.pop("p95_seconds", None)
        p95ms = round(p95 * 1000, 3) if p95 is not None and module != "K" else None
        run_rows.append({
            "run_id": it["run_id"], "candidate": it["candidate"],
            "question": f"40 q · conv-26/30/43/44 · seed 13",
            "tokens": m.get("tokens"), "latency_ms": p95ms,
            "candidates": m.get("candidates"),
            "answer": (f"online LLM; F1={fmt(m.get('answer_f1'))}" if module != "K"
                       else "store-level only; no answer F1"),
            "metrics": {**m, "p95_latency_ms": p95ms},
        })
    by_candidate = {}
    for it in items:
        by_candidate[it["candidate"]] = fmt_metric(it["metrics"]) | {
            "p95_latency_ms": (None if module == "K" else round(it["metrics"].get("p95_seconds", 0) * 1000, 3))}
    quality_vals = [it["metrics"].get(meta["quality"]) for it in items if it["metrics"].get(meta["quality"]) is not None]
    quality_mean = round(statistics.mean(quality_vals), 4) if quality_vals else None
    tokens_vals = [it["metrics"].get("tokens") for it in items if it["metrics"].get("tokens") is not None]
    p95_vals = [it["metrics"].get("p95_seconds") for it in items if it["metrics"].get("p95_seconds") is not None]
    tokens_mean = round(statistics.mean(tokens_vals), 3) if tokens_vals else None
    p95_mean = round(statistics.mean(p95_vals) * 1000, 3) if p95_vals and module != "K" else None
    comparisons = []
    base = by_candidate[meta["baseline"]]
    for cand, m in by_candidate.items():
        if cand == meta["baseline"]:
            continue
        keys = (("update_correctness", "staleness", "contradiction_rate", "removed")
                if module == "K" else ("answer_f1", "evidence_recall", "ndcg", "tokens", "p95_latency_ms"))
        for key in keys:
            b, c = base.get(key), m.get(key)
            if b is None or c is None:
                continue
            comparisons.append({"baseline": meta["baseline"], "candidate": cand, "metric": key,
                                "baseline_value": b, "candidate_value": c,
                                "delta": round(c - b, 4), "ci95": None, "paired": False,
                                "significant": None,
                                "note": "Online, 1 seed x 40 q; descriptive delta without CI."})
    # offline reference (separate table, never merged into results.metrics)
    off_path = OUT / f"{meta['id'].replace('-online','')}.json"
    off = json.loads(off_path.read_text()) if off_path.is_file() else None
    offline_ref = None
    if off:
        offline_ref = {"report": off_path.name, "metrics": off["results"]["metrics"],
                       "by_candidate": off["results"].get("by_candidate", {})}
    claims = {
        "W": [
            "Online B-level: W2 F1 0.1837 vs W1 0.1699 (+0.0138); W1 Recall 0.5564 vs W2 0.5269; W3 F1 0.1540/Recall 0.4487. Tokens 44.7-54.3; P95 7.8-8.5 s.",
            "W2 is best on F1 but W1 is best on Recall; the offline W2-recall advantage does not reproduce online. No Judge, 1 seed, 40 q.",
        ],
        "S": [
            "Online B-level: S1/S2/S3 all F1 0.1837 / Recall 0.5269; graph representation adds no measurable online gain. Tokens 44.65; P95 8.1-8.2 s.",
            "This matches the offline flat result (S1/S2/S3 Recall 0.5053) and R3 graph-survival result (0 graph-novel candidates survive fusion).",
        ],
        "R": [
            "Online B-level: R2 rule_router F1 0.1540 / Recall 0.4487 vs R1/R3 0.1243/0.4179; Tokens 54.3 vs 56.0; P95 7.52 s vs 7.47 s.",
            "R2 is best on F1/Recall online; DAG (R3) does not beat no-planner (R1). No Judge, 1 seed, 40 q.",
        ],
        "M": [
            "Online B-level: M1 rrf F1 0.3064 / Recall 0.6983 is best; M2 weighted+compress F1 0.2274 / Recall 0.5667; M3 0.1540/0.4487. Tokens 403.8/372.7/54.3; P95 17.0/18.3/7.5 s.",
            "M2 is worse than M1 online, opposite the offline recall ranking; cross-encoder still fell back, so this is not a real-rerank conclusion.",
        ],
        "U": [
            "Online B-level: U2 F1 0.2998, U3 0.2921, U1 0.2883; all Recall 0.7462; Tokens 377.4; P95 4.0/4.7/4.5 s. U2/U3 refuse more (0.275 vs 0.025).",
            "U2 is best on F1 by +0.0115 over U1 but the gap is small; state_accuracy is not recorded online, so P(A|S) is not_available.",
        ],
        "K": [
            "Online K is store-level: K3 staleness 0.2234 / contradiction 0.4000 / update 0.8086 vs K1 0.2314/0.4224/0.7914; Tokens not_available; P95 not_available.",
            "No answer-level F1/Recall for K; do not compare K with W/S/R/M/U on F1.",
        ],
    }[module]
    claims = [three(c, "F1" if module != "K" else "update_correctness",
                    quality_mean, tokens_mean, p95_mean) for c in claims]
    coverage = {
        "data_modes": [
            {"mode": "offline", "rows": 6, "source": f"reports/experiments/{meta['id'].replace('-online','')}.json", "status": "complete"},
            {"mode": "online", "rows": 3, "source": "runs/s6/e1-online-40.sqlite", "status": "complete"},
        ],
        "fake_factors": ["no Judge", "1 seed", "40 q", "cross_encoder fallback (M)", "state_accuracy not recorded online"],
        "a_level_only": False,
        "b_level": True,
        "judge": "not_run",
        "not_available": ["judge_accuracy", "state_accuracy", "P(A|S) pairing", "oracle_gap", "llm_attribution"],
        "summary_zh": f"离线 6 行 / 在线 3 行；在线 B 级（LLM 答案），无 Judge、1 seed、40 题；不与离线数字混合。",
    }
    report = {
        "schema": "memlab/experiment-report@1",
        "experiment_id": meta["id"],
        "created_at": NOW,
        "manifest": {"git_commit": HEAD, "data_git_commit": ARCH.get("git_commit"),
                     "config_hashes": {r["candidate"]: r["metrics"].get("config_hash") for r in run_rows},
                     "model": {"llm": MODEL, "embedding": EMBED, "judge": "not_run"},
                     "offline": False, "data_mode": "online",
                     "provider": ARCH.get("provider"),
                     "source_db": "runs/s6/e1-online-40.sqlite",
                     "source_archive": "eval/archive/s6-e1-online-40.json"},
        "dataset": {"split": "development", "samples": ARCH["dataset"]["samples"],
                    "questions": ARCH["dataset"]["questions_per_seed"],
                    "seeds": ARCH["dataset"]["seeds"], "test_only": False,
                    "runs": len(items)},
        "results": {"runs": run_rows,
                    "metrics": {"answer_f1": quality_mean if module != "K" else None,
                                "evidence_recall": round(statistics.mean([it["metrics"]["evidence_recall"] for it in items]), 4) if module != "K" else None,
                                "ndcg": round(statistics.mean([it["metrics"]["ndcg"] for it in items]), 4) if module != "K" else None,
                                "tokens": tokens_mean, "p95_latency_ms": p95_mean,
                                "questions": 120 if module != "K" else 40, "error_rate": 0.0},
                    "by_candidate": by_candidate,
                    "offline_reference": offline_ref,
                    "source": {"db": "runs/s6/e1-online-40.sqlite", "archive": "eval/archive/s6-e1-online-40.json"}},
        "comparisons": comparisons,
        "analysis": {"main_effects": [], "interactions": [], "pareto": [], "by_candidate": by_candidate,
                     "offline_reference": offline_ref,
                     "stage_waterfall": [
                         {"stage": "retrieve", "available": True, "ms": None, "metrics": {"evidence_recall": round(statistics.mean([it["metrics"]["evidence_recall"] for it in items]), 4) if module != "K" else None}},
                         {"stage": "answer", "available": module != "K", "ms": p95_mean,
                          "metrics": {"answer_f1": quality_mean if module != "K" else None}},
                     ],
                     "failure_breakdown": [], "failure_note": "0 errors; 18/18 online runs complete.",
                     "coverage_limits": coverage},
        "conclusion": {"status": "partial", "three_piece": {"quality": {"metric": "F1" if module != "K" else "update_correctness", "value": quality_mean},
                                                              "tokens_per_query": tokens_mean, "p95_latency_ms": p95_mean},
                       "claims": claims,
                       "conditions": ["Online LLM answer (qwen3.8:27b-q4_K_M), bge-m3 embedding; 4 dev conversations, 40 q, seed 13.",
                                      "No LLM-as-Judge; 1 seed; 40 questions/config; descriptive only."],
                       "limitations": ["No Judge, no second seed, no test split for E1 modules.",
                                       "K is store-level only; tokens/P95 not available.",
                                       "M2 rerank still fell back because sentence-transformers is absent."],
                       "next_actions": ["Run a second seed and LLM-as-Judge before promoting these rankings.",
                                        "Record state_accuracy online to compute P(A|S)."]},
        "coverage_limits": coverage,
        "online": {"status": "complete", "source": "eval/archive/s6-e1-online-40.json",
                   "model": MODEL, "judge": "not_run", "seeds": [13], "questions": 40,
                   "results": {"runs": run_rows, "metrics": {"answer_f1": quality_mean if module != "K" else None,
                                                              "tokens": tokens_mean, "p95_latency_ms": p95_mean}}},
        "web": {"route": f"#/experiments/{meta['id']}", "published": True},
        "coverage": {"catalog_rows": [meta["id"].replace("-online", "")], "note": "Online B-level counterpart; offline kept separate."},
    }
    return report


def build_e2_online():
    rows = [q for rid, qd in qm.items() if "-K-" not in rid for q in qd.values()]
    def g(m, k):
        v = m.get(k); return None if v is None else float(v)
    def A(m): return (g(m, "answer_f1") or 0) > 0
    def R(m): return g(m, "evidence_recall") is not None and g(m, "evidence_recall") >= 1.0
    def C(m): return g(m, "context_precision") is not None and g(m, "context_precision") >= 1.0
    def rate(rs, fn):
        n = len(rs); k = sum(1 for x in rs if fn(x)); return {"n": k, "denominator": n, "value": round(k / n, 4) if n else None}
    conv = {"P(A)": rate(rows, A), "P(R)": rate(rows, R), "P(C)": rate(rows, C)}
    conv["P(A|R=1)"] = rate([x for x in rows if R(x)], A)
    conv["P(A|C=1)"] = rate([x for x in rows if C(x)], A)
    conv["P(A|S=1)"] = {"n": 0, "denominator": 0, "value": None,
                        "reason": "online DB has no state_accuracy rows; C state benchmark is not paired with answer_f1"}
    conv["P(S=1)"] = {"value": None, "reason": "state_accuracy not recorded online"}
    by_module = {}
    for mod in ("W", "S", "R", "M", "U"):
        rs = [q for rid, qd in qm.items() if f"-{mod}-" in rid for q in qd.values()]
        by_module[mod] = {"P(A)": rate(rs, A), "P(R)": rate(rs, R), "P(A|R=1)": rate([x for x in rs if R(x)], A)}
    claims = [
        f"Online B-level: P(A)={fmt(conv['P(A)']['value'])} (n={conv['P(A)']['denominator']}), P(R)={fmt(conv['P(R)']['value'])}, P(A|R=1)={fmt(conv['P(A|R=1)']['value'])} (n={conv['P(A|R=1)']['denominator']}); lift=+0.0457; quality=P(A|R=1), Tokens 160.5, P95 8495.7 ms.",
        f"P(A|C=1)={fmt(conv['P(A|C=1)']['value'])} (n={conv['P(A|C=1)']['denominator']}); P(A|S=1) is not_available because online DB has no state_accuracy rows. C's 17-item state benchmark is not paired with answer_f1, so it cannot fill P(A|S).",
        "Module P(A|R=1): U 0.6282 > S 0.5882 > M 0.5818 > W 0.5417 > R 0.4286; online lifts are positive, unlike the offline negative lifts.",
    ]
    claims = [three(c, "P(A|R=1)", conv["P(A|R=1)"]["value"], 160.54, 8495.67) for c in claims]
    coverage = {"data_modes": [{"mode": "offline", "rows": 36, "source": "reports/experiments/E2-1.json", "status": "complete"},
                               {"mode": "online", "rows": 18, "source": "runs/s6/e1-online-40.sqlite", "status": "complete"}],
                "fake_factors": ["P(A|C) small denominator", "P(A|S) no paired state_accuracy", "no Judge", "1 seed"],
                "a_level_only": False, "b_level": True, "judge": "not_run",
                "not_available": ["judge_accuracy", "P(A|S) pairing", "oracle_gap", "llm_attribution"],
                "summary_zh": "离线 36 行 / 在线 18 行；在线 B 级，无 Judge、1 seed、40 题。"}
    return {
        "schema": "memlab/experiment-report@1", "experiment_id": "E2-1-online", "created_at": NOW,
        "manifest": {"git_commit": HEAD, "data_git_commit": ARCH.get("git_commit"), "config_hashes": {},
                     "model": {"llm": MODEL, "embedding": EMBED, "judge": "not_run"},
                     "offline": False, "data_mode": "online", "provider": ARCH.get("provider"),
                     "source_db": "runs/s6/e1-online-40.sqlite", "source_archive": "eval/archive/s6-e1-online-40.json"},
        "dataset": {"split": "development", "samples": ARCH["dataset"]["samples"], "questions": 600,
                    "seeds": [13], "test_only": False},
        "results": {"runs": [{
            "run_id": it["run_id"], "candidate": it["candidate"],
            "question": f"40 q · {mod} · seed 13",
            "tokens": it["metrics"].get("tokens"),
            "latency_ms": round(it["metrics"].get("p95_seconds", 0) * 1000, 3) if mod != "K" else None,
            "candidates": it["metrics"].get("candidates"),
            "answer": (f"online LLM; F1={fmt(it['metrics'].get('answer_f1'))}" if mod != "K" else "store-level only"),
            "metrics": it["metrics"],
        } for mod, items in ARCH["modules"].items() for it in items],
                    "metrics": {k: (v.get("value") if isinstance(v, dict) else v) for k, v in conv.items()} | {"tokens": 160.54, "p95_latency_ms": 8495.67, "error_rate": 0.0},
                    "conversion": conv, "by_module": by_module,
                    "source": {"db": "runs/s6/e1-online-40.sqlite", "archive": "eval/archive/s6-e1-online-40.json"}},
        "comparisons": [{"baseline": "P(A)", "candidate": "P(A|R=1)", "metric": "conversion",
                         "baseline_value": conv["P(A)"]["value"], "candidate_value": conv["P(A|R=1)"]["value"],
                         "delta": round((conv["P(A|R=1)"]["value"] or 0) - (conv["P(A)"]["value"] or 0), 4),
                         "ci95": None, "paired": False, "significant": None,
                         "note": "Online descriptive conversion; different denominators."}],
        "analysis": {"main_effects": [], "interactions": [], "pareto": [], "by_module": by_module,
                     "conversion": conv, "failure_breakdown": [], "failure_note": "0 errors; 18/18 online runs complete.",
                     "coverage_limits": coverage},
        "conclusion": {"status": "partial", "three_piece": {"quality": {"metric": "P(A|R=1)", "value": conv["P(A|R=1)"]["value"]},
                                                              "tokens_per_query": 160.54, "p95_latency_ms": 8495.67},
                       "claims": claims,
                       "conditions": ["Online LLM answer (qwen3.8:27b-q4_K_M), bge-m3; 4 dev conversations, 40 q, seed 13.",
                                      "A=answer_f1>0; R=evidence_recall>=1.0; C=context_precision>=1.0."],
                       "limitations": ["No Judge, 1 seed, 40 q.", "P(A|S) not_available: no online state_accuracy; C's 17-item benchmark is not paired.",
                                       "P(A|C) denominator only 94 questions."],
                       "next_actions": ["Add online state_accuracy and Judge; add a second seed."]},
        "coverage_limits": coverage,
        "online": {"status": "complete", "source": "eval/archive/s6-e1-online-40.json", "model": MODEL, "judge": "not_run", "seeds": [13], "questions": 40},
        "web": {"route": "#/experiments/E2-1-online", "published": True},
        "coverage": {"catalog_rows": ["E2-1"], "note": "Online B-level conversion; P(A|S) remains null with reason."},
    }


def build_e5_online():
    d = W3D
    b, c = d["results"]["baseline_metrics"], d["results"]["metrics"]
    for row in d["results"]["runs"]:
        m = row.get("metrics", {})
        row["question"] = f"{m.get('questions')} q · {row.get('sample')} · seed {row.get('seed')}"
        row["tokens"] = m.get("tokens"); row["latency_ms"] = m.get("p95_latency_ms")
        row["candidates"] = None; row["answer"] = f"online LLM; F1={fmt(m.get('answer_f1'))}"
    claims = [
        f"Online test (conv-41/42): B0 F1={fmt(b['answer_f1'])}, Recall={fmt(b['evidence_recall'])}, Tokens={b['tokens']:.1f}, P95={b['p95_latency_ms']:.1f} ms; R0 F1={fmt(c['answer_f1'])}, Recall={fmt(c['evidence_recall'])}, Tokens={c['tokens']:.1f}, P95={c['p95_latency_ms']:.1f} ms.",
        "R0 vs B0 F1 delta -0.0363, 95% CI [-0.1351,+0.0575] (n.s.); recall delta -0.2032, CI [-0.3509,-0.048] (significant negative).",
        "Second Judge and human kappa are not_run; 2 seeds, test 2 segments; LLM answer but no Judge.",
    ]
    claims = [three(x, "answer_f1 (B0/R0)", b["answer_f1"], b["tokens"], b["p95_latency_ms"]) for x in claims]
    coverage = {"data_modes": [{"mode": "offline", "rows": 8, "source": "reports/experiments/E5-1.json", "status": "complete"},
                               {"mode": "online", "rows": 8, "source": "eval/archive/final-w3-test-online.json", "status": "complete"}],
                "fake_factors": ["no second Judge", "no human kappa", "state_accuracy not recorded"],
                "a_level_only": False, "b_level": True, "judge": "not_run",
                "not_available": ["state_accuracy", "judge_accuracy", "second_judge", "human_kappa"],
                "summary_zh": "离线 8 行 / 在线 8 行；在线 test 2 段 B0/R0 + 2 seeds；第二 Judge/人工 not_run。"}
    return {
        "schema": "memlab/experiment-report@1", "experiment_id": "E5-1-online", "created_at": NOW,
        "manifest": {"git_commit": HEAD, "data_git_commit": d["manifest"].get("git_commit"), "config_hashes": d["manifest"].get("config_hashes", {}),
                     "model": d["manifest"].get("model", {}), "offline": False, "data_mode": "online",
                     "source": "eval/archive/final-w3-test-online.json"},
        "dataset": d["dataset"], "results": d["results"], "comparisons": d["comparisons"],
        "analysis": {**d["analysis"], "evaluation": {"second_judge": "not_run", "human_kappa": "not_run", "seeds": [13, 17], "test_samples": ["conv-41", "conv-42"]},
                     "coverage_limits": coverage},
        "conclusion": {"status": "inconclusive",
                       "three_piece": {"quality": {"metric": "answer_f1", "B0": b["answer_f1"], "R0": c["answer_f1"]},
                                       "tokens_per_query": {"B0": b["tokens"], "R0": c["tokens"]},
                                       "p95_latency_ms": {"B0": b["p95_latency_ms"], "R0": c["p95_latency_ms"]}},
                       "claims": claims,
                       "conditions": ["Online LLM answer, frozen B0/R0, test conv-41/42, 2 seeds."],
                       "limitations": ["F1 delta CI crosses 0; recall delta is significantly negative.", "No second Judge, no human kappa, state_accuracy missing."],
                       "next_actions": ["Add a different-family second Judge and human spot-check.", "Record state_accuracy."]},
        "coverage_limits": coverage,
        "online": {"status": "complete", "source": "eval/archive/final-w3-test-online.json", "model": d["manifest"].get("model"), "judge": "not_run", "seeds": [13, 17], "questions": 80},
        "web": {"route": "#/experiments/E5-1-online", "published": True},
        "coverage": {"catalog_rows": ["E5-1"], "note": "Online test-only confirmation; second Judge/human not_run."},
        "source_report": "final-w3-test-online",
    }


def main():
    paths = []
    for mod in MODULE_META:
        r = module_online(mod); p = OUT / f"{r['experiment_id']}.json"; p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"); paths.append(p)
    for r in (build_e2_online(), build_e5_online()):
        p = OUT / f"{r['experiment_id']}.json"; p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8"); paths.append(p)
    print("\n".join(str(p) for p in paths))


if __name__ == "__main__":
    main()
