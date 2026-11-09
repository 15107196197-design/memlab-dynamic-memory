"""SQLite result store for experiment runs and per-question metrics.

One row per (run_id, qid, metric) keeps resume, sharding and later analysis
simple.  The store is deliberately queryable, not a pile of JSON files: analysis
must not depend on re-reading stdout.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .compiler import RunPlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    spec_id TEXT,
    design TEXT,
    config_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    config_json TEXT,
    environment_json TEXT,
    dataset_json TEXT,
    factors_json TEXT,
    notes_json TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    run_id TEXT NOT NULL,
    qid TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    meta_json TEXT,
    PRIMARY KEY (run_id, qid, metric)
);
CREATE TABLE IF NOT EXISTS artifacts (
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    hash TEXT,
    PRIMARY KEY (run_id, kind, path)
);
CREATE INDEX IF NOT EXISTS metrics_run_metric ON metrics(run_id, metric);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class ResultStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ResultStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ runs
    def upsert_run(self, plan: RunPlan | Mapping[str, Any], status: str | None = None) -> None:
        data = plan.to_dict() if isinstance(plan, RunPlan) else dict(plan)
        run_id = data["run_id"]
        now = _now()
        existing = self._conn.execute("SELECT created_at FROM runs WHERE run_id=?", (run_id,)).fetchone()
        created = existing["created_at"] if existing else now
        with self._lock:
            self._conn.execute(
                """INSERT INTO runs
                   (run_id, spec_id, design, config_hash, status, created_at, updated_at,
                    config_json, environment_json, dataset_json, factors_json, notes_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id) DO UPDATE SET
                     status=excluded.status, updated_at=excluded.updated_at,
                     config_json=excluded.config_json, environment_json=excluded.environment_json,
                     dataset_json=excluded.dataset_json, factors_json=excluded.factors_json,
                     notes_json=excluded.notes_json""",
                (
                    run_id, data.get("spec_id"), data.get("design"), data.get("config_hash"),
                    status or data.get("status") or "pending", created, now,
                    json.dumps(data.get("effective_config") or data.get("config"), ensure_ascii=False),
                    json.dumps(data.get("environment") or {}, ensure_ascii=False),
                    json.dumps(data.get("dataset") or {}, ensure_ascii=False),
                    json.dumps(data.get("factors") or {}, ensure_ascii=False),
                    json.dumps(data.get("notes") or [], ensure_ascii=False),
                ),
            )
            self._conn.commit()

    def set_status(self, run_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE runs SET status=?, updated_at=? WHERE run_id=?", (status, _now(), run_id))
            self._conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        for key in ("config_json", "environment_json", "dataset_json", "factors_json", "notes_json"):
            if data.get(key):
                try:
                    data[key[:-5]] = json.loads(data[key])
                except json.JSONDecodeError:
                    data[key[:-5]] = None
        return data

    def runs(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._conn.execute("SELECT * FROM runs ORDER BY created_at, run_id")]

    # --------------------------------------------------------------- metrics
    def add_metric(self, run_id: str, qid: str, metric: str, value: float | None,
                   meta: Mapping[str, Any] | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO metrics(run_id,qid,metric,value,meta_json) VALUES (?,?,?,?,?)",
                (run_id, qid, metric, value, json.dumps(dict(meta or {}), ensure_ascii=False)),
            )
            self._conn.commit()

    def add_metrics(self, run_id: str, qid: str, values: Mapping[str, Any],
                    meta: Mapping[str, Any] | None = None) -> None:
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            self.add_metric(run_id, qid, str(name), float(value), meta)

    def completed(self, run_id: str, qid: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM metrics WHERE run_id=? AND qid=? LIMIT 1", (run_id, qid)
        ).fetchone()
        return row is not None

    def metrics(self, run_id: str | None = None, metric: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM metrics"
        clauses, args = [], []
        if run_id is not None:
            clauses.append("run_id=?")
            args.append(run_id)
        if metric is not None:
            clauses.append("metric=?")
            args.append(metric)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        return [dict(row) for row in self._conn.execute(query + " ORDER BY run_id,qid,metric", args)]

    def summary(self, metric: str = "answer_f1") -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT r.run_id, r.spec_id, r.design, r.config_hash, r.status,
                      COUNT(m.value) AS n, AVG(m.value) AS mean,
                      MIN(m.value) AS min, MAX(m.value) AS max
               FROM runs r LEFT JOIN metrics m ON m.run_id=r.run_id AND m.metric=?
               GROUP BY r.run_id ORDER BY mean DESC""",
            (metric,),
        )
        return [dict(row) for row in rows]

    # ------------------------------------------------------------- artifacts
    def add_artifact(self, run_id: str, kind: str, path: str, hash_value: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO artifacts(run_id,kind,path,hash) VALUES (?,?,?,?)",
                (run_id, kind, str(path), hash_value),
            )
            self._conn.commit()
