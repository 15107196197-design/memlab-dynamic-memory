# -*- coding: utf-8 -*-
"""D · 模块契约环：六模块环流 + 接口编号 + 只测的模块对。"""
import os
import math
from _common import text, rect, line, path, circle, marker_defs, write_page, MONO

BG = "#07161C"
INK = "#E8F1F4"
INK2 = "#9FB6BF"
MUT = "#6B8590"

MODS = [
    ("W", "写入", "#F2A93B", "E1-W1…W5", "抽取 P/R"),
    ("S", "存储", "#35C4B0", "S1–S4", "检索上限"),
    ("R", "检索", "#5B93FF", "R1–R4", "Recall@K"),
    ("M", "合并", "#A98BFF", "M1–M6", "nDCG · 冗余"),
    ("U", "使用", "#F0657E", "U1–U4", "F1 · 状态"),
    ("K", "维护", "#A8C46B", "K1–K3", "陈旧 · 矛盾"),
]

CX, CY, R, A = 700, 455, 285, 86

CONTRACTS = [
    ("①", "W → S", "每条事实带 t_event / t_ingest、evidence、schema_version"),
    ("②", "S → R", "返回 memory_id / channel / score / source；图检索带路径"),
    ("③", "R → M", "每路独立排序、候选预算固定，否则融合不可比"),
    ("④", "M → U", "上下文带 memory_id / 证据 / 时间，超预算显式截断"),
    ("⑤", "U → 评测", "答案带引用 / 拒答 / 冲突披露，否则无法归因"),
    ("⑥", "K → W", "更新 / 失效 / 一致性扫描回写，长期状态可追溯"),
]

PAIRS = [
    ("W × R", "结构化写入是否让图检索更有效", "2×2"),
    ("S × M", "图粒度是否被重排补偿", "2×2"),
    ("R × M", "规划是否让融合更有用", "2×2"),
    ("M × U", "压缩是否伤答案", "2×2"),
    ("W × K", "更新策略是否影响长期状态", "2×2"),
    ("R × U", "检索好是否使用好", "2×2"),
]


def hexpts(cx, cy, a):
    return " ".join(f"{cx + a*math.cos(math.radians(60*k)):.1f},{cy + a*math.sin(math.radians(60*k)):.1f}"
                    for k in range(6))


