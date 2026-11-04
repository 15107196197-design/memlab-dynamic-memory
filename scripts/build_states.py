"""Build offline state slots and version chains for the course conversations.

    python scripts/build_states.py                 # all six course conversations
    python scripts/build_states.py --samples conv-26
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memwb import config, dataset, states  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", nargs="+", default=config.COURSE_SAMPLES)
    args = parser.parse_args()
    for sid in args.samples:
        states.build(dataset.store().get(sid), log=lambda line: print(line, flush=True))


if __name__ == "__main__":
    main()
