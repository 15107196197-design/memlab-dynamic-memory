"""E2 coupling analysis: quality propagation, conversion and attribution.

S7a builds the analysis layer *before* S6 finishes.  It reads the same SQLite rows
as S5, so synthetic fixtures can test the math without a model; S7b then points it
at real S6 runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .store import ResultStore


@dataclass(frozen=True)
class Conversion:
    run_id: str
    gate: str
    gate_min: float
    outcome: str
    outcome_min: float
    n_total: int
    n_gated: int
    n_success: int
    conversion: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "gate": self.gate,
            "gate_min": self.gate_min,
            "outcome": self.outcome,
            "outcome_min": self.outcome_min,
            "n_total": self.n_total,
            "n_gated": self.n_gated,
            "n_success": self.n_success,
            "conversion": self.conversion,
        }


def question_metrics(store: ResultStore, run_id: str) -> dict[str, dict[str, float]]:
    """Per-question metric map: ``qid -> {metric: value}`` (null values skipped)."""
    out: dict[str, dict[str, float]] = {}
    for row in store.metrics(run_id=run_id):
        if row.get("value") is None:
            continue
        out.setdefault(str(row["qid"]), {})[str(row["metric"])] = float(row["value"])
    return out


def _by_question(store: ResultStore, run_id: str) -> dict[str, dict[str, float]]:
    return question_metrics(store, run_id)


def conversion(store: ResultStore, run_id: str, *, gate: str = "evidence_recall",
               gate_min: float = 1.0, outcome: str = "answer_f1",
               outcome_min: float = 0.0) -> Conversion:
    """P(outcome above threshold | gate above threshold) for one run.

    ``n_gated`` is the denominator, not all questions: the question is conditional.
    """
    values = _by_question(store, run_id)
    gated = [q for q, metrics in values.items() if metrics.get(gate) is not None and metrics[gate] >= gate_min]
    success = [q for q in gated if values[q].get(outcome) is not None and values[q][outcome] > outcome_min]
    return Conversion(
        run_id=run_id, gate=gate, gate_min=gate_min, outcome=outcome,
        outcome_min=outcome_min, n_total=len(values), n_gated=len(gated),
        n_success=len(success),
        conversion=round(len(success) / len(gated), 4) if gated else None,
    )


def conversion_table(store: ResultStore, *, gate: str = "evidence_recall",
                     gate_min: float = 1.0, outcome: str = "answer_f1") -> list[dict[str, Any]]:
    return [conversion(store, row["run_id"], gate=gate, gate_min=gate_min, outcome=outcome).to_dict()
            for row in store.runs()]


def _mean(store: ResultStore, run_id: str, metric: str) -> float | None:
    values = [float(row["value"]) for row in store.metrics(run_id=run_id, metric=metric)
              if row.get("value") is not None]
    return sum(values) / len(values) if values else None


def oracle_gap(store: ResultStore, system_run: str, oracle_run: str,
               metric: str = "answer_f1") -> dict[str, Any]:
    system = _mean(store, system_run, metric)
    oracle = _mean(store, oracle_run, metric)
    gap = None if system is None or oracle is None else round(oracle - system, 4)
    return {
        "metric": metric, "system_run": system_run, "oracle_run": oracle_run,
        "system": round(system, 4) if system is not None else None,
        "oracle": round(oracle, 4) if oracle is not None else None,
        "gap": gap,
    }


def _run_meta(store: ResultStore, run_id: str) -> dict[str, Any]:
    run = store.get_run(run_id) or {}
    factors = run.get("factors") or {}
    environment = run.get("environment") or {}
    return {"factors": factors, "environment": environment}


def group_metric(store: ResultStore, metric: str, *, factor: str = "module") -> list[dict[str, Any]]:
    """Group run means by a factor (run.factors[factor])."""
    groups: dict[str, list[float]] = {}
    for row in store.runs():
        meta = _run_meta(store, row["run_id"])
        key = meta["factors"].get(factor)
        if key is None:
            key = "unknown"
        value = _mean(store, row["run_id"], metric)
        if value is not None:
            groups.setdefault(str(key), []).append(value)
    return [{"group": key, "n": len(values), "mean": round(sum(values) / len(values), 4)}
            for key, values in sorted(groups.items())]


def eta_squared(groups: Sequence[Sequence[float]]) -> float | None:
    """One-way effect size; a cheap screen, not a replacement for LMM."""
    flat = [value for group in groups for value in group]
    if len(flat) < 2:
        return None
    overall = sum(flat) / len(flat)
    between = sum(len(group) * (sum(group) / len(group) - overall) ** 2 for group in groups if group)
    total = sum((value - overall) ** 2 for value in flat)
    return round(between / total, 4) if total else None


def llm_attribution(store: ResultStore, metric: str = "answer_f1") -> list[dict[str, Any]]:
    """Run means grouped by the configured LLM model/tier, for the LLM confound."""
    groups: dict[str, list[float]] = {}
    for row in store.runs():
        meta = _run_meta(store, row["run_id"])
        env = meta["environment"]
        llm = env.get("llm") if isinstance(env.get("llm"), Mapping) else {}
        key = str(llm.get("model") or env.get("llm_level") or "unknown")
        value = _mean(store, row["run_id"], metric)
        if value is not None:
            groups.setdefault(key, []).append(value)
    return [{"llm": key, "n": len(values), "mean": round(sum(values) / len(values), 4)}
            for key, values in sorted(groups.items())]


def bottleneck(store: ResultStore, run_id: str, *,
               gate: str = "evidence_recall", outcome: str = "answer_f1") -> dict[str, Any]:
    """Small diagnostic: is the gate or the use stage the likely bottleneck?"""
    conv = conversion(store, run_id, gate=gate, outcome=outcome)
    gate_mean = _mean(store, run_id, gate)
    outcome_mean = _mean(store, run_id, outcome)
    if conv.n_gated == 0:
        diagnosis = "no_gated_questions"
    elif conv.conversion is not None and conv.conversion < 0.5:
        diagnosis = "use_or_merge_bottleneck"
    elif gate_mean is not None and gate_mean < 0.5:
        diagnosis = "retrieval_bottleneck"
    else:
        diagnosis = "no_clear_bottleneck"
    return {
        "run_id": run_id, "gate_mean": gate_mean, "outcome_mean": outcome_mean,
        "conversion": conv.to_dict(), "diagnosis": diagnosis,
    }


# ---- S7b-A offline screen ------------------------------------------------
# The functions below add a descriptive, A-level screen on top of the existing
# conversion math.  They deliberately do not call a model, build an oracle run or
# label a module as causal: they only report P(outcome | gate) and how much data
# supports it.  S7b-B uses the same rows once real LLM metrics exist.

SCREEN_METRICS = (
    "answer_f1", "evidence_recall", "context_precision", "ndcg",
    "state_accuracy", "judge_accuracy", "tokens", "seconds",
)


def _mean_of(values: Iterable[float]) -> float | None:
    values = [float(value) for value in values]
    return round(sum(values) / len(values), 4) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def run_screen(store: ResultStore, run_id: str, *,
               gate: str = "evidence_recall", gate_min: float = 1.0,
               outcome: str = "answer_f1", outcome_min: float = 0.0) -> dict[str, Any]:
    """One run's descriptive gate → outcome screen.

    ``p_outcome`` is unconditional; ``p_outcome_given_gate`` conditions on the
    gate, so the denominator is ``n_gated`` rather than all questions.  ``lift`` is
    their difference and must not be read as a causal effect.
    """
    run = store.get_run(run_id) or {}
    factors = run.get("factors") or {}
    questions = question_metrics(store, run_id)
    observed = {qid: values for qid, values in questions.items() if outcome in values}
    gated = {qid: values for qid, values in observed.items()
             if values.get(gate) is not None and values[gate] >= gate_min}
    success = {qid for qid, values in gated.items() if values[outcome] > outcome_min}
    outcome_success = sum(1 for values in observed.values() if values[outcome] > outcome_min)
    p_outcome = _rate(outcome_success, len(observed))
    p_given_gate = _rate(len(success), len(gated))
    if not observed:
        status = "outcome_not_recorded"
    elif not gated:
        status = "no_gated_questions"
    else:
        status = "ok"
    return {
        "run_id": run_id,
        "module": factors.get("module"),
        "candidate": factors.get("candidate"),
        "seed": factors.get("seed"),
        "n_questions": len(questions),
        "n_observed": len(observed),
        "n_gated": len(gated),
        "n_success": len(success),
        "n_outcome_success": outcome_success,
        "p_gate": _rate(len(gated), len(observed)),
        "p_outcome": p_outcome,
        "p_outcome_given_gate": p_given_gate,
        "lift": (round(p_given_gate - p_outcome, 4)
                 if p_given_gate is not None and p_outcome is not None else None),
        "mean_outcome": _mean_of(values[outcome] for values in observed.values()),
        "mean_outcome_gated": _mean_of(values[outcome] for values in gated.values()),
        "mean_gate": _mean_of(values[gate] for values in observed.values()
                              if values.get(gate) is not None),
        "status": status,
    }


def aggregate_screens(rows: Sequence[Mapping[str, Any]], *, key: str) -> list[dict[str, Any]]:
    """Pool run screens by a factor label, keeping both pooled and run-level views."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        label = row.get(key)
        groups.setdefault(str(label) if label is not None else "unknown", []).append(row)
    out: list[dict[str, Any]] = []
    for label, group in sorted(groups.items()):
        usable = [row for row in group if row.get("status") == "ok"]
        n_observed = sum(int(row.get("n_observed") or 0) for row in group)
        n_gated = sum(int(row.get("n_gated") or 0) for row in group)
        n_success = sum(int(row.get("n_success") or 0) for row in group)
        n_outcome_success = sum(int(row.get("n_outcome_success") or 0) for row in group)
        conversions = [row["p_outcome_given_gate"] for row in usable
                       if row.get("p_outcome_given_gate") is not None]
        lifts = [row["lift"] for row in usable if row.get("lift") is not None]
        out.append({
            key: label,
            "runs": len(group),
            "runs_with_gate": len(usable),
            "n_observed": n_observed,
            "n_gated": n_gated,
            "p_gate": _rate(n_gated, n_observed),
            "p_outcome": _rate(n_outcome_success, n_observed),
            "p_outcome_given_gate": _rate(n_success, n_gated),
            "conversion_run_mean": _mean_of(conversions),
            "conversion_run_min": min(conversions) if conversions else None,
            "conversion_run_max": max(conversions) if conversions else None,
            "lift_mean": _mean_of(lifts),
        })
    return out


