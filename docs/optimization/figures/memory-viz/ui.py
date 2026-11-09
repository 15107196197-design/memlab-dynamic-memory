# -*- coding: utf-8 -*-
"""Shared UI chrome for the memory-visualization proposals."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import text, rect, line, path, circle, write_page, MONO, SANS  # noqa

BG = "#FAF9F5"
PANEL = "#FFFFFF"
LINE = "#E7E3D8"
LINE2 = "#F0EDE5"
INK = "#202A33"
MUT = "#7B7568"
FAINT = "#A9A294"
ACCENT = "#2F6F5E"
ACCENT_BG = "#EDF4F0"

STATE = {
    "ACTIVE": ("#2F7A4F", "#E9F3EC", "#256B43"),
    "HISTORICAL": ("#B07A2A", "#FBF1DF", "#8A5D16"),
    "CONFLICT": ("#A33B3B", "#F9E7E7", "#8E2B2B"),
    "UNRESOLVED": ("#6B7280", "#F0F1F3", "#4B5563"),
}
STATE_ZH = {"ACTIVE": "有效", "HISTORICAL": "历史", "CONFLICT": "冲突", "UNRESOLVED": "未解析"}

KIND = {"fact": "#2F6F9E", "event": "#8A6D3B", "turn": "#6B7280"}
KIND_ZH = {"fact": "事实", "event": "事件", "turn": "轮次"}

NAV = ["首页", "记忆库", "提问与状态", "实验台", "图谱 Graph", "评测对照", "系统"]


def topbar(active="记忆库", sample="conv-26 · Caroline & Melanie"):
    s = [rect(0, 0, 1600, 56, "#FFFFFF"),
         line(0, 56, 1600, 56, LINE, 1)]
    s.append(text(32, 35, "动态记忆工作台", 16, INK, 700, ls=0.5))
    x = 208
    for n in NAV:
        w = 88 if n in ("记忆库", "图谱 Graph", "评测对照") else 72
        if n == "图谱 Graph":
            w = 84
        on = n == active
        s.append(text(x, 34, n, 12, INK if on else "#5E6A72", 600 if on else 400))
        if on:
            s.append(rect(x - 2, 51, len(n) * 12 + 6, 2, INK, 1))
        x += w
    # sample + search
    s.append(rect(1248, 14, 232, 28, "#FCFBF7", 14, LINE, 1))
    s.append(text(1262, 32, sample, 10.5, "#4E5A62", 500))
    s.append(rect(1492, 14, 60, 28, "#FCFBF7", 14, LINE, 1))
    s.append(text(1522, 32, "搜索", 10, "#4E5A62", 500, anchor="middle"))
    return "".join(s)


def page_head(title, sub, right="", eyebrow="MEMORY EXPLORER · 记忆库"):
    s = [text(32, 88, eyebrow, 9, "#A2967F", 600, ls=2)]
    s.append(text(32, 120, title, 26, INK, 700, family="Songti SC, STSong, serif"))
    s.append(text(32, 142, sub, 10.5, MUT))
    if right:
        s.append(text(1568, 142, right, 10, FAINT, anchor="end"))
    return "".join(s)


def panel(x, y, w, h, fill=PANEL, r=10):
    return rect(x, y, w, h, fill, r, LINE, 1)


def state_pill(x, y, state, size=9.5):
    col, bg, tx = STATE.get(state, STATE["UNRESOLVED"])
    w = 58 if state != "UNRESOLVED" else 72
    return (rect(x, y, w, 18, bg, 9, col, 0.9) +
            text(x + w / 2, y + 12.5, STATE_ZH.get(state, state), size, tx, 600, anchor="middle")), w


def kind_chip(x, y, kind):
    col = KIND.get(kind, "#6B7280")
    return (rect(x, y, 34, 16, col + "14", 4, col + "55", 0.8) +
            text(x + 17, y + 11, KIND_ZH.get(kind, kind), 8.5, col, 500, anchor="middle"))


def dot(x, y, col, r=3):
    return circle(x, y, r, col)


def kv_table(x, y, w, rows, row_h=26, label_w=96):
    s = []
    for i, (k, v) in enumerate(rows):
        yy = y + i * row_h
        if i:
            s.append(line(x, yy - row_h / 2, x + w, yy - row_h / 2, LINE2, 1))
        s.append(text(x, yy + 4, k, 9, FAINT))
        s.append(text(x + label_w, yy + 4, v, 10.5, "#33404A", 500))
    return "".join(s)


def axis_time(x0, x1, d0, d1, y, ticks, size=8.5):
    """d0/d1 as date ordinals; ticks list of (ordinal,label)."""
    def px(o):
        return x0 + (o - d0) / (d1 - d0) * (x1 - x0)
    s = [line(x0, y, x1, y, LINE, 1)]
    for o, lab in ticks:
        xx = px(o)
        s.append(line(xx, y, xx, y + 5, "#CFC8B8", 1))
        s.append(text(xx, y + 16, lab, 8, FAINT, anchor="middle"))
    return "".join(s), px


def write(path, body, title, bg=BG):
    write_page(path, body, title, bg=bg, extra_css="text{white-space:pre;}")
