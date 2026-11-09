"""Dev-only diagnosis for the online R0 collapse.

Runs the frozen R0 and four pre-registered fixes on the four development
conversations.  It never touches the test split.  The goal is to separate:
post-filter pruning, MMR/decay/compress pruning, missing time context, and
cross-encoder top_n.
"""
from __future__ import annotations

import copy
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memlab import webapp

SAMPLES = ["conv-26", "conv-30", "conv-43", "conv-44"]
VARIANTS = ["r0", "dropstale", "postoff", "time", "combined"]


def make_config(name: str) -> dict:
    cfg = copy.deepcopy(webapp._preset("R0").to_dict())
    cfg["preset"] = f"R0-{name}"
    if name in ("dropstale", "combined"):
        cfg["post"]["filter"]["params"]["drop_stale"] = False
    if name in ("postoff", "combined"):
        for key in ("mmr", "decay", "compress"):
            cfg["post"][key] = {"impl": "none", "params": {}}
    if name in ("time", "combined"):
        cfg["answer"].setdefault("params", {})["time_context"] = True
    if name == "combined":
        cfg["rerank"]["params"]["top_n"] = 100
    return cfg


def mean(values):
    values = [float(v) for v in values if v is not None]
    return round(statistics.mean(values), 4) if values else None


def main() -> int:
    started = time.time()
    out = {"schema": "memlab/dev-diagnostics@1", "split": "development",
           "samples": SAMPLES, "questions_per_sample": 5, "seed": 13,
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "variants": {}}
    for name in VARIANTS:
        cfg = make_config(name)
        all_rows = []
        for sample in SAMPLES:
            result = webapp.post("/api/v2/runs", {
                "sample": sample, "batch": True, "questions": 5,
                "seed": 13, "offline": False, "config": cfg,
            })
            all_rows.extend(result.get("rows") or [])
            print(f"{name} {sample}: F1={result['metrics'].get('answer_f1')} "
                  f"R={result['metrics'].get('evidence_recall')} "
                  f"refused={result['metrics'].get('refused_rate')}", flush=True)
        f1 = [r.get("answer_f1") for r in all_rows]
        rec = [r.get("evidence_recall") for r in all_rows]
        refused = [1 if r.get("refused") else 0 for r in all_rows]
        answered = [r for r in all_rows if not r.get("refused")]
        by_category = {}
        for r in all_rows:
            by_category.setdefault(str(r.get("category")), []).append(r)
        out["variants"][name] = {
            "config": cfg,
            "metrics": {
                "questions": len(all_rows),
                "answer_f1": mean(f1),
                "evidence_recall": mean(rec),
                "refused_rate": mean(refused),
                "answered_questions": len(answered),
                "answered_f1": mean([r.get("answer_f1") for r in answered]),
                "tokens": mean([r.get("tokens") for r in all_rows]),
            },
            "by_category": {
                cat: {"n": len(rows), "answer_f1": mean([r.get("answer_f1") for r in rows]),
                      "evidence_recall": mean([r.get("evidence_recall") for r in rows]),
                      "refused_rate": mean([1 if r.get("refused") else 0 for r in rows])}
                for cat, rows in sorted(by_category.items())
            },
            "rows": all_rows,
        }
        print(name, json.dumps(out["variants"][name]["metrics"], ensure_ascii=False), flush=True)
    out["elapsed_seconds"] = round(time.time() - started, 1)
    path = ROOT / "eval" / "archive" / "dev-diagnostics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
