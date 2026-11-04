"""Evaluation: answer F1, evidence Recall@K and dynamic state-judgement accuracy.

Answer F1 follows the LoCoMo protocol (normalise, remove articles, token F1;
multi-hop answers are split on commas; open-domain answers use the first ';' part),
with a light suffix stemmer instead of NLTK's Porter stemmer.
"""
import collections
import json
import re
import statistics
import string
import time

from . import config, dataset, llm, memory, pipeline, retrieval

CATEGORY = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}
RECALL_KS = (5, 10, 15, 20, 30)


# ----------------------------------------------------------------------------- metrics

def _stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def normalize(text):
    text = str(text).lower().replace(",", " ")
    text = "".join(c for c in text if c not in string.punctuation)
    text = re.sub(r"\b(a|an|the|and)\b", " ", text)
    return [_stem(w) for w in text.split()]


def token_f1(prediction, gold):
    pred, ref = normalize(prediction), normalize(gold)
    if not pred or not ref:
        return float(pred == ref)
    overlap = sum((collections.Counter(pred) & collections.Counter(ref)).values())
    if not overlap:
        return 0.0
    precision, recall = overlap / len(pred), overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def answer_f1(prediction, gold, category):
    gold = str(gold)
    if category == 3:
        gold = gold.split(";")[0]
    if category == 1:
        preds = [p for p in str(prediction).split(",") if p.strip()] or [str(prediction)]
        golds = [g for g in gold.split(",") if g.strip()] or [gold]
        return statistics.mean(max(token_f1(p, g) for p in preds) for g in golds)
    return token_f1(prediction, gold)


def evidence_turns(qa):
    return sorted({t for ref in qa.get("evidence", []) for t in re.findall(r"D\d+:\d+", str(ref))})


def recall(gold_turns, retrieved_turns):
    if not gold_turns:
        return None
    return len(set(gold_turns) & set(retrieved_turns)) / len(gold_turns)


def answerable(qa_list):
    """(index, qa) pairs that have a reference answer; adversarial category 5 is excluded."""
    return [(i, q) for i, q in enumerate(qa_list) if q.get("category") in (1, 2, 3, 4) and q.get("answer") is not None]


def stratified(qa_list, limit):
    """Cycle through categories 1-4 in source order until `limit` questions are chosen (0 = all)."""
    eligible = answerable(qa_list)
    if not limit:
        return eligible
    groups = {c: [x for x in eligible if x[1]["category"] == c] for c in (1, 2, 3, 4)}
    chosen = []
    while len(chosen) < limit and any(groups.values()):
        for c in (1, 2, 3, 4):
            if groups[c] and len(chosen) < limit:
                chosen.append(groups[c].pop(0))
    return sorted(chosen)


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 4) if values else None


# ----------------------------------------------------------------------------- retrieval

