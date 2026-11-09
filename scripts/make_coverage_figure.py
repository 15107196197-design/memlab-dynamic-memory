#!/usr/bin/env python3
"""Regenerate docs/report/figures/coverage.png from configs/experiment-catalog.json.

The report groups catalog statuses into four display buckets:
  data     = partial + no_op + not_wired
  hardware = blocked_on_hardware
  code     = blocked_on_code
  pending  = pending

Usage: python scripts/make_coverage_figure.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "configs" / "experiment-catalog.json"
OUTPUT = ROOT / "docs" / "report" / "figures" / "coverage.png"

BG = (247, 249, 252)
INK = (15, 23, 42)
MUTED = (91, 107, 132)
WHITE = (255, 255, 255)
COLORS = [(5, 150, 105), (217, 119, 6), (148, 163, 184), (203, 213, 225)]

WIDTH, HEIGHT = 1600, 900
LEFT, RIGHT = 93, 1508
BAR_TOP, BAR_BOTTOM = 333, 478
BAR_GAP = 5

LABELS = ["有数据", "硬件/依赖受限", "缺实现", "待跑"]


def _load_font(candidates, size):
    for path, index in candidates:
        try:
            return ImageFont.truetype(str(path), size, index=index)
        except (OSError, ValueError):
            continue
    raise RuntimeError(f"no usable font among {candidates}")


def cjk_font(size):
    candidates = []
    # macOS ships PingFang as an on-demand asset.
    for path in sorted(Path("/System/Library/AssetsV2").glob("**/PingFang.ttc")):
        candidates.append((path, 3))  # PingFang SC Regular
    candidates += [
        (Path("/System/Library/Fonts/PingFang.ttc"), 0),
        (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),
        (Path("/System/Library/Fonts/STHeiti Light.ttc"), 0),
        (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0),
        (Path("/Library/Fonts/Arial Unicode.ttf"), 0),
    ]
    return _load_font(candidates, size)


def latin_font(size):
    candidates = [
        (Path("/System/Library/Fonts/SFNS.ttf"), 0),
        (Path("/System/Library/Fonts/HelveticaNeue.ttc"), 0),
        (Path("/System/Library/Fonts/Helvetica.ttc"), 0),
    ]
    try:
        return _load_font(candidates, size)
    except RuntimeError:
        return cjk_font(size)


def draw_ink(draw, x, y, text, font, fill):
    """Draw text so its ink box starts at (x, y); returns the ink width."""
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((x - box[0], y - box[1]), text, font=font, fill=fill)
    return box[2] - box[0]


def draw_center(draw, cx, y, text, font, fill):
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw_ink(draw, cx - width / 2, y, text, font, fill)
    return width


def coverage_counts(catalog):
    status = [item.get("status") for item in catalog["items"]]
    counts = {
        "partial": status.count("partial"),
        "no_op": status.count("no_op"),
        "not_wired": status.count("not_wired"),
        "hardware": status.count("blocked_on_hardware"),
        "code": status.count("blocked_on_code"),
        "pending": status.count("pending"),
    }
    counts["total"] = len(status)
    counts["data"] = counts["partial"] + counts["no_op"] + counts["not_wired"]
    counts["online"] = sum(
        1
        for item in catalog["items"]
        if item.get("grade") in ("offline+online", "online")
    )
    assert counts["data"] + counts["hardware"] + counts["code"] + counts["pending"] == counts["total"]
    return counts


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    c = coverage_counts(catalog)
    values = [c["data"], c["hardware"], c["code"], c["pending"]]
    total = c["total"]

    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    title = f"实验覆盖：{total} 行 catalog 中 {c['data']} 行有可追溯证据"
    subtitle = (
        f"按 configs/experiment-catalog.json（{catalog.get('updated', '')}）"
        "的状态归并；括号内为原始 status 行数"
    )
    draw_ink(draw, LEFT, 71, title, cjk_font(47), INK)
    draw_ink(draw, LEFT, 137, subtitle, cjk_font(21), MUTED)

    available = RIGHT - LEFT - BAR_GAP * (len(values) - 1)
    widths = [round(v / total * available) for v in values]
    widths[-1] = RIGHT - LEFT - sum(widths[:-1]) - BAR_GAP * (len(values) - 1)

    number_font = latin_font(56)
    label_font = cjk_font(21)
    pct_font = cjk_font(18)
    x = LEFT
    for index, (value, width) in enumerate(zip(values, widths)):
        color = COLORS[index]
        draw.rectangle([x, BAR_TOP, x + width - 1, BAR_BOTTOM - 1], fill=color)
        number_color = WHITE if index < 2 else INK
        draw_center(draw, x + width / 2, 348, str(value), number_font, number_color)
        draw_center(draw, x + width / 2, 515, LABELS[index], label_font, INK)
        draw_center(
            draw,
            x + width / 2,
            548,
            f"{round(value / total * 100)}%",
            pct_font,
            MUTED,
        )
        x += width + BAR_GAP

    # Legend.
    legend_font = cjk_font(22)
    legend_y = 621
    square = 25
    for index, (value, width) in enumerate(zip(values, widths)):
        lx = LEFT + index * 330
        draw.rectangle([lx, legend_y, lx + square - 1, legend_y + square - 1], fill=COLORS[index])
        draw_ink(draw, lx + square + 13, legend_y + 2, f"{LABELS[index]} {value} 行", legend_font, INK)

    # Footnotes.
    foot_font = cjk_font(20)
    lines = [
        f"有数据 = partial {c['partial']} + no_op {c['no_op']} + not_wired {c['not_wired']}；"
        f"其中多数是 offline A 级，只有 {c['online']} 条有 online 报告。",
        f"硬件/依赖受限 = blocked_on_hardware {c['hardware']}；"
        f"缺实现 = blocked_on_code {c['code']}；待跑 = pending {c['pending']}。",
        "deck 第 7 页用原始 status 计数；本图把原始 status 归并为四类口径。",
    ]
    for index, line in enumerate(lines):
        draw_ink(draw, LEFT - 2, 740 + index * 38, line, foot_font, MUTED)

    source = "来源：configs/experiment-catalog.json · 状态计数见 numbers.md"
    source_font = cjk_font(17)
    box = draw.textbbox((0, 0), source, font=source_font)
    draw_ink(draw, RIGHT - box[2], 861, source, source_font, MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, optimize=True)
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {total} rows, {values}")


if __name__ == "__main__":
    main()