def build():
    s = []
    s.append(f'<defs>'
             f'<radialGradient id="bg" cx="45%" cy="42%" r="72%">'
             f'<stop offset="0" stop-color="#0E2730"/><stop offset="1" stop-color="{BG}"/></radialGradient>'
             f'{marker_defs(["#3E6C7C", "#6B8590"])}'
             f'<filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
             f'<feGaussianBlur stdDeviation="6" result="b"/><feMerge>'
             f'<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
             f'</defs>')
    s.append(rect(0, 0, 1600, 1000, "url(#bg)"))

    # blueprint grid
    for x in range(0, 1600, 50):
        s.append(line(x, 0, x, 1000, "#5FA8B8", 0.6, 0.06))
    for y in range(0, 1000, 50):
        s.append(line(0, y, 1600, y, "#5FA8B8", 0.6, 0.06))

    # header
    s.append(text(64, 76, "04 · EXPERIMENTS  /  CONTRACT RING", 10, "#6B8590", 600, ls=2.4))
    s.append(text(64, 122, "模块契约环", 36, INK, 700))
    s.append(text(64, 150, "六个模块 · 六个接口 · 六个只测的配对", 11.5, INK2))

    # quote (left)
    s.append(text(64, 214, "“", 40, "#2E5563", 700))
    s.append(text(84, 236, "插拔本身是好思路，", 13, "#C7D8DE", 500))
    s.append(text(84, 258, "问题不在插拔，而在散落。", 13, "#C7D8DE", 500))
    s.append(text(84, 280, "— 4.1 设计原则", 9, MUT))

    # left card: interface vs downstream
    s.append(rect(64, 430, 268, 176, "#0C2028", 12, "#1E3E49", 1))
    s.append(text(84, 458, "每个模块的“好”", 10.5, "#8FA9B2", 600, ls=0.5))
    s.append(text(84, 484, "接口指标", 10.5, "#F2A93B", 600))
    s.append(text(152, 484, "输出是否满足下游契约", 8.6, "#B9CBD3"))
    s.append(text(84, 510, "下游指标", 10.5, "#35C4B0", 600))
    s.append(text(152, 510, "下游用了是否真的变好", 8.6, "#B9CBD3"))
    s.append(line(84, 526, 312, 526, "#1E3E49", 1))
    s.append(text(84, 550, "只看接口 → 字段很多但下游不用", 8.6, "#9FB6BF"))
    s.append(text(84, 570, "只看下游 → 不知道是哪一段贡献", 8.6, "#9FB6BF"))
    s.append(text(84, 594, "两个都记录，才能定位瓶颈", 8.8, "#CFE3EC", 500))

    # orbit ring
    s.append(circle(CX, CY, R, "none", "#2A4C58", 1, 0.45, extra='stroke-dasharray="2 8"'))

    # flow arrows between hexes
    for i in range(6):
        ang = -90 + i * 60
        ang2 = ang + 60
        x1 = CX + math.cos(math.radians(ang)) * R
        y1 = CY + math.sin(math.radians(ang)) * R
        x2 = CX + math.cos(math.radians(ang2)) * R
        y2 = CY + math.sin(math.radians(ang2)) * R
        ux, uy = (x2 - x1) / R, (y2 - y1) / R
        sx, sy = x1 + ux * (A + 4), y1 + uy * (A + 4)
        ex, ey = x2 - ux * (A + 8), y2 - uy * (A + 8)
        if i == 4:
            s.append(line(sx, sy, ex, ey, "#3E5C66", 1.1, 0.55, dash="2 6"))
            continue
        col = "#3E6C7C"
        dash = "4 5" if i == 5 else None
        s.append(line(sx, sy, ex, ey, col, 1.6, 0.9, dash=dash,
                      extra=' marker-end="url(#ar0)"'))

    # hexes
    for i, (code, name, col, exps, metric) in enumerate(MODS):
        ang = -90 + i * 60
        hx = CX + math.cos(math.radians(ang)) * R
        hy = CY + math.sin(math.radians(ang)) * R
        s.append(f'<polygon points="{hexpts(hx, hy, A)}" fill="{col}" fill-opacity="0.09" '
                 f'stroke="{col}" stroke-opacity="0.6" stroke-width="1.4"/>')
        s.append(f'<polygon points="{hexpts(hx, hy, A-7)}" fill="none" stroke="{col}" '
                 f'stroke-opacity="0.14" stroke-width="1"/>')
        s.append(text(hx, hy - 32, code, 25, col, 700, anchor="middle", family=MONO))
        s.append(text(hx, hy - 8, name, 13, "#E6EFF3", 600, anchor="middle", ls=1))
        s.append(text(hx, hy + 14, exps, 8, MUT, 400, anchor="middle"))
        s.append(text(hx, hy + 32, metric, 8.5, "#C3D5DC", 500, anchor="middle"))

    # maintenance link label (U — K)
    s.append(rect(410, 440, 86, 24, "#0A1B23", 12, "#2A4C58", 1))
    s.append(text(453, 456, "维护 · 全链路", 8.2, "#8FA9B2", 500, anchor="middle"))

    # U -> evaluation annotation
    s.append(text(453, 694, "⑤ 输出给评测", 8.6, "#F0657E", 600, anchor="middle"))
    s.append(text(453, 710, "引用 · 拒答 · 冲突披露", 8, "#9FB6BF", 400, anchor="middle"))

    # contract number badges
    for i in range(6):
        if i == 4:
            continue
        ang = -90 + i * 60 + 30
        bx = CX + math.cos(math.radians(ang)) * R * math.cos(math.radians(30))
        by = CY + math.sin(math.radians(ang)) * R * math.cos(math.radians(30))
        s.append(circle(bx, by, 13, "#0A1B23", "#3E6C7C", 1.4, extra=' filter="url(#glow)"'))
        s.append(text(bx, by + 4, "①②③④⑤⑥"[i], 11, "#CFE3EC", 500, anchor="middle"))

    # center
    s.append(circle(CX, CY, 143, "#0B2029", "#2A4C58", 1.2, 0.95))
    s.append(circle(CX, CY, 132, "none", "#22444F", 1, 0.7))
    s.append(text(CX, CY - 56, "参考流水线", 16, INK, 700, anchor="middle", ls=1))
    s.append(text(CX, CY - 36, "插一个模块，固定其余", 9.5, INK2, 400, anchor="middle"))
    s.append(line(CX - 62, CY - 20, CX + 62, CY - 20, "#2A4C58", 1))
    for i, t in enumerate(("① 单模块插拔", "② 双模块 2×2", "③ 三模块部分因子")):
        s.append(text(CX - 54, CY + 4 + i * 22, t, 10.5, "#D6E4EA", 500))
    s.append(text(CX, CY + 78, "看边际贡献与超加 / 次加", 8.5, MUT, 400, anchor="middle"))

    # right: four levels card
    s.append(rect(1075, 150, 480, 140, "#0C2028", 12, "#1E3E49", 1))
    s.append(text(1095, 176, "插拔的四个层级", 11, "#8FA9B2", 600, ls=0.5))
    levels = [("①", "模块内组件", "on / off"), ("②", "模块内实现", "A/B 选型"),
              ("③", "模块间候选", "2–3 插头"), ("④", "环境", "LLM · 规模")]
    for i, (n, t1, t2) in enumerate(levels):
        yy = 202 + i * 22
        s.append(text(1095, yy, n, 9, "#5FA8B8", 700))
        s.append(text(1113, yy, t1, 10, "#D6E4EA", 500))
        s.append(text(1258, yy, t2, 8.5, MUT, 400, anchor="end"))

    # right: pairs panel
    s.append(rect(1075, 310, 480, 452, "#0C2028", 12, "#1E3E49", 1))
    s.append(text(1095, 338, "E2 · 只测强相关的模块对", 11, "#8FA9B2", 600, ls=0.5))
    s.append(text(1095, 356, "不做全因子；显著后再扩到 3–4 模块", 8.5, MUT))
    s.append(line(1095, 370, 1535, 370, "#1E3E49", 1))
    for i, (pair, desc, tag) in enumerate(PAIRS):
        yy = 398 + i * 60
        s.append(text(1095, yy, pair, 12, "#E6EFF3", 600, family=MONO))
        s.append(text(1095, yy + 18, desc, 8.8, "#9FB6BF"))
        s.append(rect(1489, yy - 13, 46, 19, "#12303A", 9, "#2A4C58", 1))
        s.append(text(1512, yy + 1, tag, 7.5, "#8FD0DD", 600, anchor="middle"))
        if i < 5:
            s.append(line(1095, yy + 36, 1535, yy + 36, "#17333D", 1))

    # bottom contracts legend
    s.append(text(64, 858, "接口契约 · 数字对应环上的位置", 9, "#6B8590", 600, ls=1.5))
    s.append(line(64, 868, 1035, 868, "#1E3E49", 1))
    for i, (n, pair, desc) in enumerate(CONTRACTS):
        col = i // 3
        row = i % 3
        x = 64 + col * 500
        y = 892 + row * 24
        s.append(text(x, y, n, 9.5, "#5FA8B8", 700))
        s.append(text(x + 16, y, pair, 9.5, "#CFE3EC", 600, family=MONO))
        s.append(text(x + 76, y, desc, 8.6, "#8FA9B2"))

    write_page(os.path.join(os.path.dirname(__file__), "04-hex-contract-ring.html"),
               "".join(s), "D · 模块契约环", bg=BG)


if __name__ == "__main__":
    build()
