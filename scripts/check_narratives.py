#!/usr/bin/env python3
"""Check the Chinese narrative layer against the experiment reports.

Rules enforced here:
  * every evidence.value must appear verbatim in its source_report;
  * every source_report path after '#' must resolve in the JSON;
  * headline_zh must contain a digit and be <= 30 characters;
  * analysis_zh must be 200-350 characters (non-whitespace count);
  * caveats_zh must have 1-3 items (at least one "cannot say what");
  * metrics_zh must have >= 3 entries with a Chinese label;
  * overview.json must have 5 blocks, each with a digit in its headline.

Run: python3 scripts/check_narratives.py
Exit code 0 prints ALL OK; any problem exits 1 and prints the list.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NARR_DIR = ROOT / "reports" / "narratives"
EXP_DIR = NARR_DIR / "experiments"

CJK = re.compile(r"[\u4e00-\u9fff]")
TOKEN = re.compile(r"\.?([A-Za-z0-9_-]+)|\[(\d+)\]|\[\"([^\"]*)\"\]|\['([^']*)'\]")
ALLOWED_STATUS = {"支持", "部分支持", "无定论", "不支持", "待验证"}

problems: list[str] = []
notes: list[str] = []
stats = {"experiments": 0, "evidence": 0}


def fail(where: str, message: str) -> None:
    problems.append(f"{where}: {message}")


def non_ws_len(text: str) -> int:
    return len(re.sub(r"\s", "", text or ""))


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        fail(str(path.relative_to(ROOT)), f"cannot read ({exc})")
    except json.JSONDecodeError as exc:
        fail(str(path.relative_to(ROOT)), f"invalid JSON ({exc})")
    return None


def split_source(source: str) -> tuple[Path, str]:
    if "#" in source:
        head, fragment = source.split("#", 1)
    else:
        head, fragment = source, ""
    return (ROOT / head), fragment


def resolve(doc, fragment: str):
    """Resolve 'a.b[0]["c"]' against doc. Raises KeyError/IndexError/ValueError."""
    cur = doc
    pos = 0
    while pos < len(fragment):
        match = TOKEN.match(fragment, pos)
        if not match:
            raise ValueError(f"cannot parse path at {fragment[pos:]!r}")
        dotted, index, quoted, single = match.groups()
        if dotted is not None:
            if not isinstance(cur, dict) or dotted not in cur:
                raise KeyError(dotted)
            cur = cur[dotted]
        elif index is not None:
            cur = cur[int(index)]
        else:
            key = quoted if quoted is not None else single
            if not isinstance(cur, dict) or key not in cur:
                raise KeyError(key)
            cur = cur[key]
        pos = match.end()
    return cur


def canonical(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, str)):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    return json.dumps(value, ensure_ascii=False)


def value_matches(expected: str, actual) -> bool:
    if expected == canonical(actual):
        return True
    try:
        return abs(float(expected) - float(actual)) <= 1e-9 * max(1.0, abs(float(actual)))
    except (TypeError, ValueError):
        return False


def check_evidence(where: str, evidence, raw_cache: dict[Path, str]) -> None:
    if not isinstance(evidence, list) or not evidence:
        fail(where, "evidence is empty")
        return
    for i, item in enumerate(evidence):
        tag = f"{where} evidence[{i}]"
        if not isinstance(item, dict):
            fail(tag, "not an object")
            continue
        for key in ("text_zh", "value", "source"):
            if not item.get(key):
                fail(tag, f"missing {key}")
        source = str(item.get("source") or "")
        expected = str(item.get("value") or "")
        if not source or not expected:
            continue
        stats["evidence"] += 1
        if not CJK.search(str(item.get("text_zh") or "")):
            fail(tag, "text_zh is not Chinese")
        report_path, fragment = split_source(source)
        if not report_path.is_file():
            fail(tag, f"source file not found: {source}")
            continue
        raw = raw_cache.get(report_path)
        if raw is None:
            raw = report_path.read_text(encoding="utf-8", errors="replace")
            raw_cache[report_path] = raw
        doc = load_json(report_path)
        if doc is None:
            continue
        if fragment:
            try:
                actual = resolve(doc, fragment)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                fail(tag, f"path does not resolve: {source} ({exc})")
                continue
            if not value_matches(expected, actual):
                fail(tag, f"value {expected!r} != JSON {canonical(actual)!r} at {source}")
                continue
        if expected not in raw:
            fail(tag, f"value {expected!r} not found verbatim in {source.split('#')[0]}")


def check_experiment(path: Path, raw_cache: dict[Path, str]) -> None:
    doc = load_json(path)
    if doc is None:
        return
    stats["experiments"] += 1
    eid = path.stem
    where = f"experiments/{eid}"
    if doc.get("schema") != "memlab/narrative@1":
        fail(where, f"schema is {doc.get('schema')!r}")
    if doc.get("experiment_id") != eid:
        fail(where, f"experiment_id {doc.get('experiment_id')!r} != filename")
    source_report = str(doc.get("source_report") or "")
    if not source_report or not (ROOT / source_report).is_file():
        fail(where, f"source_report missing or not found: {source_report!r}")
    status = doc.get("status_zh")
    if status not in ALLOWED_STATUS:
        fail(where, f"status_zh {status!r} not in {sorted(ALLOWED_STATUS)}")
    for key in ("headline_zh", "summary_zh", "analysis_zh", "next_zh"):
        if not str(doc.get(key) or "").strip():
            fail(where, f"missing {key}")
    headline = str(doc.get("headline_zh") or "")
    if not re.search(r"\d", headline):
        fail(where, "headline_zh has no digit")
    if len(headline) > 30:
        fail(where, f"headline_zh is {len(headline)} chars (>30)")
    analysis = str(doc.get("analysis_zh") or "")
    size = non_ws_len(analysis)
    if not 200 <= size <= 350:
        fail(where, f"analysis_zh is {size} chars (200-350 required)")
    caveats = doc.get("caveats_zh") or []
    if not isinstance(caveats, list) or not 1 <= len(caveats) <= 3:
        fail(where, f"caveats_zh must have 1-3 items, got {len(caveats) if isinstance(caveats, list) else 'n/a'}")
    else:
        for i, caveat in enumerate(caveats):
            if not CJK.search(str(caveat)):
                fail(where, f"caveats_zh[{i}] is not Chinese")
    metrics = doc.get("metrics_zh") or []
    if not isinstance(metrics, list) or len(metrics) < 3:
        fail(where, "metrics_zh must have >= 3 entries")
    else:
        for i, metric in enumerate(metrics):
            if not CJK.search(str(metric.get("label_zh") or "")):
                fail(where, f"metrics_zh[{i}].label_zh is not Chinese")
            if not str(metric.get("value") or "").strip():
                fail(where, f"metrics_zh[{i}].value is empty")
    check_evidence(where, doc.get("evidence"), raw_cache)


def check_overview(raw_cache: dict[Path, str]) -> None:
    path = NARR_DIR / "overview.json"
    if not path.is_file():
        fail("overview.json", "missing")
        return
    doc = load_json(path)
    if doc is None:
        return
    if doc.get("schema") != "memlab/narrative@1":
        fail("overview.json", f"schema is {doc.get('schema')!r}")
    headline = str(doc.get("headline_zh") or "")
    if not CJK.search(headline) or not re.search(r"\d", headline):
        fail("overview.json", "headline_zh must be Chinese and contain a digit")
    overall = str(doc.get("overall_zh") or "")
    size = non_ws_len(overall)
    if not 300 <= size <= 500:
        fail("overview.json", f"overall_zh is {size} chars (300-500 required)")
    blocks = doc.get("blocks") or []
    if not isinstance(blocks, list) or len(blocks) != 5:
        fail("overview.json", f"blocks must be exactly 5, got {len(blocks) if isinstance(blocks, list) else 'n/a'}")
        return
    for i, block in enumerate(blocks):
        where = f"overview.json blocks[{i}]"
        for key in ("id", "title_zh", "headline_zh", "body_zh"):
            if not str(block.get(key) or "").strip():
                fail(where, f"missing {key}")
        if not CJK.search(str(block.get("title_zh") or "")):
            fail(where, "title_zh is not Chinese")
        if not re.search(r"\d", str(block.get("headline_zh") or "")):
            fail(where, "headline_zh has no digit")
        body_size = non_ws_len(str(block.get("body_zh") or ""))
        if not 150 <= body_size <= 250:
            fail(where, f"body_zh is {body_size} chars (150-250 required)")
        check_evidence(where, block.get("evidence"), raw_cache)


def check_web_sync() -> None:
    """Optional: keep the v2.js embedded copy identical to the JSON sources."""
    js = ROOT / "web" / "v2.js"
    if not js.is_file():
        return
    text = js.read_text(encoding="utf-8")
    expected = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(EXP_DIR.glob("*.json"))}
    expected_overview = json.loads((NARR_DIR / "overview.json").read_text(encoding="utf-8"))

    def extract(marker: str):
        start = text.find(marker)
        if start < 0:
            return None
        brace = text.find("{", start)
        if brace < 0:
            return None
        depth, in_str, escape = 0, False, False
        for pos in range(brace, len(text)):
            ch = text[pos]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace:pos + 1])
                    except json.JSONDecodeError as exc:
                        fail("web/v2.js", f"cannot parse embedded {marker}: {exc}")
                        return None
        return None

    embedded = extract("const NARRATIVES =")
    if embedded is None:
        notes.append("web/v2.js has no embedded NARRATIVES yet (phase A); sync check skipped")
    elif embedded != expected:
        missing = sorted(set(expected) - set(embedded))
        extra = sorted(set(embedded) - set(expected))
        changed = sorted(k for k in set(expected) & set(embedded) if expected[k] != embedded[k])
        fail("web/v2.js", f"NARRATIVES out of sync (missing={missing}, extra={extra}, changed={changed})")
    overview = extract("const NARRATIVE_OVERVIEW =")
    if overview is not None and overview != expected_overview:
        fail("web/v2.js", "NARRATIVE_OVERVIEW out of sync with reports/narratives/overview.json")


def main() -> int:
    raw_cache: dict[Path, str] = {}
    files = sorted(EXP_DIR.glob("*.json")) if EXP_DIR.is_dir() else []
    if not files:
        fail("reports/narratives/experiments", "no narrative JSON files found")
    for path in files:
        check_experiment(path, raw_cache)
    check_overview(raw_cache)
    check_web_sync()

    for note in notes:
        print(f"NOTE: {note}")
    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"ALL OK: {stats['experiments']} experiments, {stats['evidence']} evidence values verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
