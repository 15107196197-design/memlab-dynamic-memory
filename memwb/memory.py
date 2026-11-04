"""Structured memory records built from LoCoMo turns.

Two layers are produced for every conversation:

* turn memories   - one per utterance; the retrieval unit and the raw evidence.
* fact memories   - machine-extracted (entity, attribute, value) facts, each linked
                    to its source turn and, when available, to the offline state
                    resolution (slot, validity state, version relations).
"""
import json
import re
from datetime import datetime, time, timedelta

from . import config, dataset

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
RELATIVE_DAY = re.compile(
    r"\b(?:yesterday|today|tomorrow|last\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
    re.IGNORECASE,
)
FIGURATIVE_YESTERDAY = re.compile(r"(?:feel(?:s|t)?|seem(?:s|ed)?)\s+like\s+(?:it\s+was\s+)?(?:just\s+)?$")


def session_date(value):
    """Parse LoCoMo's '1:56 pm on 8 May, 2023' format; None when unparseable."""
    try:
        return datetime.strptime(value, "%I:%M %p on %d %B, %Y")
    except (ValueError, TypeError):
        return None


def iso_date(value):
    parsed = session_date(value)
    return parsed.isoformat(timespec="minutes") if parsed else None


def resolve_relative_dates(text, timestamp):
    """Resolve a narrow set of relative day expressions against the recording date.

    The result is a heuristic: quotes or reported speech can make it wrong, and the
    data carries no timezone.
    """
    reference = session_date(timestamp)
    if not reference:
        return []
    found = []
    for match in RELATIVE_DAY.finditer(text):
        phrase = match.group(0)
        normalized = " ".join(phrase.lower().split())
        prefix = text[max(0, match.start() - 35):match.start()].lower()
        if normalized == "yesterday" and FIGURATIVE_YESTERDAY.search(prefix):
            continue  # "feels like just yesterday" does not date anything
        if normalized in ("yesterday", "today", "tomorrow"):
            offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[normalized]
        else:
            target = WEEKDAYS.index(normalized.split()[-1])
            offset = -((reference.weekday() - target) % 7 or 7)
        found.append({
            "expression": phrase,
            "date": (reference + timedelta(days=offset)).date().isoformat(),
            "basis": "heuristic relative to session recording date; timezone unknown",
        })
    return found


def dataset_observations(sample):
    """Map the dataset's own observation annotations to every turn they cite."""
    out = {}
    observations = sample.get("observation", {})
    if not isinstance(observations, dict):
        return out
    for session, group in observations.items():
        if not isinstance(group, dict):
            continue
        for entity, items in group.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not (isinstance(item, list) and len(item) >= 2 and isinstance(item[0], str) and isinstance(item[1], str)):
                    continue
                refs = list(dict.fromkeys(re.findall(r"D\d+:\d+", item[1])))
                for turn in refs:
                    out.setdefault(turn, []).append({
                        "entity": entity, "content": item[0], "source_turns": refs,
                        "origin": "dataset_annotation", "session_annotation": session,
                    })
    return out


def turn_id(sample_id, turn):
    return sample_id.replace("-", "") + "_" + turn.replace(":", "_")


def fact_id(sample_id, turn, index):
    return f"{turn_id(sample_id, turn)}_f{index}"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_facts(sample_id):
    path = config.FACTS_DIR / f"{sample_id}--{config.model_slug(config.extraction_model())}.json"
    data = _load_json(path)
    return data.get("turns", {}) if data else {}


def consistent_status(fact_ids, chain):
    """Validity per fact, made consistent with the chain's relations:
    the source of an UPDATE/SUPERSEDE is history; both ends of a CONFLICT are in conflict."""
    status = {f: chain.get("status", {}).get(f, "ACTIVE") for f in fact_ids}
    for rel in chain.get("relations", []):
        if rel["type"] in ("UPDATE", "SUPERSEDE") and status.get(rel["from"]) == "ACTIVE":
            status[rel["from"]] = "HISTORICAL"
        if rel["type"] == "CONFLICT":
            for f in (rel["from"], rel["to"]):
                if status.get(f) == "ACTIVE":
                    status[f] = "CONFLICT"
    return status


def load_states(sample_id):
    """Offline state slots; version chains resolved so far are merged in (resumable builds)."""
    path = config.STATES_DIR / f"{sample_id}--{config.model_slug(config.extraction_model())}.json"
    data = _load_json(path)
    if data:
        for key, slot in data.get("slots", {}).items():
            chain = data.get("chains", {}).get(key)
            if chain:
                slot["relations"] = chain["relations"]
                slot["status"] = consistent_status(slot["facts"], chain)
    return data


