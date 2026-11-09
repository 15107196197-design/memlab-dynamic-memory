#!/usr/bin/env bash
# MemLab course report — reproduction entry point.
#
# These are the commands listed in report §8.3 and appendix A.3.  They were
# executed during the 2026-11-09 project run; the exact commands are kept here
# so the archived JSON can be traced back to a runnable entry point.
#
# Notes before running:
#   * The offline commands write into eval/archive/, reports/experiments/ and
#     runs/.  If you need to keep the committed archive untouched, copy those
#     directories aside first.
#   * The online command needs a reachable 27B Ollama/API endpoint; without one
#     it is expected to fail at the provider preflight.
#   * same-config reruns that differ by more than 0.01 must be recorded in the
#     report limitations (docs/optimization/04-experiments.md §4.15.7).
#   * caveat: the offline answer path is changing in parallel (STATUS-LEDGER
#     §5.3).  If a local rerun differs from the archived offline F1, record the
#     drift in limitations instead of editing the report numbers.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== full test suite =="
python -m unittest discover -s tests -t .

echo "== offline test B0/R0 (2 test conversations, 80 questions/config, seeds 13/17) =="
python scripts/final_w3.py --questions 20 --seeds 13 17

echo "== R3 graph retrieval (offline, category=1, 61 questions/cell) =="
python -m memlab.experiments.cli run \
  --spec configs/experiments/e1-r3-graph.json \
  --executor e2e --offline --limit 60 \
  --db runs/r3-graph/r3.sqlite

echo "== S6 six-module screening (offline) =="
python scripts/s6_e1.py --questions 80 --seeds 13 17 \
  --samples conv-26 conv-30 conv-43 conv-44

if [[ "${MEMLAB_ONLINE:-0}" == "1" ]]; then
  echo "== S6 six-module screening (online 27B; needs Ollama/API) =="
  python scripts/s6_e1.py --online --questions 40 --seeds 13 \
    --samples conv-26 conv-30 conv-43 conv-44
else
  echo "== S6 online 27B skipped; set MEMLAB_ONLINE=1 with a 27B endpoint to run it =="
fi

echo "== state benchmark =="
python scripts/state_accuracy.py
