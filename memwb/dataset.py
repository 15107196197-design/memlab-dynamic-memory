"""LoCoMo conversations: loading, validation and persistent user imports."""
import hashlib
import json
import re
import threading

from . import config

SAMPLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}")
SESSION_KEY = re.compile(r"session_(\d+)")


def validate(sample):
    """Check the LoCoMo structure the application relies on; return a normalised copy."""
    if not isinstance(sample, dict):
        raise ValueError("Each conversation must be an object")
    sid = sample.get("sample_id")
    if not isinstance(sid, str) or not SAMPLE_ID.fullmatch(sid):
        raise ValueError("Invalid sample_id: use letters, numbers, underscore or hyphen")
    conversation = sample.get("conversation")
    if not isinstance(conversation, dict):
        raise ValueError("conversation must be an object")
    seen, total = set(), 0
    for key, turns in conversation.items():
        if not SESSION_KEY.fullmatch(key):
            continue
        if not isinstance(turns, list):
            raise ValueError(f"{key} must be a list")
        recorded = conversation.get(key + "_date_time")
        if not isinstance(recorded, str) or not recorded.strip():
            raise ValueError(f"{key} requires a recording time")
        for turn in turns:
            if not isinstance(turn, dict) or not all(isinstance(turn.get(f), str) for f in ("dia_id", "speaker", "text")):
                raise ValueError(f"{key} turns need dia_id, speaker and text strings")
            if turn["dia_id"] in seen:
                raise ValueError("Duplicate turn: " + turn["dia_id"])
            seen.add(turn["dia_id"])
            total += 1
    if not total:
        raise ValueError("No session turns found")
    if "qa" in sample and not isinstance(sample["qa"], list):
        raise ValueError("qa must be a list")
    return {**sample, "qa": sample.get("qa", [])}


def sessions(sample):
    """Yield (session_number, recorded_time, turns) in session order."""
    conversation = sample["conversation"]
    numbered = []
    for key, turns in conversation.items():
        match = SESSION_KEY.fullmatch(key)
        if match and isinstance(turns, list):
            numbered.append((int(match.group(1)), conversation.get(key + "_date_time"), turns))
    return sorted(numbered, key=lambda x: x[0])


class Store:
    """In-memory list of conversations plus the user's persistent imports."""

    def __init__(self, data_file=None, import_dir=None):
        self.data_file = data_file or config.DATA_FILE
        self.import_dir = import_dir or config.IMPORT_DIR
        self.samples = json.loads(self.data_file.read_text(encoding="utf-8"))
        self._lock = threading.Lock()
        self._load_imported()

    def ids(self):
        return [s["sample_id"] for s in self.samples]

    def get(self, sample_id):
        sample = next((s for s in self.samples if s["sample_id"] == sample_id), None)
        if sample is None:
            raise KeyError(f"Unknown conversation: {sample_id}")
        return sample

    def _destination(self, sample_id):
        return self.import_dir / (hashlib.sha256(sample_id.encode("utf8")).hexdigest() + ".json")

    def _load_imported(self):
        if not self.import_dir.exists():
            return
        known = {s.casefold() for s in self.ids()}
        for file in sorted(self.import_dir.glob("*.json")):
            sample = validate(json.loads(file.read_text(encoding="utf8")))
            if sample["sample_id"].casefold() in known:
                raise ValueError("Duplicate stored conversation: " + sample["sample_id"])
            self.samples.append(sample)
            known.add(sample["sample_id"].casefold())

    def import_samples(self, payload):
        """Validate and atomically persist one conversation or a list of them."""
        incoming = payload if isinstance(payload, list) else [payload]
        if not incoming:
            raise ValueError("No conversations provided")
        checked = [validate(x) for x in incoming]
        with self._lock:
            ids = [x["sample_id"] for x in checked]
            folded = {v.casefold() for v in ids}
            if len(folded) != len(ids) or folded & {v.casefold() for v in self.ids()}:
                raise ValueError("Conversation ID already exists; no data was imported")
            self.import_dir.mkdir(parents=True, exist_ok=True)
            pending, committed = [], []
            try:
                # Stage every file first so that a failure leaves no partial batch behind.
                for sample in checked:
                    dest = self._destination(sample["sample_id"])
                    if dest.exists():
                        raise ValueError("Import destination already exists")
                    tmp = dest.with_suffix(".json.tmp")
                    with tmp.open("x", encoding="utf8") as f:
                        pending.append((tmp, dest))
                        json.dump(sample, f, ensure_ascii=False, indent=2)
                for tmp, dest in pending:
                    tmp.replace(dest)
                    committed.append(dest)
            except Exception:
                for tmp, _ in pending:
                    tmp.unlink(missing_ok=True)
                for dest in committed:
                    dest.unlink(missing_ok=True)
                raise
            self.samples.extend(checked)
        return ids


_store = None


def store():
    global _store
    if _store is None:
        _store = Store()
    return _store


def set_store(value):
    """Replace the shared store (used by tests)."""
    global _store
    _store = value
