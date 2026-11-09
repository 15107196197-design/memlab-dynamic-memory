#!/usr/bin/env bash
# Re-render all five figures to 3200x2000 PNG.
set -euo pipefail
cd "$(dirname "$0")"

CHROME="${CHROME:-$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell}"
if [ ! -x "$CHROME" ]; then
  echo "chrome-headless-shell not found: $CHROME" >&2
  echo "set CHROME=/path/to/chrome-headless-shell" >&2
  exit 1
fi

python3 a_stack.py
python3 b_mindmap.py
python3 c_metro.py
python3 d_hexring.py
python3 e_tree.py

for f in 01-isometric-stack 02-radial-mindmap 03-metro-map 04-hex-contract-ring 05-diagnosis-tree; do
  "$CHROME" --headless=new --no-sandbox --disable-gpu --disable-gpu-sandbox \
    --use-angle=swiftshader --hide-scrollbars --force-device-scale-factor=2 \
    --window-size=1600,1000 --screenshot="$PWD/$f.png" "$PWD/$f.html" 2>&1 | tail -1
done