def evaluate_retrieval(sample_ids, log=print):
    """Evidence Recall@K of each retriever over all answerable questions (no LLM calls)."""
    rows = []
    store = dataset.store()
    for sid in sample_ids:
        sample = store.get(sid)
        turns, fact_list = memory.build(sample)
        facts = pipeline.facts_as_of(fact_list, {m["memory_id"] for m in turns})
        qas = answerable(sample["qa"])
        vectors = llm.embed([q["question"] for _, q in qas])
        top = max(RECALL_KS)
        for (index, qa), qvec in zip(qas, vectors):
            gold = evidence_turns(qa)
            if not gold:
                continue
            ranked = {
                "bm25": retrieval.bm25(qa["question"], turns, top, fact_list),
                "vector": retrieval.vector(qa["question"], turns, top, qvec),
                "hybrid": retrieval.hybrid(qa["question"], turns, top, fact_list, qvec),
            }
            row = {"sample": sid, "qa_index": index, "category": qa["category"], "gold": gold}
            for name, items in ranked.items():
                order = [m["source"]["turn"] for m in items]
                for k in RECALL_KS:
                    row[f"{name}@{k}"] = recall(gold, order[:k])
            # Dynamic candidates = hybrid top-15 plus memory-graph expansion (variable size).
            base = ranked["hybrid"][:15]
            expanded = base + pipeline.graph_expand(base, turns, facts, 8)
            row["dynamic_candidates"] = recall(gold, [m["source"]["turn"] for m in expanded])
            row["dynamic_candidate_count"] = len(expanded)
            # Same budget without the graph: plain hybrid ranking cut at the same size.
            row["hybrid@same_size"] = recall(gold, [m["source"]["turn"] for m in ranked["hybrid"][:len(expanded)]])
            rows.append(row)
        log(json.dumps({"sample": sid, "questions": len(rows)}))
    summary = {}
    for name in ("bm25", "vector", "hybrid"):
        summary[name] = {f"@{k}": mean(r[f"{name}@{k}"] for r in rows) for k in RECALL_KS}
    summary["dynamic_candidates"] = {"recall": mean(r["dynamic_candidates"] for r in rows),
                                     "mean_candidates": mean(r["dynamic_candidate_count"] for r in rows),
                                     "hybrid@same_size": mean(r["hybrid@same_size"] for r in rows)}
    by_cat = {}
    for c in (1, 2, 3, 4):
        sub = [r for r in rows if r["category"] == c]
        by_cat[CATEGORY[c]] = {"n": len(sub), **{f"{n}@15": mean(r[f"{n}@15"] for r in sub) for n in ("bm25", "vector", "hybrid")},
                               "dynamic_candidates": mean(r["dynamic_candidates"] for r in sub)}
    return {"questions": len(rows), "summary": summary, "by_category": by_cat, "rows": rows}


# ----------------------------------------------------------------------------- QA

def qa_row(sample_id, index, qa, method, k):
    row = {"sample": sample_id, "qa_index": index, "category": qa["category"], "method": method,
           "question": qa["question"], "gold_answer": qa["answer"], "gold_evidence": evidence_turns(qa)}
    started = time.perf_counter()
    try:
        result = pipeline.answer(sample_id, qa["question"], method, k)
        row.update(prediction=result["answer"], answer_f1=round(answer_f1(result["answer"], qa["answer"], qa["category"]), 4),
                   evidence_recall=None if method == "full" else recall(row["gold_evidence"], result["retrieved_turns"]),
                   retrieved_count=len(result["retrieved_turns"]))
        if method == "dynamic":
            states = {m["id"]: m["state"] for m in result["memories"]}
            row["states"] = collections.Counter(states.values())
            row["relations"] = collections.Counter(r["type"] for r in result["relations"])
    except Exception as exc:  # noqa: BLE001 - failures are recorded and scored as 0
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


def summarize_qa(rows):
    out = {}
    for method in pipeline.METHODS:
        sub = [r for r in rows if r["method"] == method]
        if not sub:
            continue
        ok = [r for r in sub if "error" not in r]
        out[method] = {
            "attempted": len(sub), "errors": len(sub) - len(ok),
            "f1": mean([r.get("answer_f1", 0.0) for r in sub]),  # errors count as 0
            "f1_success_only": mean([r["answer_f1"] for r in ok]),
            "evidence_recall": mean([r.get("evidence_recall") for r in ok]),
            "mean_seconds": mean([r["seconds"] for r in sub]),
            "by_category": {CATEGORY[c]: mean([r.get("answer_f1", 0.0) for r in sub if r["category"] == c]) for c in (1, 2, 3, 4)},
        }
    return out


# ----------------------------------------------------------------------------- state judgement

def _pair_type(relations, a, b):
    for r in relations:
        if {r["from_id"], r["to_id"]} == {a, b}:
            return r["type"]
    return "NONE"


