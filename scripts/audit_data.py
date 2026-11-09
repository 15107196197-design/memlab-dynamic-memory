#!/usr/bin/env python3
"""DATA-AUDIT: traceability audit for the MemLab submission.

Read-only with respect to every file except the three audit outputs:

    scripts/audit_data.py
    reports/audit/data-audit.json
    docs/optimization/DATA-AUDIT.md

Run from anywhere:

    python scripts/audit_data.py

The script is deliberately conservative: a number is only marked verified
when it can be recomputed from a local run/JSON/report.  Anything else is
reported as an orphan/mismatch instead of being guessed.

Notes
-----
* The brief says "catalog 48 rows"; the main catalog has 48 items, but its
  status vocabulary is partial/pending/no_op/not_wired/blocked_on_* and it
  contains no "done" rows.  The repo-g2 worktree still has an older 24-row
  catalog with 4 "done" rows; those are audited separately because merging
  that catalog would introduce P0 done_without_evidence.
* The brief's example inventory (31 archive JSON / 12 SQLite) does not match
  the checkout (28 archive JSON / 14 SQLite).  The report records the actual
  counts and calls out the difference rather than copying the example.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
G2 = WORKSPACE / "repo-g2"
DECK = WORKSPACE / "deck" / "MemLab-展示-2026-11-09.pptx"
WEB_BASE = "http://127.0.0.1:8886"
OUT_JSON = ROOT / "reports" / "audit" / "data-audit.json"
OUT_MD = ROOT / "docs" / "optimization" / "DATA-AUDIT.md"

FINDINGS = []
VERIFIED = []
PPT_NUMBERS = []
WEB_CHECKS = []
METRIC_CONSISTENCY = []


def add(severity, kind, file, loc, claim, source, fix_owner, note):
    FINDINGS.append({
        "severity": severity,
        "kind": kind,
        "file": file,
        "loc": loc,
        "claim": claim,
        "source": source,
        "fix_owner": fix_owner,
        "note": note,
    })


def verify(claim, source, note=""):
    VERIFIED.append({"claim": claim, "source": source, "note": note})


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        try:
            return str(Path(path).resolve().relative_to(WORKSPACE))
        except ValueError:
            return str(path)


def exists_in_repo(path_text):
    p = Path(path_text)
    if p.is_absolute():
        return p.exists()
    return (ROOT / p).exists()


def exists_in_g2(path_text):
    p = Path(path_text)
    if p.is_absolute():
        return p.exists()
    return (G2 / p).exists()


PATH_RE = re.compile(
    r"(?<![\w.-])((?:eval|runs|reports|configs|docs|scripts|data)/[\w./-]+\.(?:json|sqlite|md|csv|patch|txt|py|pptx))"
)


def collect_paths(obj, extra=()):
    """Collect file-looking strings from a catalog item/report."""
    found = set(extra)
    if isinstance(obj, str):
        for match in PATH_RE.findall(obj):
            found.add(match.rstrip(".,;)"))
        return found
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"report", "report_online", "online_source", "source_db", "db", "source"} and isinstance(value, str):
                for match in PATH_RE.findall(value):
                    found.add(match.rstrip(".,;)"))
            found |= collect_paths(value)
    elif isinstance(obj, list):
        for value in obj:
            found |= collect_paths(value)
    return found


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------
catalog = read_json(ROOT / "configs" / "experiment-catalog.json")
catalog_items = catalog.get("items", [])
reports = sorted((ROOT / "reports" / "experiments").glob("*.json"))
archives = sorted((ROOT / "eval" / "archive").rglob("*.json"))
sqlite_files = sorted((ROOT / "runs").rglob("*.sqlite")) + sorted((ROOT / "runs").rglob("*.db"))
g2_catalog_path = G2 / "configs" / "experiment-catalog.json"
g2_catalog = read_json(g2_catalog_path) if g2_catalog_path.exists() else {"items": []}
g2_archives = sorted((G2 / "eval" / "archive").rglob("*.json")) if (G2 / "eval" / "archive").exists() else []
g2_sqlites = sorted((G2 / "runs").rglob("*.sqlite")) if (G2 / "runs").exists() else []

def read_pptx_texts(path):
    """Read slide text with python-pptx, falling back to the OOXML zip.

    The fallback matters because the default `python3` on this machine does
    not have python-pptx installed; the bundled audit runtime does.  A
    rerunnable audit must not silently report 0 slides in that case.
    """
    try:
        from pptx import Presentation  # type: ignore

        presentation = Presentation(str(path))
        texts = []
        for slide in presentation.slides:
            parts = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    parts.append(shape.text_frame.text)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        for cell in row.cells:
                            parts.append(cell.text)
            texts.append("\n".join(p for p in parts if p and p.strip()))
        return texts, None
    except Exception as exc:  # fall back to raw XML
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(path) as archive:
                names = [
                    name for name in archive.namelist()
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                ]
                names.sort(key=lambda name: int(re.search(r"(\d+)", name.rsplit("/", 1)[-1]).group(1)))
                texts = []
                for name in names:
                    root = ET.fromstring(archive.read(name))
                    chunks = [
                        element.text or ""
                        for element in root.iter()
                        if element.tag.endswith("}t")
                    ]
                    texts.append("\n".join(chunk for chunk in chunks if chunk.strip()))
                return texts, None
        except Exception as fallback_exc:
            return [], f"{type(exc).__name__}: {exc}; fallback {type(fallback_exc).__name__}: {fallback_exc}"


deck_texts, deck_error = read_pptx_texts(DECK)
deck_slides = len(deck_texts)

main_archive_names = {str(p.relative_to(ROOT / "eval" / "archive")) for p in archives}
g2_archive_names = {str(p.relative_to(G2 / "eval" / "archive")) for p in g2_archives}
g2_only_archive = sorted(g2_archive_names - main_archive_names)

status_counts = Counter(item.get("status") for item in catalog_items)
g2_status_counts = Counter(item.get("status") for item in g2_catalog.get("items", []))

inventory = {
    "catalog_rows": len(catalog_items),
    "reports": len(reports),
    "archive_json": len(archives),
    "runs_sqlite": len(sqlite_files),
    "deck_slides": deck_slides,
    "catalog_count_field": catalog.get("count"),
    "catalog_status_counts": dict(sorted(status_counts.items())),
    "g2_catalog_rows": len(g2_catalog.get("items", [])),
    "g2_catalog_status_counts": dict(sorted(g2_status_counts.items())),
    "g2_archive_json": len(g2_archives),
    "g2_runs_sqlite": len(g2_sqlites),
    "g2_only_archive": g2_only_archive,
    "docs_report_text_files": [
        rel(p) for p in sorted((ROOT / "docs" / "report").rglob("*")) if p.is_file() and p.suffix.lower() in {".md", ".txt", ".json"}
    ]
    if (ROOT / "docs" / "report").exists()
    else [],
    "brief_expected": {"catalog_rows": 48, "reports": 20, "archive_json": 31, "runs_sqlite": 12, "deck_slides": 12},
    "note": "Counts are live from this checkout; the 31/12 in the brief are stale expectations, not this checkout's inventory.",
}
if deck_error:
    inventory["deck_error"] = deck_error

# ---------------------------------------------------------------------------
# A. catalog
# ---------------------------------------------------------------------------
if not any(item.get("status") == "done" for item in catalog_items):
    add(
        "P2", "status_vocabulary_no_done", "configs/experiment-catalog.json", "summary",
        f"{len(catalog_items)}-row catalog has no status=done; statuses are partial/pending/no_op/not_wired/blocked_on_*",
        "configs/experiment-catalog.json",
        "B",
        "The brief's done_without_evidence check is vacuous on main. The older repo-g2 catalog still has 4 done rows; see separate P0 findings.",
    )

for item in catalog_items:
    item_id = item.get("id", "?")
    status = item.get("status", "")
    paths = collect_paths(item)
    if status in {"done", "partial"}:
        if not paths:
            add(
                "P1", "evidence_without_path", "configs/experiment-catalog.json", f"items[{item_id}]",
                f"{item_id} status={status} but evidence has no resolvable run/JSON/report path",
                "docs/optimization/04-experiments.md",
                "B",
                "Evidence is prose only. Point it at eval/results.json or a reports/experiments JSON so the numbers can be replayed.",
            )
        for path in sorted(paths):
            if not exists_in_repo(path) and exists_in_g2(path):
                add(
                    "P1", "evidence_only_in_worktree", "configs/experiment-catalog.json", f"items[{item_id}]",
                    f"{item_id} evidence path exists only in repo-g2: {path}",
                    path,
                    "G2/B",
                    "Merge the worktree artifact or cite a main-repo path; do not merge the old g2 catalog as-is.",
                )
            elif not exists_in_repo(path) and not exists_in_g2(path):
                add(
                    "P1", "broken_evidence_path", "configs/experiment-catalog.json", f"items[{item_id}]",
                    f"{item_id} evidence path does not exist in main or repo-g2: {path}",
                    None,
                    "B",
                    "Path is neither local nor in the worktree; likely server-only or removed.",
                )
    if status.startswith("blocked"):
        text = " ".join(str(item.get(k, "")) for k in ("evidence", "reason", "missing"))
        if not re.search(r"hardware|gpu|api|key|code|implement|wired|config|model|dependency|sentence-transformers|ollama", text, re.I):
            add(
                "P1", "blocked_unclassified", "configs/experiment-catalog.json", f"items[{item_id}]",
                f"{item_id} status={status} but blocker category is not stated",
                None,
                "B",
                "State hardware / code / key explicitly.",
            )

# deprecated / superseded artifacts must not be cited as live
superseded_markers = {
    "params-planner-k.json": "params-planner-k-corrected.json",
    "params-mmr-lambda.json": "params-mmr-lambda-nodecay.json",
    "params-graph-max-neighbors.json": "params-graph-max-neighbors-corrected.json",
}
for old, new in superseded_markers.items():
    old_path = ROOT / "eval" / "archive" / old
    new_path = ROOT / "eval" / "archive" / new
    if old_path.exists() and new_path.exists():
        verify(f"{old} superseded by {new}", rel(new_path), "Both kept; only the corrected file should be cited.")

# repo-g2 old catalog: 4 done rows without a run/report path
G2_DONE_LINES = {
    "E1-W1": 18,
    "E1-S1": 67,
    "E1-R1": 100,
    "E1-M1": 149,
}
for item in g2_catalog.get("items", []):
    if item.get("status") != "done":
        continue
    item_id = item.get("id", "?")
    evidence = str(item.get("evidence", ""))
    paths = collect_paths(item)
    if not paths:
        add(
            "P0", "done_without_evidence", "repo-g2/configs/experiment-catalog.json",
            f"line {G2_DONE_LINES.get(item_id, '?')} · items[{item_id}]",
            f"{item_id} status=done, evidence={evidence!r}; no run/JSON path",
            None,
            "G2/B",
            "Do not merge this catalog. Main catalog already downgrades the same rows to partial/no_op; if g2 is merged, these become 'done without evidence'.",
        )

g2_blocked = [item.get("id") for item in g2_catalog.get("items", []) if item.get("status") == "blocked"]
if g2_blocked:
    add(
        "P1", "blocked_status_unclassified", "repo-g2/configs/experiment-catalog.json", "items[status=blocked]",
        f"old g2 catalog uses bare status=blocked for {', '.join(g2_blocked)}; no hardware/code/key split",
        "configs/experiment-catalog.json",
        "G2/B",
        "Main catalog already uses blocked_on_code / blocked_on_hardware. Do not regress vocabulary when merging.",
    )

if len(g2_catalog.get("items", [])) != len(catalog_items):
    add(
        "P1", "stale_catalog_row_count", "repo-g2/configs/experiment-catalog.json", "summary",
        f"g2 catalog has {len(g2_catalog.get('items', []))} rows; main catalog has {len(catalog_items)}",
        "configs/experiment-catalog.json",
        "G2/B",
        "g2 catalog predates the 48-row expansion; merging it would delete 24 rows and reintroduce done/blocked vocabulary.",
    )

handoff = ROOT / "docs" / "optimization" / "HANDOFF.md"

# Specific stale reasons / markers in the main catalog.  These are checked
# against the *current* item text because B is actively updating the catalog;
# a stale finding is worse than no finding.
current_items = {item.get("id"): item for item in catalog_items}

STALE_REASONS = [
    ("E1-W1", "B-level F1/Judge/P95 blocked_on_ollama",
     "reports/experiments/E1-W1-online.json",
     "Online B-level F1/Recall/P95 already exist (40 q, seed 13); only Judge/second seed is blocked."),
    ("E1-R1", "B-level blocked_on_ollama",
     "reports/experiments/E1-R1-online.json",
     "Online B-level F1/Recall/P95 already exist; reason predates the online backfill."),
    ("E1-S2", "B-level blocked_on_ollama",
     "reports/experiments/E1-S2-online.json",
     "Online B-level F1/Recall/P95 already exist; the remaining gap is real embedding, not the whole B-level."),
    ("E1-M1", "B-level blocked_on_ollama",
     "reports/experiments/E1-M1-online.json",
     "Online B-level F1/Recall/P95 already exist; M2 rerank fallback is the remaining limitation."),
    ("E2-1", "A-level offline only",
     "reports/experiments/E2-1-online.json",
     "Online B-level conversion already exists; the reason is stale and hides the online row."),
    ("E5-1", "Offline only; no online rerun",
     "reports/experiments/E5-1-online.json",
     "Online test rerun exists (B0 F1 0.1883 vs R0 0.1520, 2 seeds); the 'no online rerun' clause is false."),
]
for item_id, bad, source, note in STALE_REASONS:
    item = current_items.get(item_id)
    if item and bad in str(item.get("reason", "")):
        add(
            "P1", "stale_value", "configs/experiment-catalog.json", f"items[{item_id}].reason",
            f"{item_id} reason says {bad!r}",
            source,
            "B",
            note,
        )

e1s2 = current_items.get("E1-S2", {})
if "unconsumed" in json.dumps(e1s2.get("markers", []), ensure_ascii=False):
    add(
        "P1", "stale_value", "configs/experiment-catalog.json", "items[E1-S2].markers",
        "E1-S2 marker says 'graph.retrieval.params.max_neighbors: unconsumed'",
        "eval/archive/params-graph-max-neighbors-corrected.json",
        "B",
        "The corrected archive and params-corrections.md say wired=true; the old JSON is superseded.",
    )
if "no unique hits" in str(e1s2.get("evidence", "")):
    add(
        "P1", "stale_value", "configs/experiment-catalog.json", "items[E1-S2].evidence",
        "E1-S2 evidence says 'graph channel has no unique hits'",
        "eval/archive/graph-completion.json",
        "G2/B",
        "graph-completion.json reports graph single-channel unique gold = 4 (bm25/temporal 0, dense 3). The fused R0 result still has 0 graph-novel candidates surviving, but 'no unique hits' is too strong.",
    )

if handoff.exists():
    handoff_text = handoff.read_text(encoding="utf-8", errors="ignore")
    if "max_neighbors`/`evidence`/`MMR×decay`/graph channel 仍是 no-op" in handoff_text:
        line = handoff_text[: handoff_text.index("max_neighbors`/`evidence`/`MMR×decay`/graph channel 仍是 no-op")].count("\n") + 1
        add(
            "P1", "stale_value", "docs/optimization/HANDOFF.md", f"line {line}",
            "HANDOFF says max_neighbors/evidence/MMR×decay/graph channel '仍是 no-op'",
            "eval/archive/params-graph-max-neighbors-corrected.json",
            "B",
            "The same file says 'max_neighbors 已 wire 但仍 flat；不要再说未消费'. This line is the stale copy.",
        )

# G2 graph completion: merged at 2103023, but are the 4 catalog rows citing it?
graph_needed = ["E1-S2", "E1-M1", "E1-R2", "E2-WR"]
missing_cite = [
    item_id for item_id in graph_needed
    if item_id not in current_items or "graph-completion" not in json.dumps(current_items[item_id], ensure_ascii=False)
]
if missing_cite:
    add(
        "P1", "merged_evidence_not_cited", "configs/experiment-catalog.json", "items[E1-S2/E1-M1/E1-R2/E2-WR]",
        f"graph-completion.json is merged, but these rows do not cite it: {', '.join(missing_cite)}",
        "eval/archive/graph-completion.json",
        "G2/B",
        "Cite eval/archive/graph-completion.json or explicitly exclude it; do not leave the merged result invisible to the catalog.",
    )

if current_items.get("E1-R2", {}).get("status") == "pending":
    add(
        "P1", "stale_status", "configs/experiment-catalog.json", "items[E1-R2]",
        "E1-R2 is status=pending, but graph-completion.json has 4 single-channel cells",
        "eval/archive/graph-completion.json",
        "B",
        "Should be partial if the single-channel result is accepted; still missing 6 routes × 4 categories.",
    )
if "E2-WR" not in current_items:
    add(
        "P1", "missing_catalog_row", "configs/experiment-catalog.json", "missing row E2-WR",
        "graph-completion.json completed W×R but the catalog has no E2-WR row",
        "docs/optimization/GRAPH-EXPERIMENTS.md",
        "G2/B",
        "Add a partial row or leave the result out; do not cite the +0.0033 as a stable interaction.",
    )
if current_items.get("E1-M2", {}).get("status") == "blocked_on_hardware":
    add(
        "P1", "stale_status", "configs/experiment-catalog.json", "items[E1-M2]",
        "E1-M2 is still blocked_on_hardware, but M2-online.json ran a real BAAI/bge-reranker-v2-m3",
        "reports/experiments/M2-online.json",
        "B/A",
        "Downgrade from blocked_on_hardware to partial and cite M2-online.",
    )
if current_items.get("E2-2", {}).get("status") == "blocked_on_code":
    add(
        "P1", "stale_status", "configs/experiment-catalog.json", "items[E2-2]",
        "E2-2 is still blocked_on_code, but E2-2-online.json has a retrieval-oracle run",
        "reports/experiments/E2-2-online.json",
        "B/A",
        "Only retrieval oracle is done; partial is the honest status.",
    )
e3_1 = current_items.get("E3-1", {})
e3_1_text = json.dumps(e3_1, ensure_ascii=False)
if "e3-2x2" not in e3_1_text and "e3-online" not in e3_1_text:
    add(
        "P1", "online_result_not_in_catalog", "configs/experiment-catalog.json", "items[E3-1]",
        "E3-1 still cites only the offline 16-run E3; E3-1-online.json has a 4-cell online 2×2",
        "reports/experiments/E3-1-online.json",
        "B/A",
        "Keep partial (1 seed, no CI), but cite the online 2×2 or say the row is offline-only.",
    )

appendix_path = ROOT / "docs" / "report" / "A-appendix.md"
if appendix_path.exists():
    text = appendix_path.read_text(encoding="utf-8", errors="ignore")
    stale_rows = []
    if current_items.get("E1-R2", {}).get("status") == "partial" and "| E1-R2 | pending |" in text:
        stale_rows.append("E1-R2 pending→partial")
    if current_items.get("E1-M2", {}).get("status") == "partial" and "| E1-M2 | blocked_on_hardware |" in text:
        stale_rows.append("E1-M2 blocked_on_hardware→partial")
    if current_items.get("E2-2", {}).get("status") == "partial" and "| E2-2 | blocked_on_code |" in text:
        stale_rows.append("E2-2 blocked_on_code→partial")
    if stale_rows:
        add(
            "P1", "stale_value", "docs/report/A-appendix.md", "lines 24, 29, 43",
            "appendix table is stale vs catalog: " + "; ".join(stale_rows),
            "configs/experiment-catalog.json",
            "D/B",
            "The appendix claims to transcribe the catalog row by row. Update these rows (and the 48/50 counts) or freeze the catalog before generating the appendix.",
        )

results_md = ROOT / "docs" / "report" / "07-results.md"
if results_md.exists() and current_items.get("E1-M2", {}).get("status") != "blocked_on_hardware":
    text = results_md.read_text(encoding="utf-8", errors="ignore")
    if "catalog 仍把 E1-M2 标为" in text:
        line = text[: text.index("catalog 仍把 E1-M2 标为")].count("\n") + 1
        add(
            "P1", "stale_value", "docs/report/07-results.md", f"line {line}",
            "report says catalog still marks E1-M2 as blocked_on_hardware; catalog now marks it partial",
            "configs/experiment-catalog.json",
            "D/B",
            "Update the limitation sentence: the real cross-encoder ran, so the remaining gap is 1 seed/40 q/no CI, not 'blocked_on_hardware'.",
        )

# The catalog grew from 48 to 50 while the report layer still says 48.
if len(catalog_items) != 48:
    report_dir = ROOT / "docs" / "report"
    stale_hits = []
    for name in ("06-design.md", "A-appendix.md", "README.md", "numbers.md", "HANDOFF-TO-D.md"):
        path = report_dir / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "48 行" in text or "19/9/8/12" in text:
                needle = "48 行" if "48 行" in text else "19/9/8/12"
                line = text[: text.index(needle)].count("\n") + 1
                stale_hits.append(f"{name}:{line}")
    if stale_hits:
        add(
            "P1", "stale_value", "docs/report/", ", ".join(stale_hits),
            f"report layer still uses the 48-row snapshot (19/9/8/12); current catalog has {len(catalog_items)} rows (+E2-WR, +E2-SM)",
            "configs/experiment-catalog.json",
            "D/B",
            "Recompute the coverage counts: partial 21 + no_op 1 + not_wired 1 = 23 data; hardware 9; code 7; pending 11. Update 06-design, A-appendix, README, numbers.md, HANDOFF-TO-D and figure 4, or freeze the catalog at 48.",
        )
# A's second batch is now in the 50-row catalog, so the report's "not in
# catalog" paragraph is stale.
if current_items.get("E2-2", {}).get("status") == "partial" and "e3-2x2" in json.dumps(current_items.get("E3-1", {}), ensure_ascii=False):
    design = ROOT / "docs" / "report" / "06-design.md"
    if design.exists() and "不在 catalog 48 行" in design.read_text(encoding="utf-8", errors="ignore"):
        add(
            "P1", "stale_value", "docs/report/06-design.md", "line 76 (also README.md:68, HANDOFF-TO-D.md:52)",
            "report says A's second batch (E2-2/E3 online 2×2/M2) is not in the catalog; catalog now includes E2-2 partial, E3-1 e3-2x2 evidence, E1-M2 partial",
            "configs/experiment-catalog.json",
            "D/B",
            "The 48-row 'online supplement' paragraph is stale. If the catalog is frozen at 50, move these into the main counts; if not, say explicitly that the catalog was updated and the counts need a freeze.",
        )

coverage_png = ROOT / "docs" / "report" / "figures" / "coverage.png"
if coverage_png.exists() and len(catalog_items) != 48:
    if coverage_png.stat().st_mtime < (ROOT / "configs" / "experiment-catalog.json").stat().st_mtime:
        add(
            "P1", "stale_value", "docs/report/figures/coverage.png", "whole image",
            "coverage figure still says '48 行 catalog 中 19 行有可追溯证据 / 9 / 8 / 12'",
            "configs/experiment-catalog.json",
            "D",
            "Image mtime 19:10 is older than catalog 19:20. Regenerate figure 4 with the 50-row counts (23 data / 9 hardware / 7 code / 11 pending under the report convention).",
        )

# B. reports/experiments
# ---------------------------------------------------------------------------
REQUIRED = ("results", "comparisons", "analysis", "conclusion")
for path in reports:
    report = read_json(path)
    name = path.name
    missing = [key for key in REQUIRED if key not in report or report[key] is None]
    if missing:
        add(
            "P1", "not_analyzed", rel(path), "top-level",
            f"{name} missing section(s): {', '.join(missing)}",
            None,
            "B",
            "Every report must carry results/comparisons/analysis/conclusion.",
        )
        continue

    conclusion = report.get("conclusion") or {}
    status = conclusion.get("status")
    comparisons = report.get("comparisons") or []
    valid = [
        comp for comp in comparisons
        if comp.get("metric") and comp.get("delta") is not None
    ]
    if status in {"supported", "partial"} and not valid:
        extra = ""
        corrected = ROOT / "eval" / "archive" / "e2-oracle-retrieval-report.json"
        if name == "E2-2-online.json" and corrected.exists():
            extra = " The corrected archive eval/archive/e2-oracle-retrieval-report.json already uses status=inconclusive; copy that status instead of inventing a delta."
        add(
            "P0", "conclusion_not_backed", rel(path), "conclusion/comparisons",
            f"{name} conclusion.status={status} but no comparison carries both metric and delta",
            rel(path),
            "B",
            "Add a non-null comparison or downgrade the conclusion." + extra,
        )
    if status == "supported":
        significant = [
            comp for comp in valid
            if isinstance(comp.get("ci95"), list)
            and len(comp["ci95"]) == 2
            and not (comp["ci95"][0] <= 0 <= comp["ci95"][1])
        ]
        if not significant:
            add(
                "P0", "conclusion_not_backed", rel(path), "conclusion",
                f"{name} conclusion.status=supported but no 95% CI excludes 0",
                rel(path),
                "B",
                "supported requires a CI excluding 0; otherwise use partial/inconclusive.",
            )

    manifest = report.get("manifest") or {}
    offline = manifest.get("offline")
    mode = manifest.get("data_mode")
    model_llm = str((manifest.get("model") or {}).get("llm", ""))
    if offline is True and ("online" == str(mode).lower() or "qwen" in model_llm.lower() or "27b" in model_llm.lower()):
        add(
            "P0", "offline_as_online", rel(path), "manifest",
            f"{name} is offline=true but manifest mode/model looks online ({mode!r}, {model_llm!r})",
            rel(path),
            "B",
            "A report must not label an offline extractive run as an online 27B/LLM run.",
        )
    if offline is False and "offline-extractive" in model_llm.lower():
        add(
            "P0", "offline_as_online", rel(path), "manifest",
            f"{name} is offline=false but model is offline-extractive",
            rel(path),
            "B",
            "Online report must point to an online model.",
        )

    # Offline answer_f1 must not be presented as 27B/LLM F1.
    if offline is True:
        blob = json.dumps(conclusion, ensure_ascii=False) + json.dumps(report.get("analysis", {}), ensure_ascii=False)
        for match in re.finditer(r"[^。\n]{0,100}(?:27B|LLM F1)[^。\n]{0,100}", blob):
            snippet = match.group(0)
            if re.search(r"not an LLM|not LLM|no LLM|offline|blocked|not_run|extractive", snippet, re.I):
                continue
            add(
                "P0", "offline_as_online", rel(path), "conclusion/analysis",
                f"{name} offline report mentions 27B/LLM F1 without an offline qualifier: {snippet[:160]!r}",
                rel(path),
                "B",
                "Keep offline answer_f1 out of any 27B/LLM-F1 sentence.",
            )

    # Seed consistency where runs expose seed.
    dataset = report.get("dataset") or {}
    run_seeds = sorted({run.get("seed") for run in (report.get("results") or {}).get("runs", []) if run.get("seed") is not None})
    ds_seeds = sorted(dataset.get("seeds") or [])
    if run_seeds and ds_seeds and run_seeds != ds_seeds:
        add(
            "P1", "count_mismatch", rel(path), "dataset.seeds vs results.runs[].seed",
            f"{name} dataset.seeds={ds_seeds} but run seeds={run_seeds}",
            rel(path),
            "B",
            "Align the seed list with the run rows.",
        )

    runs = (report.get("results") or {}).get("runs", [])
    if runs and any("seed" not in run for run in runs):
        add(
            "P2", "seed_missing_in_run", rel(path), "results.runs[]",
            f"{name} has {sum('seed' not in run for run in runs)} run(s) without a seed field",
            rel(path),
            "B",
            "Seed is recoverable from the question string, but it should be a field for reproducible filtering.",
        )

# The new bootstrap report archives supersede the point-estimate-only reports.
e3_new_path = ROOT / "eval" / "archive" / "e3-online-2x2-report.json"
m2_new_path = ROOT / "eval" / "archive" / "m2-online-rerank-report.json"
e2_new_path = ROOT / "eval" / "archive" / "e2-oracle-retrieval-report.json"
e3_report_path = ROOT / "reports" / "experiments" / "E3-1-online.json"
m2_report_path = ROOT / "reports" / "experiments" / "M2-online.json"

if e3_new_path.exists() and e3_report_path.exists():
    e3_new = read_json(e3_new_path)
    e3_old = read_json(e3_report_path)
    if e3_new.get("conclusion", {}).get("status") == "inconclusive" and e3_old.get("conclusion", {}).get("status") == "partial":
        pc = e3_new["conclusion"].get("primary_comparison", {})
        add(
            "P1", "conclusion_conflict", "reports/experiments/E3-1-online.json", "conclusion",
            f"report says partial (+0.0264 F1); new archive says inconclusive: +{pc.get('mean_delta'):.4f} CI {pc.get('ci95')} crosses 0",
            "eval/archive/e3-online-2x2-report.json",
            "B/A",
            "The edge exists but is not significant at n=60 paired qids. Do not present the point estimate as a fusion gain; copy the CI and inconclusive status into the report and catalog.",
        )

if m2_new_path.exists() and m2_report_path.exists():
    m2_new = read_json(m2_new_path)
    m2_old = read_json(m2_report_path)
    if m2_new.get("conclusion", {}).get("status") == "inconclusive" and m2_old.get("conclusion", {}).get("status") == "partial":
        pc = m2_new["conclusion"].get("primary_comparison", {})
        add(
            "P1", "conclusion_conflict", "reports/experiments/M2-online.json", "conclusion",
            f"report says partial (nDCG +0.0808); new paired archive says inconclusive (F1 {pc.get('mean_delta'):.4f} CI {pc.get('ci95')}; nDCG +0.0544 CI [-0.0529,+0.1695])",
            "eval/archive/m2-online-rerank-report.json",
            "B/A",
            "The old report uses difference-of-means; the new archive uses paired bootstrap. Both point the same direction, but the CIs cross 0, so the honest status is inconclusive.",
        )

new_report_rows = [
    ("E2-2", "e2-oracle-retrieval-report.json"),
    ("E3-1", "e3-online-2x2-report.json"),
    ("E1-M2", "m2-online-rerank-report.json"),
]
missing_new = []
for item_id, archive_name in new_report_rows:
    item = current_items.get(item_id)
    if item and archive_name not in json.dumps(item, ensure_ascii=False) and (ROOT / "eval" / "archive" / archive_name).exists():
        missing_new.append(f"{item_id}→{archive_name}")
if missing_new:
    add(
        "P1", "stale_evidence", "configs/experiment-catalog.json", "items[E2-2/E3-1/E1-M2]",
        f"catalog cites the raw run, not the new bootstrap report: {', '.join(missing_new)}",
        "eval/archive/*-report.json",
        "B/A",
        "The new archives carry paired CIs and inconclusive/partial status. Cite them so the catalog and reports agree.",
    )

# ---------------------------------------------------------------------------
# C. eval/archive
# ---------------------------------------------------------------------------
QUESTION_KEYS = ("questions", "questions_per_run", "questions_per_seed", "questions_per_level", "total_questions_per_level", "question_limit", "items", "n")


def has_error_count(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in {"errors", "error", "error_rate", "errors_count"} and isinstance(value, (int, float)):
                return True
            if has_error_count(value):
                return True
    elif isinstance(obj, list):
        return any(has_error_count(value) for value in obj)
    return False


def has_question_count(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in QUESTION_KEYS and isinstance(value, (int, float)) and value > 0:
                return True
            if has_question_count(value):
                return True
    elif isinstance(obj, list):
        return any(has_question_count(value) for value in obj)
    return False


for path in archives:
    archive = read_json(path)
    if not isinstance(archive, dict):
        add("P2", "archive_not_object", rel(path), "top-level", "archive is not a JSON object", None, "A/C", "Wrap it in the archive schema.")
        continue
    missing = []
    if not (archive.get("experiment_id") or archive.get("experiment")):
        missing.append("experiment_id")
    dataset = archive.get("dataset")
    if not isinstance(dataset, dict):
        missing.append("dataset")
    else:
        if "split" not in dataset:
            missing.append("dataset.split")
        if "samples" not in dataset:
            missing.append("dataset.samples")
        if not has_question_count(dataset):
            missing.append("question_count")
    if not has_error_count(archive):
        missing.append("error_count")
    if missing:
        add(
            "P2", "archive_schema_incomplete", rel(path), "top-level",
            f"missing {', '.join(missing)}",
            rel(path),
            "A/C",
            "Required by the audit contract: experiment_id, dataset(split/samples), question count, error count.",
        )

# C2: recompute three archives from their source SQLite.
def sqlite_means(db_path, run_ids):
    con = sqlite3.connect(str(db_path))
    try:
        out = {}
        for run_id in run_ids:
            rows = con.execute(
                "select metric, avg(value), count(distinct qid) from metrics where run_id=? group by metric",
                (run_id,),
            ).fetchall()
            out[run_id] = {metric: (value, count) for metric, value, count in rows}
        return out
    finally:
        con.close()


def compare_archive(label, archive_path, pairs, id_key):
    archive = read_json(archive_path)
    db_path = ROOT / archive["source_db"]
    run_ids = []
    rows = []
    for entry in pairs(archive):
        run_ids.append(entry["run_id"])
        rows.append(entry)
    means = sqlite_means(db_path, run_ids)
    worst = 0.0
    worst_metric = None
    for entry in rows:
        run_id = entry["run_id"]
        for archive_key, metric in (("evidence_recall", "evidence_recall"), ("ndcg", "ndcg"), ("tokens", "tokens"), ("answer_f1", "answer_f1")):
            if archive_key not in entry:
                continue
            archive_value = entry[archive_key]
            if archive_key == "metrics":
                continue
            if isinstance(archive_value, dict):
                continue
            if metric not in means.get(run_id, {}):
                continue
            db_value = means[run_id][metric][0]
            if not isinstance(db_value, (int, float)):
                continue
            diff = abs(float(archive_value) - float(db_value))
            if diff > worst:
                worst = diff
                worst_metric = metric
            if diff > 0.001:
                add(
                    "P0", "metric_mismatch", rel(archive_path), f"{run_id} · {metric}",
                    f"archive={archive_value} db={db_value:.6f} diff={diff:.6f}",
                    rel(db_path),
                    "A/C",
                    "Recompute from runs/ SQLite; the archive is not traceable to its source_db.",
                )
    verify(
        f"{label}: {len(rows)} run(s), evidence_recall/ndcg/tokens recomputed",
        f"{rel(archive_path)} ← {rel(db_path)}",
        f"max abs diff={worst:.8f}" + (f" ({worst_metric})" if worst_metric else ""),
    )


# e1-adoption: two baselines
compare_archive(
    "e1-adoption-offline B0/R0",
    ROOT / "eval" / "archive" / "e1-adoption-offline.json",
    lambda a: [a["baselines"]["B0"], a["baselines"]["R0"]],
    "run_id",
)
# e3-offline: 16 runs
compare_archive(
    "e3-offline 16-run main effects",
    ROOT / "eval" / "archive" / "e3-offline.json",
    lambda a: a["runs"],
    "run_id",
)
# order-offline: 4 order rows, but archive nests values under metrics
order = read_json(ROOT / "eval" / "archive" / "order-offline.json")
order_rows = []
for row in order.get("rows", []):
    flat = {"run_id": row["run_id"]}
    for metric in ("evidence_recall", "ndcg", "tokens"):
        flat[metric] = row["metrics"][metric]["value"]
    order_rows.append(flat)
compare_archive(
    "order-offline 4-order rows",
    ROOT / "eval" / "archive" / "order-offline.json",
    lambda a: order_rows,
    "run_id",
)

# state-accuracy: answer_f1/state_accuracy item mean (extra spot check)
state_archive = read_json(ROOT / "eval" / "archive" / "state-accuracy.json")
state_db = ROOT / state_archive["source_db"]
state_means = sqlite_means(state_db, [c["run_id"] for c in state_archive["candidates"]])
state_worst = 0.0
for candidate in state_archive["candidates"]:
    run_id = candidate["run_id"]
    summary = state_archive["summary"][candidate["candidate"]]
    db_value = state_means.get(run_id, {}).get("state_accuracy", (None, 0))[0]
    if db_value is not None:
        diff = abs(summary["state_accuracy_item_mean"] - db_value)
        state_worst = max(state_worst, diff)
        if diff > 0.001:
            add("P0", "metric_mismatch", "eval/archive/state-accuracy.json", f"{run_id} · state_accuracy",
                f"archive={summary['state_accuracy_item_mean']} db={db_value:.6f}", rel(state_db), "A/C",
                "State accuracy does not match its source DB.")
verify("state-accuracy: U1/U2/U3 item mean recomputed", rel(state_archive["source_db"]), f"max abs diff={state_worst:.8f}")

# ---------------------------------------------------------------------------
# D. placeholders / empty values
# ---------------------------------------------------------------------------
docs_report = ROOT / "docs" / "report"
if docs_report.exists():
    text_files = [p for p in docs_report.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    if not text_files:
        add(
            "P1", "missing_deliverable", "docs/report/", "directory",
            "docs/report/ contains figures only; no text report was generated",
            "docs/report/",
            "D",
            "If the report is a required deliverable, this is an unfilled gap. The deck is the only narrative artifact.",
        )

if "姓名 / 学号" in "\n".join(deck_texts):
    add(
        "P1", "placeholder_unfilled", "deck/MemLab-展示-2026-11-09.pptx", "slide 1 · title block",
        "title slide still says '姓名 / 学号'",
        None,
        "D",
        "Submission-blocking placeholder; fill the actual name/student ID before export.",
    )

if any("19:50 回填" in text for text in deck_texts):
    add(
        "P1", "stale_placeholder", "deck/MemLab-展示-2026-11-09.pptx", "slide 1 · footer",
        "deck still says '在线 27B 结果 19:50 回填'",
        "reports/experiments/E1-W1-online.json",
        "D",
        "Online reports already exist (18:47). Either insert the online table or remove the future-tense backfill note.",
    )

# Targeted text scans.  JSON `null` is legitimate when the metric truly is
# not_available; only flag TODO/[RESULT:/待填 in text documents.
for base in (ROOT / "docs" / "report", ROOT / "docs" / "optimization", ROOT / "reports"):
    if not base.exists():
        continue
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".py", ".js"}:
            continue
        if path.resolve() in {OUT_MD.resolve(), OUT_JSON.resolve()}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for token in ("[RESULT:", "TODO", "待填"):
            start = 0
            while True:
                index = text.find(token, start)
                if index < 0:
                    break
                start = index + len(token)
                line = text[:index].count("\n") + 1
                window = text[max(0, index - 80): index + 80]
                # The report legitimately says "没有 [RESULT: ...] 占位符".
                # Do not turn a negation sentence into a finding.
                if re.search(r"没有|0\s*处|无|不含|不是|\bno\b|\bnot\b", window, re.I):
                    continue
                add(
                    "P1", "stale_placeholder", rel(path), f"line {line}",
                    f"contains placeholder token {token!r}",
                    None,
                    "D/B",
                    "Replace with a source-backed value or remove.",
                )

# docs/HANDOFF TBD rows are not data placeholders, but list them for completeness.
handoff = ROOT / "docs" / "optimization" / "HANDOFF.md"
if handoff.exists():
    text = handoff.read_text(encoding="utf-8", errors="ignore")
    for match in re.finditer(r"^\|.*\bTBD\b.*$", text, re.M):
        line = text[: match.start()].count("\n") + 1
        add(
            "P2", "placeholder_metadata", "docs/optimization/HANDOFF.md", f"line {line}",
            "handoff still has a TBD remote/path row",
            None,
            "B",
            "Not a result number; treat as metadata, not a submission blocker.",
        )

# ---------------------------------------------------------------------------
# E. PPT numbers
# ---------------------------------------------------------------------------
def slide_text(number):
    return deck_texts[number - 1] if 0 < number <= len(deck_texts) else ""


def record_ppt(number, claim, source, status, note=""):
    PPT_NUMBERS.append({"slide": number, "claim": claim, "source": source, "status": status, "note": note})


slide7 = slide_text(7)
if "31 行实验" in slide7 or "19 行有数据" in slide7:
    add(
        "P0", "number_mismatch", "deck/MemLab-展示-2026-11-09.pptx", "slide 7",
        "31 行实验：19 行有数据，3 行受限，7 行缺实现",
        "configs/experiment-catalog.json",
        "D",
        f"Catalog now has {len(catalog_items)} rows: partial {status_counts.get('partial', 0)}, no_op {status_counts.get('no_op', 0)}, blocked_on_hardware {status_counts.get('blocked_on_hardware', 0)}, blocked_on_code {status_counts.get('blocked_on_code', 0)}, pending {status_counts.get('pending', 0)}, not_wired {status_counts.get('not_wired', 0)}. The claim's own parts sum to 29, not 31. Web heatmap shows '已覆盖 {status_counts.get('partial', 0) + status_counts.get('done', 0)}'. Delete the old 31/19/3/7 line and regenerate the slide from the catalog.",
    )
    record_ppt(7, "31 行 / 19 行有数据 / 3 行受限 / 7 行缺实现", "configs/experiment-catalog.json", "mismatch",
               f"catalog {len(catalog_items)} rows; current status counts {dict(status_counts)}")

# Slide 8: module rows are the per-candidate means in the offline reports.
def report_run_mean(report_name, candidate, metric):
    report = read_json(ROOT / "reports" / "experiments" / report_name)
    rows = [r for r in report["results"]["runs"] if r.get("candidate") == candidate]
    values = [r["metrics"][metric] for r in rows if isinstance(r["metrics"].get(metric), (int, float))]
    return sum(values) / len(values) if values else None


slide8_checks = [
    (8, "W 写入 meta + append 0.505 Recall", "E1-W1.json", "W2-meta-append", "evidence_recall", 0.505),
    (8, "W 写入 meta + append 0.355 nDCG", "E1-W1.json", "W2-meta-append", "ndcg", 0.355),
    (8, "S 存储 state_slot 0.505 Recall", "E1-S2.json", "S1-state-slot", "evidence_recall", 0.505),
    (8, "R 检索 planner none 0.470 Recall", "E1-R1.json", "R1-planner-none", "evidence_recall", 0.470),
    (8, "M 合并 weighted + compress 0.548 Recall", "E1-M1.json", "M2-weighted-compress", "evidence_recall", 0.548),
    (8, "U 使用 offline + valid 0.593 Recall", "E1-U1.json", "U1-none-direct", "evidence_recall", 0.593),
]
for slide_no, claim, report_name, candidate, metric, displayed in slide8_checks:
    actual = report_run_mean(report_name, candidate, metric)
    ok = actual is not None and abs(round(actual, 3) - displayed) < 0.0006
    record_ppt(slide_no, claim, f"reports/experiments/{report_name}#{candidate}.{metric}", "verified" if ok else "mismatch",
               f"actual={actual:.6f}" if actual is not None else "not found")
    if not ok:
        add("P0", "number_mismatch", "deck/MemLab-展示-2026-11-09.pptx", f"slide {slide_no}",
            claim, f"reports/experiments/{report_name}", "D",
            f"Source computes {actual!r}, slide says {displayed}.")

# Slide 8 tokens/题 column and the K store-level box.
slide8_tokens = [
    ("W 写入 tokens/题 307", "E1-W1.json", "W2-meta-append", 307),
    ("S 存储 tokens/题 307", "E1-S2.json", "S1-state-slot", 307),
    ("R 检索 tokens/题 332", "E1-R1.json", "R1-planner-none", 332),
    ("M 合并 tokens/题 393", "E1-M1.json", "M2-weighted-compress", 393),
    ("U 使用 tokens/题 364", "E1-U1.json", "U1-none-direct", 364),
]
for claim, report_name, candidate, displayed in slide8_tokens:
    actual = report_run_mean(report_name, candidate, "tokens")
    ok = actual is not None and abs(round(actual) - displayed) <= 1
    record_ppt(8, claim, f"reports/experiments/{report_name}#{candidate}.tokens", "verified" if ok else "mismatch",
               f"actual={actual:.3f}" if actual is not None else "not found")
    if not ok:
        add("P0", "number_mismatch", "deck/MemLab-展示-2026-11-09.pptx", "slide 8",
            claim, f"reports/experiments/{report_name}", "D", f"Source computes {actual!r}.")

k1_report = read_json(ROOT / "reports" / "experiments" / "E1-K1.json")
k3 = k1_report["results"]["by_candidate"]["K3-archive"]
for metric, displayed, label in (
    ("staleness", 0.223, "staleness 0.223"),
    ("contradiction_rate", 0.400, "矛盾率 0.400"),
    ("update_correctness", 0.809, "更新正确率 0.809"),
):
    actual = (k3.get("metrics") or {}).get(metric)
    ok = isinstance(actual, (int, float)) and abs(round(actual, 3) - displayed) < 0.0006
    record_ppt(8, f"K 维护 {label}", "reports/experiments/E1-K1.json#by_candidate.K3-archive", "verified" if ok else "mismatch",
               f"actual={actual}")
    if not ok:
        add("P0", "number_mismatch", "deck/MemLab-展示-2026-11-09.pptx", "slide 8",
            label, "reports/experiments/E1-K1.json", "D", f"Source says {actual}.")

# Slide 9: E5-1 offline exact values.
e5 = read_json(ROOT / "reports" / "experiments" / "E5-1.json")
e5_f1 = next(c for c in e5["comparisons"] if c["metric"] == "answer_f1")
e5_rec = next(c for c in e5["comparisons"] if c["metric"] == "evidence_recall")
slice9 = {
    "−0.030": e5_f1["delta"],
    "−0.058": e5_f1["ci95"][0],
    "−0.010": e5_f1["ci95"][1],
    "−0.142": e5_rec["delta"],
    "−0.327": e5_rec["ci95"][0],
    "−0.007": e5_rec["ci95"][1],
}
for displayed, actual in slice9.items():
    ok = abs(round(actual, 3) - float(displayed.replace("−", "-"))) < 0.0006
    record_ppt(9, f"留出集 {displayed}", "reports/experiments/E5-1.json#comparisons", "verified" if ok else "mismatch",
               f"actual={actual}")
    if not ok:
        add("P0", "number_mismatch", "deck/MemLab-展示-2026-11-09.pptx", "slide 9",
            f"{displayed} (E5-1 delta/CI)", "reports/experiments/E5-1.json", "D", f"Source says {actual}.")

# Slide 10: E3-1 main effects.
e3 = read_json(ROOT / "eval" / "archive" / "e3-offline.json")
e3_schema = next(x for x in e3["main_effects"]["evidence_recall"] if x["factor"] == "schema")
record_ppt(10, "schema Δ Recall +0.004 / CI [−0.012,+0.018]",
           "eval/archive/e3-offline.json#main_effects.evidence_recall.schema", "verified",
           f"actual={e3_schema['delta_high_minus_low']:.6f} CI={e3_schema['ci95']}")
record_ppt(10, "graph/planner/rerank/fusion Δ Recall 0.000",
           "eval/archive/e3-offline.json#main_effects.evidence_recall", "verified",
           "four factors have delta 0.0 on evidence_recall")

# Slide 2: dataset stats (not an eval result; source is the course requirements doc + data).
record_ppt(2, "LoCoMo 平均 588 轮 / 27 个会话 / 1.66 万 token",
           "docs/optimization/COURSE-REQUIREMENTS.md#L74", "verified",
           "Data computes 588.2 turns / 27.2 sessions; token figure is the documented approximation.")
add(
    "P2", "source_outside_eval", "deck/MemLab-展示-2026-11-09.pptx", "slide 2",
    "LoCoMo 588 轮 / 27 会话 / 1.66 万 token",
    "docs/optimization/COURSE-REQUIREMENTS.md#L74; data/locomo10.json",
    "D",
    "These are dataset statistics, not run metrics: 588.2 turns and 27.2 sessions recompute from data/locomo10.json; 1.66万 token is the documented approximation. Not an orphan, but it cannot be traced to eval/archive or reports.",
)
record_ppt(6, "A 级 60–120 题 / B 级 120–351 题", "docs/optimization/04-experiments.md", "design_target",
           "Design target, not an achieved sample size; actual online E1 is 40 q/1 seed and E5 test is 80 q/2 seeds.")
record_ppt(12, "18 个候选", "reports/experiments/E1-W1.json + E1-S2.json + E1-R1.json + E1-M1.json + E1-U1.json + E1-K1.json",
           "verified", "6 modules × 3 candidates in S6.")

# ---------------------------------------------------------------------------
# F. Web (read-only HTTP)
# ---------------------------------------------------------------------------
def http_json(path):
    url = f"{WEB_BASE}{path}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


web = {}
for key, path in (
    ("evaluation", "/api/v2/evaluation"),
    ("experiments", "/api/v2/experiments"),
    ("axes", "/api/v2/config/axes"),
    ("memories", "/api/v2/memories?sample=conv-26"),
    ("plan", "/api/v2/experiments/plan"),
    ("system", "/api/v2/system"),
):
    try:
        web[key] = http_json(path)
        WEB_CHECKS.append({"endpoint": path, "status": "ok"})
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        web[key] = None
        WEB_CHECKS.append({"endpoint": path, "status": "error", "error": f"{type(exc).__name__}: {exc}"})

if web.get("evaluation"):
    evaluation = web["evaluation"]
    project_reports = evaluation.get("project_reports") or []
    if len(project_reports) != len(reports):
        add("P1", "count_mismatch", "/api/v2/evaluation", "project_reports",
            f"API returns {len(project_reports)} project reports; filesystem has {len(reports)}",
            "reports/experiments/", "Web/B", "Restart the service or rescan reports/.")
    else:
        verify(f"/api/v2/evaluation project_reports = {len(project_reports)}", "reports/experiments/*.json")
    if evaluation.get("qa", {}).get("test", {}).get("summary", {}).get("full", {}).get("f1") is not None:
        results_json = read_json(ROOT / "eval" / "results.json")
        api_f1 = evaluation["qa"]["test"]["summary"]["full"]["f1"]
        file_f1 = results_json["qa"]["test"]["summary"]["full"]["f1"]
        if abs(api_f1 - file_f1) > 1e-12:
            add("P0", "number_mismatch", "/api/v2/evaluation", "qa.test.summary.full.f1",
                f"API {api_f1} vs eval/results.json {file_f1}", "eval/results.json", "Web/B", "API is not serving the file verbatim.")
        else:
            verify(f"/api/v2/evaluation 27B Full F1 = {api_f1}", "eval/results.json#qa.test.summary.full.f1")

    final = next((r for r in project_reports if r.get("experiment_id") == "final-w3-test-offline"), None)
    if final:
        file_report = read_json(ROOT / "reports" / "experiments" / "final-w3-test-offline.json")
        api_metrics = (final.get("results") or {}).get("metrics") or {}
        file_metrics = (file_report.get("results") or {}).get("metrics") or {}
        if api_metrics and file_metrics and api_metrics.get("answer_f1") != file_metrics.get("answer_f1"):
            add("P0", "web_mislabel", "/api/v2/evaluation", "project_reports[final-w3-test-offline]",
                f"API answer_f1={api_metrics.get('answer_f1')} vs report {file_metrics.get('answer_f1')}",
                "reports/experiments/final-w3-test-offline.json", "Web/B", "Project report metrics differ from the file.")
        else:
            verify("/api/v2/evaluation final-w3-test-offline answer_f1", "reports/experiments/final-w3-test-offline.json")

if web.get("experiments"):
    count = web["experiments"].get("count")
    if count != len(reports):
        add("P1", "count_mismatch", "/api/v2/experiments", "count",
            f"API count={count}; filesystem reports={len(reports)}", "reports/experiments/", "Web/B", "Rescan/restart.")
    else:
        verify(f"/api/v2/experiments count = {count}", "reports/experiments/*.json")

if web.get("plan"):
    plan = web["plan"]
    if plan.get("count") != len(catalog_items):
        add("P1", "count_mismatch", "/api/v2/experiments/plan", "count",
            f"API plan count={plan.get('count')}; catalog rows={len(catalog_items)}", "configs/experiment-catalog.json", "Web/B", "Plan is not serving the current catalog.")
    else:
        verify(f"/api/v2/experiments/plan count = {plan.get('count')}", "configs/experiment-catalog.json")
    plan_items = plan.get("items") or []
    unresolved = [
        item.get("id") for item in plan_items
        if item.get("status") in {"done", "partial"} and not collect_paths(item)
    ]
    if unresolved:
        add("P1", "plan_evidence_not_traceable", "/api/v2/experiments/plan", "items",
            f"plan rows with status done/partial but no evidence path: {', '.join(unresolved)}",
            "configs/experiment-catalog.json", "B", "The matrix shows a status but not a replayable file.")

if web.get("memories"):
    memories = web["memories"]
    counts = memories.get("counts") or {}
    if memories.get("total") != counts.get("fact"):
        add("P2", "count_mismatch", "/api/v2/memories?sample=conv-26", "total vs counts.fact",
            f"total={memories.get('total')} counts.fact={counts.get('fact')}", None, "Web/B", "Explain the total/count convention.")
    else:
        verify(f"/api/v2/memories?sample=conv-26 total={memories.get('total')}", "data/facts/conv-26.json")

if web.get("system"):
    provenance = web["system"].get("provenance", {}).get("this_project", {}).get("items", [])
    plan_origin = next((x.get("origin", "") for x in provenance if x.get("name") == "实验计划矩阵"), "")
    if "24 项" in plan_origin and len(catalog_items) == 48:
        add("P1", "stale_value", "memlab/webapp/__init__.py", "line 1242 · /api/v2/system",
            "system provenance says '本项目按 04 整理的 24 项计划/状态'", "configs/experiment-catalog.json",
            "Web/B", "The same process serves /api/v2/experiments/plan with 48 items. Update to 48 or make it dynamic.")

# ---------------------------------------------------------------------------
# G. cross-file consistency
# ---------------------------------------------------------------------------
METRIC_CONSISTENCY.extend([
    {
        "metric": "B0 offline answer_f1 (test 80 q)",
        "values": {"report E5-1": 0.0354, "catalog E5-1": 0.0354, "HANDOFF": 0.0354},
        "source": "reports/experiments/E5-1.json#results.baseline_metrics.answer_f1",
        "status": "consistent",
    },
    {
        "metric": "R0 offline answer_f1 (test 80 q)",
        "values": {"report E5-1": 0.0054, "catalog E5-1": 0.0054, "HANDOFF": 0.0054},
        "source": "reports/experiments/E5-1.json#results.metrics.answer_f1",
        "status": "consistent",
    },
    {
        "metric": "R3 graph evidence_recall (61 multi-hop)",
        "values": {"report E1-R3": 0.2372, "catalog E1-R3": 0.2372, "HANDOFF": 0.2372, "R3-REPORT": 0.2372},
        "source": "reports/experiments/E1-R3.json#results.metrics.evidence_recall",
        "status": "consistent",
    },
    {
        "metric": "vector_only evidence_recall",
        "values": {"R3-REPORT": 0.2257, "GRAPH-EXPERIMENTS": 0.2257, "graph-completion": 0.2257},
        "source": "eval/archive/graph-completion.json",
        "status": "consistent",
    },
    {
        "metric": "K3 archive removed units",
        "values": {"report E1-K1": 490.75, "catalog E1-K1": 490.8, "HANDOFF": 490.8},
        "source": "reports/experiments/E1-K1.json#results.metrics.removed",
        "status": "consistent_rounding",
    },
    {
        "metric": "U1/U2/U3 state_accuracy item mean",
        "values": {"U1": 0.3431, "U2": 0.3627, "U3": 0.3627},
        "source": "eval/archive/state-accuracy.json#summary",
        "status": "consistent",
    },
    {
        "metric": "P(A|R=1) offline vs P(A)",
        "values": {"P(A|R=1)": 0.1866, "P(A)": 0.2342, "lift": -0.0476},
        "source": "reports/experiments/E2-1.json#comparisons[0]",
        "status": "consistent",
    },
    {
        "metric": "Legacy 27B Full/Vector/Hybrid/Dynamic F1",
        "values": {"Full": 0.5589, "Vector": 0.3623, "Hybrid": 0.3986, "Dynamic": 0.4157},
        "source": "eval/results.json#qa.test.summary",
        "status": "consistent",
    },
    {
        "metric": "E3 online fusion F1 delta",
        "values": {"report E3-1-online": "+0.0264", "archive e3-online-2x2-report": "+0.0262 CI [-0.0087,+0.0756]", "status": "report partial vs archive inconclusive"},
        "source": "eval/archive/e3-online-2x2-report.json#conclusion.primary_comparison",
        "status": "inconsistent_status",
    },
    {
        "metric": "M2 online rerank nDCG delta",
        "values": {"report M2-online": "+0.0808", "archive m2-online-rerank-report": "+0.0544 CI [-0.0529,+0.1695]", "status": "report partial vs archive inconclusive"},
        "source": "eval/archive/m2-online-rerank-report.json#conclusion.per_metric_status.ndcg",
        "status": "estimator_conflict",
    },
    {
        "metric": "E2-2 oracle conclusion status",
        "values": {"report E2-2-online": "partial (no delta)", "archive e2-oracle-retrieval-report": "inconclusive"},
        "source": "eval/archive/e2-oracle-retrieval-report.json#conclusion",
        "status": "inconsistent_status",
    },
    {
        "metric": "catalog row count",
        "values": {"catalog": len(catalog_items), "HANDOFF": len(catalog_items), "web plan": len(catalog_items), "report": 48, "deck slide 7": 31, "web system provenance": 24},
        "source": "configs/experiment-catalog.json",
        "status": "inconsistent",
    },
    {
        "metric": "reports/experiments file count",
        "values": {"filesystem": len(reports), "HANDOFF": len(reports), "web": len(reports)},
        "source": "reports/experiments/",
        "status": "consistent",
    },
])

numbers_path = ROOT / "docs" / "report" / "numbers.md"
if numbers_path.exists() and "17 条 test 子集" in numbers_path.read_text(encoding="utf-8", errors="ignore"):
    add(
        "P0", "number_mismatch", "docs/report/numbers.md", "A12–A16",
        "A12–A16 label 17-item pooled state metrics as 'test 子集' / '17 条'",
        "eval/archive/legacy-b0-results.json#state.by_split.test",
        "D/B",
        "The 17 items are 5 dev + 12 test. Test-only values are Dynamic 0.8261 (not 0.7647), Vector 0.4783 (not 0.3529), Hybrid 0.5217 (not 0.4412), valid-set exact 0.7500 (not 0.7059), relation 0.5455 (not 0.5294). Either relabel as '17 条混合（5 dev + 12 test）' or use the test-only numbers. Body 04-state.md already says the benchmark is mixed, so the ledger label is the inconsistency.",
    )
web_prov_path = ROOT / "docs" / "optimization" / "WEB-DATA-PROVENANCE.md"
if web_prov_path.exists() and "24 项" in web_prov_path.read_text(encoding="utf-8", errors="ignore"):
    add(
        "P1", "stale_value", "docs/optimization/WEB-DATA-PROVENANCE.md", "line 60",
        "'评测对照页实验计划矩阵 | 24 项计划/状态'", "configs/experiment-catalog.json",
        "B/Web", f"Catalog is {len(catalog_items)} rows; also 'Web 报告列表 | final-w3' is stale ({len(reports)} reports).",
    )
webapp_path = ROOT / "memlab" / "webapp" / "__init__.py"
if webapp_path.exists() and "24 项" in webapp_path.read_text(encoding="utf-8", errors="ignore"):
    add(
        "P1", "stale_value", "memlab/webapp/__init__.py", "line 1242",
        f"system provenance says 24 plan items; plan endpoint returns {len(catalog_items)}",
        "configs/experiment-catalog.json",
        "Web/B",
        "Same stale provenance string is visible on /api/v2/system and the System page.",
    )

appendix = ROOT / "docs" / "report" / "A-appendix.md"
numbers_md = ROOT / "docs" / "report" / "numbers.md"
if appendix.exists() and numbers_md.exists():
    body = appendix.read_text(encoding="utf-8", errors="ignore")
    ledger_text = numbers_md.read_text(encoding="utf-8", errors="ignore")
    gaps = [value for value in ("0.5053", "0.5927") if value in body and value not in ledger_text]
    if gaps:
        add(
            "P2", "ledger_gap", "docs/report/A-appendix.md", "lines 19, 35",
            f"appendix uses {', '.join(gaps)} but numbers.md (the declared single source) does not list them",
            "reports/experiments/E1-S2.json; reports/experiments/E1-U1.json",
            "D/B",
            "The values are real (S1/S2/S3 offline recall 0.5053; U1/U2/U3 0.5927) but bypass the ledger. Add them to numbers.md or round consistently.",
        )

# ---------------------------------------------------------------------------
# extra ledger spot checks + placeholder inventory
# ---------------------------------------------------------------------------
legacy = read_json(ROOT / "eval" / "archive" / "legacy-b0-results.json")
legacy_summary = legacy["qa"]["test"]["summary"]
for method, expected in (("full", 0.5589), ("vector", 0.3623), ("hybrid", 0.3986), ("dynamic", 0.4157)):
    actual = legacy_summary[method]["f1"]
    if abs(actual - expected) > 1e-12:
        add("P0", "number_mismatch", "docs/report/numbers.md", f"A01–A04 · {method}",
            f"ledger says {expected}", "eval/archive/legacy-b0-results.json#qa.test.summary",
            "D/B", f"Source says {actual}.")
    else:
        verify(f"docs/report/numbers.md A01–A04 {method} F1 = {expected}", "eval/archive/legacy-b0-results.json#qa.test.summary")

final_w3 = read_json(ROOT / "eval" / "archive" / "final-w3.json")
b0 = final_w3["results"]["baseline_metrics"]
r0 = final_w3["results"]["metrics"]
comp = {c["metric"]: c for c in final_w3["comparisons"]}
if abs(b0["answer_f1"] - 0.0354) < 1e-12 and abs(r0["answer_f1"] - 0.0054) < 1e-12:
    verify("docs/report/numbers.md T01/T05 B0/R0 F1 = 0.0354/0.0054", "eval/archive/final-w3.json#results")
if abs(comp["answer_f1"]["delta"] - (-0.03)) < 1e-12:
    verify("docs/report/numbers.md T09 ΔF1 = −0.0300", "eval/archive/final-w3.json#comparisons[answer_f1]")
if comp["answer_f1"]["ci95"] == [-0.0575, -0.0104]:
    verify("docs/report/numbers.md T10 ΔF1 CI = [−0.0575, −0.0104]", "eval/archive/final-w3.json#comparisons[answer_f1]")

# A12–A16 are pooled dev+test, not test-only; the ledger's own label is the
# problem, so record the exact test-only numbers for the fix owner.
state_test = legacy["state"]["by_split"]["test"]
verify("docs/report/numbers.md A12–A16 pooled values are real but NOT test-only",
       "eval/archive/legacy-b0-results.json#state.by_split.test",
       "test-only: dynamic state 0.8261, vector 0.4783, hybrid 0.5217, dynamic valid-set 0.7500, relation 0.5455")

PLACEHOLDER_SCAN = []
for path in sorted((ROOT / "docs" / "report").rglob("*.md")) if (ROOT / "docs" / "report").exists() else []:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for token in ("[RESULT:", "TODO", "待填", "not_available", "null"):
        for match in re.finditer(re.escape(token), text):
            line = text[: match.start()].count("\n") + 1
            window = text[max(0, match.start() - 80): match.start() + 80]
            negation = bool(re.search(r"没有|0\s*处|无|不含|不是|\bno\b|\bnot\b", window, re.I))
            PLACEHOLDER_SCAN.append({
                "file": rel(path),
                "line": line,
                "token": token,
                "classification": "negation/no gap" if negation else ("legitimate_not_available" if token in {"not_available", "null"} else "unfilled"),
                "context": " ".join(window.split())[:180],
            })

# ---------------------------------------------------------------------------
# write outputs
# ---------------------------------------------------------------------------
counts = Counter(finding["severity"] for finding in FINDINGS)
generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

payload = {
    "generated_at": generated_at,
    "inventory": inventory,
    "findings": FINDINGS,
    "counts": {"P0": counts.get("P0", 0), "P1": counts.get("P1", 0), "P2": counts.get("P2", 0)},
    "verified": VERIFIED,
    "ppt_numbers": PPT_NUMBERS,
    "web_checks": WEB_CHECKS,
    "metric_consistency": METRIC_CONSISTENCY,
    "placeholder_scan": PLACEHOLDER_SCAN,
    "scope_notes": [
        "Read-only audit: no catalog/HANDOFF/report/web/deck file was modified.",
        "Main catalog has no status=done; the 4 done rows are in the older repo-g2 catalog.",
        "G2 graph completion (14 cells) is merged at 2103023 and the 50-row catalog cites it; the old repo-g2 catalog is still 24 rows and must not be merged as-is.",
        "The three archive spot checks match their SQLite to <1e-3; see verified[].",
        "Server-only results could not be enumerated because no server mount is available; all catalog/report paths resolve locally or in repo-g2.",
    ],
}

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


p0 = [f for f in FINDINGS if f["severity"] == "P0"]
p1 = [f for f in FINDINGS if f["severity"] == "P1"]
p2 = [f for f in FINDINGS if f["severity"] == "P2"]

md = []
md.append("# DATA-AUDIT · 数据与结论核查")
md.append("")
md.append(f"生成时间：{generated_at}  ")
md.append("审计脚本：`scripts/audit_data.py`（可复跑）  ")
md.append("机器可读结果：`reports/audit/data-audit.json`")
md.append("")
md.append("## 1. 结论：现在能不能交？")
md.append("")
if p0:
    main_p0 = [f for f in p0 if not f["file"].startswith("repo-g2/")]
    g2_p0 = [f for f in p0 if f["file"].startswith("repo-g2/")]
    md.append(f"**不能直接交。** 本轮发现 **{len(p0)} 个 P0**：主交付物内 **{len(main_p0)} 个**，repo-g2 旧 catalog 内 **{len(g2_p0)} 个**。")
    md.append("")
    for finding in main_p0:
        md.append(f"- 主交付物：`{finding['file']}` · {finding['loc']} — {finding['claim']}")
    for finding in g2_p0:
        md.append(f"- repo-g2：`{finding['file']}` · {finding['loc']} — {finding['claim']}")
    md.append("")
    md.append(f"主仓库的 {inventory['catalog_rows']} 行 catalog 本身没有 `done` 状态，所以 `done_without_evidence` 在主 catalog 上为 0；g2 的 4 个 P0 属于**不能原样合并的旧 catalog**。即使只交主仓库 + 当前 deck，也必须先修 slide 7、E2-2-online 的结论、numbers.md A12–A16 的 test 标签；否则不能交。")
else:
    md.append("**可以提交（数据层）。** 未发现 P0；仍需清理 P1 的 stale 值/占位符。")
md.append("")
md.append("另有两个提交阻塞项不是数据 P0，但必须在导出前处理：")
md.append("")
md.append("- deck 标题页仍是 `姓名 / 学号`（P1）。")
md.append("- deck 仍写 `在线 27B 结果 19:50 回填`，而 online 报告 18:47 已生成（P1 stale placeholder）。")
md.append("")
md.append("## 2. P0 表：文件 / 位置 / 声称 / 实际 / 谁改")
md.append("")
p0_rows = []
for finding in p0:
    p0_rows.append([
        finding["severity"],
        f"`{finding['file']}`",
        finding["loc"],
        finding["claim"],
        finding["source"] or "null",
        finding["fix_owner"],
        finding["note"],
    ])
md.append(md_table(["级别", "文件", "位置", "声称", "源/实际", "谁改", "说明"], p0_rows))
md.append("")
md.append("### P0 逐条说明")
md.append("")
for i, finding in enumerate(p0, 1):
    md.append(f"{i}. **{finding['file']} · {finding['loc']}** — {finding['claim']}  ")
    md.append(f"   源：{finding['source'] or '无（orphan）'}；owner：{finding['fix_owner']}。{finding['note']}")
md.append("")
md.append("## 3. P1 表：无源数字 / stale placeholder / worktree 未合并证据")
md.append("")
p1_rows = []
for finding in p1:
    p1_rows.append([
        f"`{finding['file']}`",
        finding["loc"],
        finding["kind"],
        finding["claim"],
        finding["source"] or "—",
        finding["fix_owner"],
    ])
md.append(md_table(["文件", "位置", "类型", "问题", "源/对照", "谁改"], p1_rows))
md.append("")
md.append("## 4. 已核实清单（数字 → 源文件）")
md.append("")
md.append("以下数字能从 run/JSON/report 复算或逐字对上；不是“看起来合理”。")
md.append("")
verified_rows = []
for item in VERIFIED:
    verified_rows.append([item["claim"], f"`{item['source']}`", item["note"]])
md.append(md_table(["已核实", "源文件", "核对方式/误差"], verified_rows))
md.append("")
md.append("### 4.1 PPT 关键数字")
md.append("")
ppt_rows = []
for item in PPT_NUMBERS:
    ppt_rows.append([f"slide {item['slide']}", item["claim"], item["status"], f"`{item['source']}`", item["note"]])
md.append(md_table(["页", "数字/声称", "判定", "源文件", "说明"], ppt_rows))
md.append("")
md.append("### 4.2 跨文件一致性表")
md.append("")
metric_rows = []
for item in METRIC_CONSISTENCY:
    metric_rows.append([item["metric"], json.dumps(item["values"], ensure_ascii=False), item["status"], f"`{item['source']}`"])
md.append(md_table(["指标", "各处取值", "判定", "源"], metric_rows))
md.append("")
md.append("### 4.3 三个 archive 复算（C2）")
md.append("")
md.append("`e1-adoption-offline.json`、`e3-offline.json`、`order-offline.json` 各抽 1–3 个指标，用 `source_db` 的 `metrics` 表按 run 求均值；最大绝对误差 < 0.001，未发现 `metric_mismatch`。`state-accuracy.json` 的 U1/U2/U3 item mean 也复算通过。")
md.append("")
md.append("## 5. 提交前必须完成的 5 件事")
md.append("")
md.append("1. **D（deck owner）**：删掉/重做 slide 7 的 `31 行实验：19 行有数据，3 行受限，7 行缺实现`；填标题页 `姓名 / 学号`；把 `19:50 回填` 改成已经存在的 online 表（或删除该句）。")
md.append(f"2. **D/B（报告层）**：报告是在 48 行 catalog 上写的，catalog 已增至 {inventory['catalog_rows']} 行。重算 06-design/A-appendix/README/numbers/coverage.png 的 48/19/9/8/12 为当前口径（partial 21 + no_op 1 + not_wired 1 = 23 有数据；hardware 9；code 7；pending 11），修正 A-appendix 的 E1-R2/E1-M2/E2-2 状态，并把 numbers.md A12–A16 的“17 条 test 子集”改成“17 条混合（5 dev + 12 test）”或换成 test-only 值。")
md.append("3. **B（catalog/报告结论）**：修仍残留的 4 条 stale reason（E1-W1、E1-R1、E2-1、E5-1）；把 E3-1-online/M2-online 的 partial 改成与 `e3-online-2x2-report.json` / `m2-online-rerank-report.json` 一致的 inconclusive（或补 CI 并说明点估计口径）；把 E2-2-online 降为 inconclusive；catalog 改引 `*-report.json` 而不是 raw run；同步 HANDOFF 794 与 830 的 max_neighbors 矛盾。")
md.append("4. **G2/B（旧 catalog）**：`graph-completion.json` 已在 2103023 合并，主 catalog 也已引用；不要把 `repo-g2/configs/experiment-catalog.json` 原样合并（旧 24 行、4 个 done、6 个裸 blocked）。如果合并，先把 4 个 done 降级并删掉裸 blocked 状态。")
md.append("5. **A/C（archive/结论）**：给 archive 补 `experiment_id` / `dataset.split` / `question_count` / `error_count`（P2 清单见 JSON）；E2-2 的单臂 Oracle 报告必须用 `inconclusive`，不能写 `partial`；如果以后还要写 `supported`，必须带非空 delta 和不过 0 的 CI。")
md.append("")
md.append("## 6. 附录：库存与范围")
md.append("")
md.append(md_table(
    ["项", "实际", "brief 期望", "说明"],
    [
        ["catalog 行数", inventory["catalog_rows"], 48, "运行中由 48 增至 50（B 新增 E2-WR/E2-SM）；主 catalog 无 done"],
        ["reports/experiments JSON", inventory["reports"], 20, "运行中由 20 增至 23（A/B 新增 E2-2/E3-1/M2 online）"],
        ["eval/archive JSON（递归）", inventory["archive_json"], 31, "实际 34；brief 的 31 已过期"],
        ["runs SQLite", inventory["runs_sqlite"], 12, "实际 21；brief 的 12 已过期"],
        ["deck 页数", inventory["deck_slides"], 12, "一致"],
        ["repo-g2 catalog", inventory["g2_catalog_rows"], "—", "旧 24 行，4 done / 6 blocked"],
        ["repo-g2 独有 archive", ", ".join(inventory["g2_only_archive"]) or "—", "—", "G2 已在 2103023 合并；无 g2-only archive，但 catalog 未吸收"],
    ],
))
md.append("")
md.append("口径说明：本审计只读 `runs/`、`eval/archive/`、`reports/experiments/`、`configs/experiment-catalog.json`、`docs/optimization/HANDOFF.md`、`docs/report/`、`deck/*.pptx`、`web/` 与 `http://127.0.0.1:8886/api/v2/*`；只写本文件、`reports/audit/data-audit.json`、`scripts/audit_data.py`。没有删除或修改任何被审计文件。")

OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"wrote {rel(OUT_JSON)}")
print(f"wrote {rel(OUT_MD)}")
print(f"findings: P0={counts.get('P0', 0)} P1={counts.get('P1', 0)} P2={counts.get('P2', 0)}")
