"""Extract structured facts from the course conversations (resumable).

    python scripts/extract.py --batch-size 15
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memwb import config, dataset, extraction  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", nargs="+", default=config.COURSE_SAMPLES)
    parser.add_argument("--batch-size", type=int, default=15)
    args = parser.parse_args()
    incomplete = {}
    for sid in args.samples:
        missing = extraction.extract(dataset.store().get(sid), args.batch_size, log=lambda s: print(s, flush=True))
        if missing:
            incomplete[sid] = missing
    if incomplete:
        print(json.dumps({"incomplete": incomplete}), flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