def _linked(relations, a, b, allowed):
    """True when a chain of relations of allowed types leads from a to b (in either direction).

    The model often links versions through intermediate turns (D2:8 -> D8:9 -> D13:1), which
    still establishes the annotated relation between the two endpoints."""
    for start, goal in ((a, b), (b, a)):
        frontier, seen = [start], {start}
        while frontier:
            node = frontier.pop()
            for r in relations:
                if r["from_id"] == node and r["type"] in allowed and r["to_id"] not in seen:
                    if r["to_id"] == goal:
                        return True
                    seen.add(r["to_id"])
                    frontier.append(r["to_id"])
    return False


def evaluate_state_item(item, method):
    """Score one annotated state-change question.

    Gold labels name turns (e.g. D19:1). For the dynamic method the predicted state is the
    model's state for that turn; baselines that do no state judgement treat every retrieved
    memory as ACTIVE. A labelled memory that was not retrieved counts as MISSING (wrong).
    """
    sid = item["sample"]
    prefix = sid.replace("-", "") + "_"
    to_id = lambda turn: prefix + turn.replace(":", "_")  # noqa: E731
    result = pipeline.answer(sid, item["question"], method, 15, item.get("as_of"))
    retrieved = {m["memory_id"] for m in result.get("retrieved", [])}
    if method == "dynamic":
        predicted = {m["id"]: m["state"] for m in result["memories"]}
        relations = result["relations"]
    else:
        predicted = {mid: "ACTIVE" for mid in retrieved}
        relations = []
    memories = []
    for turn, gold in item["memories"].items():
        pred = predicted.get(to_id(turn), "MISSING")
        memories.append({"turn": turn, "gold": gold, "predicted": pred, "retrieved": to_id(turn) in retrieved, "correct": pred == gold})
    rels = []
    for a, b, gold in item["relations"]:
        pred = _pair_type(relations, to_id(a), to_id(b))
        allowed = gold if isinstance(gold, list) else [gold]  # some pairs accept two defensible types
        direct = pred in allowed
        rels.append({"from": a, "to": b, "gold": gold, "predicted": pred, "correct_direct": direct,
                     "correct": direct or _linked(relations, to_id(a), to_id(b), set(allowed))})
    gold_valid = {t for t, s in item["memories"].items() if s == "ACTIVE"}
    pred_valid = {m["turn"] for m in memories if m["predicted"] == "ACTIVE"}
    return {
        "id": item["id"], "sample": sid, "method": method, "question": item["question"],
        "gold_answer": item.get("answer"), "prediction": result["answer"],
        "answer_f1": round(token_f1(result["answer"], item["answer"]), 4) if item.get("answer") else None,
        "memories": memories, "relations": rels,
        "predicted_relations": [{k: r.get(k) for k in ("from_id", "to_id", "type", "reason", "support")} for r in relations],
        "valid_set_exact": gold_valid == pred_valid,
        "evidence_recall": sum(m["retrieved"] for m in memories) / len(memories),
    }


def summarize_state(rows):
    out = {}
    for method in pipeline.METHODS:
        sub = [r for r in rows if r["method"] == method and "error" not in r]
        if not sub:
            continue
        mems = [m for r in sub for m in r["memories"]]
        rels = [x for r in sub for x in r["relations"]]
        out[method] = {
            "items": len(sub), "errors": sum(1 for r in rows if r["method"] == method and "error" in r),
            "memory_state_accuracy": mean([float(m["correct"]) for m in mems]),
            "labelled_memories": len(mems),
            "relation_accuracy": mean([float(x["correct"]) for x in rels]) if method == "dynamic" else None,
            "relation_accuracy_direct": mean([float(x.get("correct_direct", x["correct"])) for x in rels]) if method == "dynamic" else None,
            "labelled_relations": len(rels),
            "valid_memory_exact_match": mean([float(r["valid_set_exact"]) for r in sub]),
            "evidence_recall": mean([r["evidence_recall"] for r in sub]),
            "answer_f1": mean([r["answer_f1"] for r in sub]),
        }
    return out


def load_state_benchmark():
    path = config.EVAL_DIR / "state_benchmark.json"
    return json.loads(path.read_text(encoding="utf-8"))["items"]
