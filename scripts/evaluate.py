"""Run the course evaluation and write results to eval/.

    python scripts/evaluate.py retrieval --split test           # Recall@K, all answerable questions
    python scripts/evaluate.py qa --split test --limit 60       # answer F1 for the four methods
    python scripts/evaluate.py state                            # state-judgement accuracy
    python scripts/evaluate.py summary                          # merge into eval/results.json

QA and state runs are resumable: rows already present in the output file are skipped,
so several processes (e.g. one per GPU, via --samples and --output) can share the work.
"""
import argparse
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memwb import config, dataset, evaluation, pipeline  # noqa: E402


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=dict), encoding="utf-8")
    tmp.replace(path)


def read_rows(path):
    return json.loads(path.read_text(encoding="utf-8"))["rows"] if path.exists() else []


def meta(args):
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "answer_model": config.answer_model(),
            "embedding_model": config.embed_model(), "split": getattr(args, "split", None)}


def run_retrieval(args):
    ids = args.samples or config.SPLIT[args.split]
    result = evaluation.evaluate_retrieval(ids)
    write(config.EVAL_DIR / f"retrieval-{args.split}.json", {**meta(args), "samples": ids, **result})
    print(json.dumps(result["summary"], indent=1))


def run_qa(args):
    ids = args.samples or config.SPLIT[args.split]
    path = Path(args.output) if args.output else config.EVAL_DIR / f"qa-{args.split}.json"
    rows = read_rows(path)
    done = {(r["sample"], r["qa_index"], r["method"]) for r in rows if "error" not in r or not args.retry_errors}
    rows = [r for r in rows if (r["sample"], r["qa_index"], r["method"]) in done]
    store = dataset.store()
    for sid in ids:
        for index, qa in evaluation.stratified(store.get(sid)["qa"], args.limit):
            for method in args.methods:
                if (sid, index, method) in done:
                    continue
                row = evaluation.qa_row(sid, index, qa, method, args.k)
                rows.append(row)
                write(path, {**meta(args), "limit_per_conversation": args.limit, "k": args.k, "rows": rows})
                print(json.dumps({k: row.get(k) for k in ("sample", "qa_index", "method", "answer_f1", "evidence_recall", "seconds", "error")}), flush=True)
    print(json.dumps(evaluation.summarize_qa(rows), indent=1))


def run_state(args):
    path = Path(args.output) if args.output else config.EVAL_DIR / "state-results.json"
    rows = read_rows(path)
    done = {(r["id"], r["method"]) for r in rows if "error" not in r}
    rows = [r for r in rows if (r["id"], r["method"]) in done]
    for item in evaluation.load_state_benchmark():
        if args.samples and item["sample"] not in args.samples:
            continue
        for method in args.methods:
            if (item["id"], method) in done:
                continue
            try:
                row = evaluation.evaluate_state_item(item, method)
            except Exception as exc:  # noqa: BLE001
                row = {"id": item["id"], "sample": item["sample"], "method": method, "error": f"{type(exc).__name__}: {exc}"}
            rows.append(row)
            write(path, {**meta(args), "rows": rows})
            print(json.dumps({k: row.get(k) for k in ("id", "method", "valid_set_exact", "answer_f1", "error")}), flush=True)
    print(json.dumps(evaluation.summarize_state(rows), indent=1))


def run_summary(args):
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "answer_model": config.answer_model(),
           "embedding_model": config.embed_model(), "split": config.SPLIT}
    for split in ("development", "test"):
        path = config.EVAL_DIR / f"retrieval-{split}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            out.setdefault("retrieval", {})[split] = {k: data[k] for k in ("questions", "summary", "by_category", "samples")}
        merged = {}
        for f in sorted(glob.glob(str(config.EVAL_DIR / f"qa-{split}*.json"))):
            for r in read_rows(Path(f)):  # several runs may cover the same question; a success wins over an error
                key = (r["sample"], r["qa_index"], r["method"])
                if key not in merged or ("error" in merged[key] and "error" not in r):
                    merged[key] = r
        qa_rows = list(merged.values())
        if qa_rows:
            out.setdefault("qa", {})[split] = {"questions": len({(r["sample"], r["qa_index"]) for r in qa_rows}),
                                               "summary": evaluation.summarize_qa(qa_rows)}
    state_rows = [r for f in sorted(glob.glob(str(config.EVAL_DIR / "state-results*.json"))) for r in read_rows(Path(f))]
    if state_rows:
        items = evaluation.load_state_benchmark()
        out["state"] = {"items": len(items), "annotation": json.loads((config.EVAL_DIR / "state_benchmark.json").read_text(encoding="utf-8"))["annotation"],
                        "by_split": {split: evaluation.summarize_state([r for r in state_rows if config.split_of(r["sample"]) == split]) for split in ("development", "test")},
                        "overall": evaluation.summarize_state(state_rows)}
    write(config.EVAL_DIR / "results.json", out)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("retrieval", "qa", "state", "summary"):
        p = sub.add_parser(name)
        p.add_argument("--split", choices=["development", "test"], default="test")
        p.add_argument("--samples", nargs="+")
        p.add_argument("--output")
        p.add_argument("--limit", type=int, default=60, help="questions per conversation, stratified by category; 0 = all")
        p.add_argument("--k", type=int, default=15)
        p.add_argument("--methods", nargs="+", choices=pipeline.METHODS, default=list(pipeline.METHODS))
        p.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    {"retrieval": run_retrieval, "qa": run_qa, "state": run_state, "summary": run_summary}[args.command](args)


if __name__ == "__main__":
    main()
