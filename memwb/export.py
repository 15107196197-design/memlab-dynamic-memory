"""Unified JSON export of the structured memory of one conversation."""
from datetime import datetime

from . import config, dataset, memory

SCHEMA = "dynamic-memory-workbench/memory-export@1"


def slots_table(sample_id, facts):
    """Slots (state aspects) with their chronologically ordered versions."""
    states = memory.load_states(sample_id)
    if not states:
        return []
    by_id = {f["memory_id"]: f for f in facts}
    out = []
    for key, slot in states.get("slots", {}).items():
        out.append({
            "key": key, "entity": slot["entity"], "slot": slot["slot"], "kind": slot["kind"],
            "description": slot.get("description", ""),
            "versions": [{"memory_id": fid, "turn": by_id[fid]["source"]["turn"], "session_time": by_id[fid]["session_time"],
                          "value": by_id[fid]["value"], "state": slot["status"].get(fid, "ACTIVE")}
                         for fid in slot["facts"] if fid in by_id],
            "relations": [{"from": r["from"], "to": r["to"], "type": r["type"], "reason": r.get("reason", "")} for r in slot["relations"]],
        })
    out.sort(key=lambda s: (-len(s["versions"]), s["key"]))
    return out


def summary(sample):
    turns, facts = memory.build(sample)
    sid = sample["sample_id"]
    states = memory.load_states(sid)
    times = [t["session_time"] for t in turns if t["session_time"]]
    return {
        "id": sid,
        "split": config.split_of(sid),
        "speakers": sorted({t["entity"] for t in turns}),
        "sessions": len({t["source"]["session"] for t in turns}),
        "turns": len(turns),
        "extracted_turns": sum(t["fact_extraction"] != "pending" for t in turns),
        "facts": len(facts),
        "states_ready": bool(states and states.get("complete")),
        "slots": len(states.get("slots", {})) if states else 0,
        "qa": len(sample.get("qa", [])),
        "first": min(times) if times else None,
        "last": max(times) if times else None,
    }


def export(sample):
    sid = sample["sample_id"]
    turns, facts = memory.build(sample)
    text = {t["memory_id"]: t["content"] for t in turns}
    state_counts = {}
    for f in facts:
        state_counts[f["state"]] = state_counts.get(f["state"], 0) + 1
    return {
        "schema": SCHEMA,
        "conversation": sid,
        "split": config.split_of(sid),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "extraction_model": config.extraction_model(),
        "notes": [
            "timestamp/session_time are session recording times without timezone, not necessarily event times.",
            "Facts, slots, states and relations are machine-generated and unverified; source.turn points to the original evidence.",
        ],
        "counts": {"turns": len(turns), "memories": len(facts), "states": state_counts},
        "memories": [{**{k: v for k, v in f.items() if k != "source_memory_id"}, "source_text": text[f["source_memory_id"]],
                      "source_memory_id": f["source_memory_id"]} for f in facts],
        "turns": [{k: v for k, v in t.items() if k != "evidence"} | {"speaker": t["entity"], "blip_caption": t["evidence"].get("blip_caption")} for t in turns],
        "slots": slots_table(sid, facts),
    }


def export_all(sample_ids=None):
    store = dataset.store()
    return {sid: export(store.get(sid)) for sid in (sample_ids or config.COURSE_SAMPLES)}
