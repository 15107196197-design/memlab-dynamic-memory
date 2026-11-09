#!/usr/bin/env bash
# Render the three memory-visualization mockups to 3200x2000 PNG.
set -euo pipefail
cd "$(dirname "$0")"

CHROME="${CHROME:-$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell}"
if [ ! -x "$CHROME" ]; then
  echo "chrome-headless-shell not found: $CHROME" >&2
  echo "set CHROME=/path/to/chrome-headless-shell" >&2
  exit 1
fi

python3 m1_records.py
python3 m2_timeline.py
python3 m3_graph.py

for f in m1-records m2-timeline m3-graph; do
  "$CHROME" --headless=new --no-sandbox --disable-gpu --disable-gpu-sandbox \
    --use-angle=swiftshader --hide-scrollbars --force-device-scale-factor=2 \
    --window-size=1600,1000 --screenshot="$PWD/$f.png" "$PWD/$f.html" 2>&1 | tail -1
done
