"""Minimal analysis helpers for the S5 result store.

S5 only needs trustworthy aggregation: per-run means and a metric table.  The
statistical layer (bootstrap, LMM, interactions) belongs to a later session and
must read the same SQLite rows rather than re-parsing stdout.
"""
from __future__ import annotations

from typing import Any

from .store import ResultStore


def summarize(store: ResultStore, metric: str = "answer_f1") -> list[dict[str, Any]]:
    return store.summary(metric)


def metric_rows(store: ResultStore, metric: str = "answer_f1") -> list[dict[str, Any]]:
    return store.metrics(metric=metric)


def run_table(store: ResultStore, metric: str = "answer_f1") -> list[dict[str, Any]]:
    rows = store.summary(metric)
    return [
        {
            "run_id": row["run_id"],
            "spec_id": row["spec_id"],
            "design": row["design"],
            "config_hash": row["config_hash"],
            "status": row["status"],
            "n": row["n"],
            metric: round(row["mean"], 4) if row["mean"] is not None else None,
        }
        for row in rows
    ]
