# -*- coding: utf-8 -*-
"""B · 放射思维导图：原则 / 模块 / 阶段 / 评测 / 归因 五枝。"""
import os
from _common import text, rect, line, path, circle, write_page, MONO

PAPER = "#F6F0E4"
INK = "#23303A"
INK2 = "#4A5762"
MUT = "#857A6A"
C_LAW = "#B4553A"
C_MOD = "#2A7F78"
C_PHASE = "#3D5FA8"
C_EVAL = "#8A6B2F"
C_ATTR = "#6B4E8E"

CX, CY = 810, 500


def pill(x, y, w, h, fill="#FFFDF7", stroke="#D8CCB6", r=12, sw=1, shadow=True, extra=""):
    f = ' filter="url(#soft)"' if shadow else ""
    return rect(x, y, w, h, fill, r, stroke, sw, extra=f + extra)


def label(x, y, main, sub=None, size=12, col=INK, sub_col=MUT, anchor="start"):
    out = [text(x, y, main, size, col, 600, anchor=anchor)]
    if sub:
        out.append(text(x, y + 16, sub, 9, sub_col, 400, anchor=anchor))
    return "".join(out)


def curve(x1, y1, x2, y2, col, sw=2.2, op=0.75, dash=None, vertical=False):
    if vertical:
        my = (y1 + y2) / 2
        d = f"M{x1},{y1} C {x1},{my} {x2},{my} {x2},{y2}"
    else:
        mx = (x1 + x2) / 2
        d = f"M{x1},{y1} C {mx},{y1} {mx},{y2} {x2},{y2}"
    return path(d, stroke=col, sw=sw, opacity=op, dash=dash)