def gate_availability(store: ResultStore, metrics: Sequence[str] = SCREEN_METRICS) -> list[dict[str, Any]]:
    """Which screen metrics are actually recorded, and for how many runs."""
    out: list[dict[str, Any]] = []
    for metric in metrics:
        rows = store.metrics(metric=metric)
        observed = sum(1 for row in rows if row.get("value") is not None)
        out.append({
            "metric": metric,
            "rows": len(rows),
            "observed": observed,
            "runs": len({row["run_id"] for row in rows}),
            "status": "ok" if observed else "missing",
        })
    return out


def screen(store: ResultStore, *, gate: str = "evidence_recall", gate_min: float = 1.0,
           outcome: str = "answer_f1", outcome_min: float = 0.0) -> dict[str, Any]:
    """Descriptive S7b-A payload over every run in ``store``.

    No Oracle gap and no LLM attribution are produced here; both need runs this
    database does not contain.  The ``oracle_gap``/``llm_attribution`` statuses
    say so instead of substituting a proxy.
    """
    runs = [run_screen(store, row["run_id"], gate=gate, gate_min=gate_min,
                       outcome=outcome, outcome_min=outcome_min)
            for row in store.runs()]
    models = sorted({
        str(((store.get_run(row["run_id"]) or {}).get("environment") or {})
            .get("llm", {}).get("model") or "unknown")
        for row in store.runs()
    })
    limits = [
        "answer_f1 is the offline extractive baseline, not an LLM answer",
        "environment.llm metadata names the intended model; the runs were offline (notes=offline_extractive)",
        "no Oracle run: oracle_gap is not_available rather than a proxy",
        "state_accuracy/judge_accuracy are not recorded: P(A|S=1) cannot be computed",
        "two seeds only; run-level min/max is dispersion, not a confidence interval",
    ]
    return {
        "schema": "memlab/s7b-a@1",
        "level": "A-offline-descriptive",
        "gate": {"metric": gate, "min": gate_min},
        "outcome": {"metric": outcome, "min": outcome_min},
        "runs": runs,
        "by_module": aggregate_screens(runs, key="module"),
        "by_candidate": aggregate_screens(runs, key="candidate"),
        "by_seed": aggregate_screens(runs, key="seed"),
        "gate_availability": gate_availability(store),
        "oracle_gap": {
            "status": "not_available",
            "reason": "No Oracle run and no retrieval-ceiling metric are stored in this DB; building an Oracle executor/run is S7b-B work.",
        },
        "llm_attribution": {
            "status": "not_available",
            "reason": "S6 runs are offline extractive; one environment label is not an LLM comparison.",
            "environment_models": models,
        },
        "limits": limits,
    }