def state_index(states):
    """fact_id -> {slot_key, slot, kind, state, relations}"""
    index = {}
    if not states:
        return index
    for key, slot in states.get("slots", {}).items():
        for fid in slot["facts"]:
            index[fid] = {
                "slot_key": key, "slot": slot["slot"], "kind": slot["kind"],
                "state": slot.get("status", {}).get(fid, "ACTIVE"), "relations": [],
            }
        for rel in slot.get("relations", []):
            if rel["from"] in index and rel["to"] in index:
                index[rel["to"]]["relations"].append({"type": rel["type"], "direction": "from", "memory_id": rel["from"], "reason": rel.get("reason", "")})
                index[rel["from"]]["relations"].append({"type": rel["type"], "direction": "to", "memory_id": rel["to"], "reason": rel.get("reason", "")})
    return index


def _fact_records(sample_id, turn, raw_facts, base, states):
    records = []
    for i, fact in enumerate(raw_facts or []):
        fid = fact_id(sample_id, turn["dia_id"], i)
        expr = fact.get("time_expression")
        resolved = next((r for r in base["resolved_time_expressions"] if expr and r["expression"].lower() in str(expr).lower()), None)
        record = {
            "memory_id": fid,
            "type": "fact",
            "content": f"{fact['entity']} · {fact['attribute'].replace('_', ' ')}: {fact['value']}",
            "entity": fact["entity"],
            "attribute": fact["attribute"],
            "value": fact["value"],
            "event": fact.get("event"),
            "time_expression": expr,
            "time_expression_in_source": (str(expr).casefold() in turn["text"].casefold()) if expr else None,
            "resolved_date": resolved["date"] if resolved else None,
            "timestamp": base["timestamp"],
            "session_time": base["session_time"],
            "source": base["source"],
            "source_memory_id": base["memory_id"],
            "extraction": "machine_unverified",
            "slot": None, "kind": None, "state": "UNRESOLVED", "relations": [],
        }
        if fid in states:
            info = states[fid]
            record.update(slot=info["slot"], slot_key=info["slot_key"], kind=info["kind"], state=info["state"], relations=info["relations"])
        records.append(record)
    return records


def build(sample):
    """Return (turn_memories, fact_memories) for one conversation."""
    sid = sample["sample_id"]
    observations = dataset_observations(sample)
    extracted = load_facts(sid)
    states = state_index(load_states(sid))
    turns, facts = [], []
    for number, recorded, items in dataset.sessions(sample):
        for turn in items:
            if not turn.get("text"):
                continue
            base = {
                "memory_id": turn_id(sid, turn["dia_id"]),
                "type": "turn",
                "content": turn["text"],
                "entity": turn.get("speaker"),
                "timestamp": recorded,
                "session_time": iso_date(recorded),
                "source": {"conversation": sid, "session": number, "turn": turn["dia_id"]},
                "resolved_time_expressions": resolve_relative_dates(turn["text"], recorded),
                "dataset_observations": observations.get(turn["dia_id"], []),
                "evidence": turn,
            }
            raw = extracted.get(turn["dia_id"])
            fact_records = _fact_records(sid, turn, raw, base, states)
            base["fact_extraction"] = "machine_unverified" if raw is not None else "pending"
            base["fact_ids"] = [f["memory_id"] for f in fact_records]
            # A turn is current unless every one of its stateful facts has been replaced.
            stateful = [f["state"] for f in fact_records if f["kind"] in ("state", "trait")]
            base["state"] = (
                "HISTORICAL" if stateful and all(s == "HISTORICAL" for s in stateful)
                else "CONFLICT" if "CONFLICT" in stateful
                else "ACTIVE" if fact_records and states else "UNRESOLVED"
            )
            turns.append(base)
            facts.extend(fact_records)
    return turns, facts


def turn_memories(sample):
    return build(sample)[0]


def apply_cutoff(items, as_of):
    """Keep memories recorded on or before as_of (YYYY-MM-DD). Recording date, not event date."""
    if not as_of:
        return items
    try:
        cutoff = datetime.combine(datetime.strptime(as_of, "%Y-%m-%d").date(), time.max)
    except (ValueError, TypeError):
        raise ValueError("截至日期格式必须为 YYYY-MM-DD")
    return [m for m in items if session_date(m["timestamp"]) is None or session_date(m["timestamp"]) <= cutoff]