def build():
    s = []
    s.append('<defs>'
             '<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">'
             '<circle cx="1.2" cy="1.2" r="1" fill="#C9BDA7" opacity="0.45"/></pattern>'
             '<filter id="soft" x="-30%" y="-30%" width="160%" height="180%">'
             '<feDropShadow dx="0" dy="2.5" stdDeviation="3" flood-color="#5B4A33" flood-opacity="0.14"/>'
             '</filter>'
             '<radialGradient id="paper" cx="50%" cy="42%" r="70%">'
             '<stop offset="0" stop-color="#FBF7EE"/><stop offset="1" stop-color="#F0E8D8"/>'
             '</radialGradient>'
             '</defs>')
    s.append(rect(0, 0, 1600, 1000, "url(#paper)"))
    s.append(rect(0, 0, 1600, 1000, "url(#dots)"))

    # faint rings
    s.append(circle(CX, CY, 428, "none", "#C9B99E", 1, 0.5, extra='stroke-dasharray="2 7"'))
    s.append(circle(CX, CY, 300, "none", "#CDBFA6", 0.8, 0.4))

    # header
    s.append(text(64, 78, "04 · EXPERIMENTS   /   MIND MAP", 10, "#9A8D7B", 600, ls=2.4))
    s.append(text(64, 124, "实验设计逻辑图", 36, INK, 700))
    s.append(text(64, 158, "原则 → 模块 → 阶段 → 评测 → 归因", 12.5, "#7C7264"))
    s.append(line(64, 176, 296, 176, "#D8CCB6", 1))

    # ---------------- branch stubs (behind pills) ----------------
    # left modules
    s.append(curve(660, CY, 634, CY, C_MOD, 3.6))
    for y in (330, 395, 460, 525, 590, 655):
        s.append(curve(445, CY, 421, y, C_MOD, 1.5, 0.5))
    # right phases
    s.append(curve(960, CY, 990, CY, C_PHASE, 3.6))
    for y in (300, 364, 428, 492, 556, 620):
        s.append(curve(1180, CY, 1268, y, C_PHASE, 1.5, 0.5))
    # top laws
    s.append(curve(810, 452, 810, 326, C_LAW, 3.4, vertical=True))
    s.append(line(450, 238, 1170, 238, C_LAW, 1.4, 0.4))
    s.append(line(810, 274, 810, 238, C_LAW, 1.4, 0.4))
    for x in (450, 690, 930, 1170):
        s.append(line(x, 238, x, 190, C_LAW, 1.4, 0.4))
    # bottom eval
    s.append(curve(748, 548, 600, 694, C_EVAL, 2.8, 0.7))
    s.append(line(320, 788, 860, 788, C_EVAL, 1.4, 0.4))
    s.append(line(600, 748, 600, 788, C_EVAL, 1.4, 0.4))
    for x in (320, 500, 680, 860):
        s.append(line(x, 788, x, 822, C_EVAL, 1.4, 0.4))
    # bottom attr
    s.append(curve(880, 548, 1030, 694, C_ATTR, 2.8, 0.7))
    s.append(line(1030, 788, 1410, 788, C_ATTR, 1.4, 0.4))
    s.append(line(1030, 748, 1030, 788, C_ATTR, 1.4, 0.4))
    for x in (1050, 1230, 1410):
        s.append(line(x, 788, x, 822, C_ATTR, 1.4, 0.4))

    # ---------------- center ----------------
    s.append(rect(660, 452, 300, 96, "#22303A", 20, extra=' filter="url(#soft)"'))
    s.append(text(810, 492, "模块化实验设计", 25, "#F7F1E5", 700, anchor="middle", ls=1))
    s.append(text(810, 518, "6 个模块 · 4 个步骤 · 6 个阶段", 10.5, "#A9B8B2", anchor="middle", ls=0.5))
    s.append(circle(660, 500, 4, "#22303A"))
    s.append(circle(960, 500, 4, "#22303A"))

    # ---------------- main branch pills ----------------
    s.append(pill(445, 473, 190, 54, "#EAF2EF", C_MOD, 14, 1.2))
    s.append(text(462, 496, "六模块", 15, C_MOD, 700))
    s.append(text(462, 514, "W S R M U K · 组织单位", 8.5, "#5E7A75"))
    s.append(text(620, 500, "6", 22, C_MOD, 700, anchor="end", opacity=0.28))

    s.append(pill(990, 473, 190, 54, "#EAEEF7", C_PHASE, 14, 1.2))
    s.append(text(1007, 496, "阶段链", 15, C_PHASE, 700))
    s.append(text(1007, 514, "E0 → E5 · 16–21 周", 8.5, "#6C7A99"))
    s.append(text(1165, 500, "→", 15, C_PHASE, 700, anchor="end", opacity=0.5))

    s.append(pill(728, 274, 164, 52, "#F7ECE7", C_LAW, 14, 1.2))
    s.append(text(746, 297, "四原则", 15, C_LAW, 700))
    s.append(text(746, 314, "先内后外 · 双指标", 8.5, "#8C6B60"))

    s.append(pill(518, 694, 164, 54, "#F5EFDF", C_EVAL, 14, 1.2))
    s.append(text(536, 717, "四层评测", 15, C_EVAL, 700))
    s.append(text(536, 735, "L1 → L4 · A/B/C 组合", 8.5, "#8A7A5A"))

    s.append(pill(948, 694, 164, 54, "#F0EBF6", C_ATTR, 14, 1.2))
    s.append(text(966, 717, "归因与判定", 15, C_ATTR, 700))
    s.append(text(966, 735, "转化率 · Oracle · LLM", 8.5, "#7C6C8C"))

    # ---------------- left: modules ----------------
    mods = [("W", "写入", "#D98E27", "W1–W5"), ("S", "存储", "#2A9D8F", "S1–S4"),
            ("R", "检索", "#3D7EE0", "R1–R4"), ("M", "合并", "#8266D8", "M1–M6"),
            ("U", "使用", "#D9536B", "U1–U4"), ("K", "维护", "#7C9A4E", "K1–K3")]
    for i, (c, n, col, ex) in enumerate(mods):
        y = 330 + i * 65
        s.append(pill(240, y - 25, 181, 50))
        s.append(rect(240, y - 25, 4, 50, col, 2))
        s.append(circle(262, y, 4.5, col))
        s.append(text(274, y + 1, f"{c} {n}", 12.5, INK, 700))
        s.append(text(410, y + 1, ex, 8.5, MUT, anchor="end"))
        s.append(text(274, y + 15, ["写入质量", "表示上限", "召回 / 规划", "融合 / 重排",
                                    "状态 / 答案", "更新 / 遗忘"][i], 8, "#8C8170"))

    # ---------------- right: phases ----------------
    phases = [("E0", "测量", "1–2 周", "协议 · 基线", "#6F7F8C"),
              ("E1", "模块内", "5–6 周", "每模块 2–3 候选", "#C39A2E"),
              ("E2", "耦合", "3–4 周", "瓶颈 · 归因", "#3E9AA8"),
              ("E3", "组合", "2–3 周", "超加 / 次加", "#7C67C4"),
              ("E4", "环境", "3–4 周", "条件最优", "#3F72B8"),
              ("E5", "确认", "2 周", "稳健 · 复现", "#4C9468")]
    for i, (c, n, w, d, col) in enumerate(phases):
        y = 300 + i * 64
        s.append(pill(1270, y - 25, 192, 50))
        s.append(rect(1270, y - 25, 4, 50, col, 2))
        s.append(text(1284, y - 2, c, 11, col, 700, family=MONO))
        s.append(text(1312, y - 2, n, 12, INK, 600))
        s.append(text(1452, y - 2, w, 8.5, MUT, anchor="end"))
        s.append(text(1284, y + 15, d, 8, "#8C8170"))

    # ---------------- top: principles ----------------
    laws = [("①", "插拔分两层", "模块内 → 模块间 → 环境"),
            ("②", "先内后外", "先局部最优，再组合"),
            ("③", "接口 + 下游", "两个指标一起看"),
            ("④", "LLM 双角色", "环境变量 × 混淆变量")]
    for i, (n, t1, t2) in enumerate(laws):
        x = 362 + i * 240
        s.append(pill(x, 132, 180, 58, "#FFFCF6", "#DCCDB8", 12))
        s.append(text(x + 14, 154, n, 11, C_LAW, 700))
        s.append(text(x + 30, 154, t1, 12, INK, 700))
        s.append(text(x + 14, 174, t2, 8.5, "#8A7C6B"))

    # ---------------- bottom: evaluation ----------------
    evals = [("L1", "模块内在", "P/R · Recall · 状态"),
             ("L2", "接口契约", "覆盖 · 预算 · 引用"),
             ("L3", "端到端", "F1 · Judge · 忠实"),
             ("L4", "成本鲁棒", "token · P95 · 方差")]
    for i, (c, n, d) in enumerate(evals):
        x = 238 + i * 180
        s.append(pill(x, 822, 166, 56, "#FFFCF6", "#DCCDB8", 12))
        s.append(text(x + 12, 845, c, 10, C_EVAL, 700, family=MONO))
        s.append(text(x + 34, 845, n, 11, INK, 600))
        s.append(text(x + 12, 864, d, 8, "#8A7C6B"))

    # ---------------- bottom: attribution ----------------
    attrs = [("转化率", "P(A|R) · P(R|W)"), ("Oracle 六件套", "write→answer 上界"), ("LLM 归因", "阶梯 · 方差 · 中介")]
    for i, (t1, t2) in enumerate(attrs):
        x = 966 + i * 180
        s.append(pill(x, 822, 166, 56, "#FFFCF6", "#DCCDB8", 12))
        s.append(text(x + 12, 845, t1, 11, INK, 600))
        s.append(text(x + 12, 864, t2, 8, "#8A7C6B"))

    # quote
    s.append(line(360, 922, 1240, 922, "#D8CCB6", 1))
    s.append(text(800, 952, "先把每个模块调到它自己的最好，再问模块之间是否互相成就。",
                  13, "#6B6154", 400, anchor="middle", ls=0.5))
    s.append(text(800, 974, "— 04-experiments · 4.18", 9, "#A2947F", anchor="middle"))

    write_page(os.path.join(os.path.dirname(__file__), "02-radial-mindmap.html"),
               "".join(s), "B · 实验逻辑思维导图", bg=PAPER)


if __name__ == "__main__":
    build()
