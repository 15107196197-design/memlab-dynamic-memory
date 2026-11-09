import sqlite3, json, math, statistics, collections, random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "runs/s6/e1.sqlite"
ARCHIVE = ROOT / "eval/archive/s6-e1-screening.json"
S7B = ROOT / "eval/archive/s7b-a-offline.json"

archive = json.loads(ARCHIVE.read_text())
s7b = json.loads(S7B.read_text())

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
runs = []
for row in con.execute("SELECT run_id, config_hash, status, dataset_json, factors_json, config_json, environment_json FROM runs"):
    runs.append({
        "run_id": row["run_id"],
        "config_hash": row["config_hash"],
        "status": row["status"],
        "dataset": json.loads(row["dataset_json"]),
        "factors": json.loads(row["factors_json"]),
        "config": json.loads(row["config_json"]),
        "environment": json.loads(row["environment_json"]),
    })
qmetrics = collections.defaultdict(lambda: collections.defaultdict(dict))
for row in con.execute("SELECT run_id, qid, metric, value FROM metrics"):
    qmetrics[row["run_id"]][row["qid"]][row["metric"]] = row["value"]

archive_runs = {}
for mod, items in archive["modules"].items():
    for item in items:
        archive_runs[item["run_id"]] = item

def pct(values, p):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    k = max(0, min(len(values) - 1, math.ceil(p / 100 * len(values)) - 1))
    return values[k]

def fnum(x):
    return None if x is None else float(x)

def qget(q, key):
    return fnum(q.get(key))

def is_a(q):
    return (qget(q, "answer_f1") or 0.0) > 0.0

def is_r(q):
    v = qget(q, "evidence_recall")
    return v is not None and v >= 1.0

def is_c(q):
    v = qget(q, "context_precision")
    return v is not None and v >= 1.0

def is_s(q):
    v = qget(q, "state_accuracy")
    return v is not None and v >= 1.0

def rate(rows, fn):
    n = len(rows)
    k = sum(1 for x in rows if fn(x))
    return {"n": k, "denominator": n, "value": round(k / n, 4) if n else None}

def run_questions(run_id):
    return list(qmetrics[run_id].values())

def run_summary(run):
    item = archive_runs[run["run_id"]]
    m = dict(item["metrics"])
    p95 = m.pop("p95_seconds", None)
    out = {
        "run_id": run["run_id"],
        "candidate": run["factors"]["candidate"],
        "module": run["factors"]["module"],
        "seed": run["factors"]["seed"],
        "config_hash": run["config_hash"],
        "status": run["status"],
        "questions": item.get("n", len(run_questions(run["run_id"]))),
        "error_rate": item.get("error_rate", 0.0),
        "metrics": {k: round(float(v), 4) for k, v in m.items() if v is not None},
    }
    out["metrics"]["state_accuracy"] = None
    if run["factors"]["module"] == "K":
        # K metrics are store-level and repeated per question; seconds/p95 is not a per-query latency.
        out["metrics"]["p95_latency_ms"] = None
        out["metrics"]["tokens"] = None
        out["store_level"] = True
    else:
        out["metrics"]["p95_latency_ms"] = round(p95 * 1000, 3) if p95 is not None else None
    return out

def mean_metrics(items, keys):
    out = {}
    for key in keys:
        vals = [it["metrics"].get(key) for it in items if it["metrics"].get(key) is not None]
        out[key] = round(statistics.mean(vals), 4) if vals else None
    out["questions"] = sum(it["questions"] for it in items)
    out["error_rate"] = round(statistics.mean(it["error_rate"] for it in items), 4) if items else None
    return out

def candidate_groups(module):
    items = [run for run in runs if run["factors"]["module"] == module]
    groups = collections.OrderedDict()
    for run in items:
        groups.setdefault(run["factors"]["candidate"], []).append(run)
    return groups

def module_report(module):
    groups = candidate_groups(module)
    summaries = collections.OrderedDict()
    for candidate, rlist in groups.items():
        summaries[candidate] = [run_summary(r) for r in rlist]
    order = list(groups.keys())
    roles = {it["candidate"]: it["role"] for it in archive["modules"][module]}
    metric_keys = ["answer_f1", "evidence_recall", "ndcg", "context_precision", "tokens",
                   "p95_latency_ms", "field_completeness", "staleness", "contradiction_rate",
                   "update_correctness", "removed", "units", "graph_nodes", "graph_edges",
                   "redundancy", "candidates", "channels", "plan_nodes", "citations", "refused"]
    by_candidate = collections.OrderedDict()
    for candidate, items in summaries.items():
        by_candidate[candidate] = {"role": roles.get(candidate), "runs": len(items),
                                   "metrics": mean_metrics(items, metric_keys)}
    return groups, summaries, by_candidate

# conversion helpers
def conversion_block(module=None, candidate=None):
    rows = []
    for run in runs:
        if module and run["factors"]["module"] != module:
            continue
        if candidate and run["factors"]["candidate"] != candidate:
            continue
        for qid, q in qmetrics[run["run_id"]].items():
            rows.append(q)
    return rows

def conversion_summary(rows):
    ra = [q for q in rows if is_r(q)]
    ca = [q for q in rows if is_c(q)]
    sa = [q for q in rows if is_s(q)]
    return {
        "P(A)": rate(rows, is_a),
        "P(R)": rate(rows, is_r),
        "P(C)": rate(rows, is_c),
        "P(S)": rate(rows, is_s),
        "P(A|R=1)": rate(ra, is_a),
        "P(A|C=1)": rate(ca, is_a),
        "P(A|S=1)": rate(sa, is_a),
    }

if __name__ == "__main__":
    print("runs", len(runs))
    for mod in ["W", "S", "R", "M", "U", "K"]:
        groups, summaries, by_candidate = module_report(mod)
        print("\n##", mod)
        for c, m in by_candidate.items():
            print(c, m["role"], {k: m["metrics"][k] for k in ["answer_f1", "evidence_recall", "ndcg", "tokens", "p95_latency_ms", "staleness", "contradiction_rate", "update_correctness", "removed"]})
        print("conversion", conversion_summary(conversion_block(mod)))
    print("\noverall conversion", conversion_summary(conversion_block()))
    print("answer modules conversion", conversion_summary([q for run in runs if run["factors"]["module"] != "K" for q in qmetrics[run["run_id"]].values()]))
