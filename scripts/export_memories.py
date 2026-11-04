"""Write the unified structured-memory JSON of every course conversation to exports/.

    python scripts/export_memories.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memwb import config, export  # noqa: E402


def main():
    config.EXPORT_DIR.mkdir(exist_ok=True)
    for sid, data in export.export_all().items():
        path = config.EXPORT_DIR / f"{sid}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf8")
        print(sid, data["counts"])


if __name__ == "__main__":
    main()
