# -*- coding: utf-8 -*-
"""A · 立体分层总览：轴向堆叠的六层“实验地层”。"""
import os
from _common import W, H, MONO, SANS, text, rect, line, path, circle, marker_defs, write_page

BG = "#080D17"
INK = "#EDF3FB"
INK2 = "#93A6C0"
INK3 = "#64758F"
DX, DY = 24, -16

MODS = [
    ("W", "写入", "#F2A93B", "W1–W5"),
    ("S", "存储", "#2FB8A6", "S1–S4"),
    ("R", "检索", "#4D8DF7", "R1–R4"),
    ("M", "合并", "#A07BF5", "M1–M6"),
    ("U", "使用", "#F0657E", "U1–U4"),
    ("K", "维护", "#A3C46B", "K1–K3"),
]

PHASES = [
    # code, name, weeks, title, l1, l2, output, accent, y, h
    ("E5", "确认", "2 周", "留出集 · 多 judge · 复现包",
     "留出集 · 3 seeds · 第二 Judge（不同家族）· 人工抽检 100–200",
     "预注册假设 · Holm 校正 · 效应量 / CI · re-run 差异 >0.01 写进 limitations",
     "最终结论 + 复现包", "#6FDCA0", 92, 92),
    ("E4", "环境", "3–4 周", "条件最优是否改变",
     "API 档位 T1 / T2 / T3 × 数据规模 × 4 候选 = 36 格",
     "c*(e)=argmax metric s.t. token / P95 / USD 预算 · regret · 热力图",
     "条件策略表 + regret", "#6FA8FF", 208, 92),
    ("E3", "组合", "2–3 周", "候选组合是否超加",
     "每模块取 2–3 个 Pareto 候选 → 先模块对 2×2 → 再 2^(k−p)",
     "超加 / 次加 = y11−y00 vs (y10−y00)+(y01−y00) · 序贯 halving",
     "组合矩阵 + Pareto", "#B197FC", 324, 92),
    ("E2", "耦合", "3–4 周", "谁带动谁、谁卡住谁",
     "转化率 P(R|W) · P(R|ceiling) · P(A|R) · Oracle 六件套",
     "LLM 阶梯 / 模块敏感性 / 方差分解 / 中介分析 · 模块对 2×2",
     "瓶颈图 + 归因表", "#56CFE1", 440, 92),
    ("E1", "模块内", "5–6 周", "六模块各自跑到局部最优",
     "", "", "每模块 2–3 候选", "#E9C46A", 556, 200),
    ("E0", "测量", "1–2 周", "先锁定尺子，再跑分",
     "LoCoMo + LongMemEval 主基准 · InfiniteBench / MemoryAgentBench 辅助",
     "B0 / R0 / 全文基线 · Oracle 上界 · 跑前先算功效与方差",
     "评测协议 + 基线报告", "#7C8DA6", 770, 84),
]


def slab(x, y, w, h, accent):
    """Axonometric panel: top face + right face + front face."""
    g = []
    g.append(f'<polygon points="{x},{y} {x+w},{y} {x+w+DX},{y+DY} {x+DX},{y+DY}" fill="#1B2740"/>')
    g.append(f'<polygon points="{x+w},{y} {x+w+DX},{y+DY} {x+w+DX},{y+DY+h} {x+w},{y+h}" fill="#0A1220"/>')
    g.append(rect(x, y, w, h, "url(#slab)", 10, "#243350", 1))
    g.append(rect(x, y + 8, 4, h - 16, accent, 2, opacity=0.95))
    g.append(rect(x + 12, y + h - 1, w - 24, 1, "#000", opacity=0.5))
    return "".join(g)


def build():
    s = []
    s.append(f'<defs>'
             f'<linearGradient id="slab" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="#141E30"/>'
             f'<stop offset="1" stop-color="#0E1626"/></linearGradient>'
             f'<radialGradient id="bg" cx="18%" cy="8%" r="80%">'
             f'<stop offset="0" stop-color="#16233A"/><stop offset="1" stop-color="{BG}"/></radialGradient>'
             f'<linearGradient id="titleG" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#9FC0FF"/></linearGradient>'
             f'{marker_defs(["#3A4C68", "#E9C46A", "#6FDCA0"])}'
             f'</defs>')
    s.append(rect(0, 0, W, H, "url(#bg)"))

    # faint grid
    g = []
    for x in range(0, W, 64):
        g.append(line(x, 0, x, H, "#8FB4FF", 0.5, 0.028))
    for y in range(0, H, 64):
        g.append(line(0, y, W, y, "#8FB4FF", 0.5, 0.028))
    s.append("".join(g))

    # ---------------- left column ----------------
    s.append(text(64, 98, "04  ·  EXPERIMENTS", 12, "#6D7E99", 600, ls=3))
    s.append(text(64, 152, "模块化实验", 46, "url(#titleG)", 700))
    s.append(text(64, 208, "路线图", 46, "#F2F6FC", 700))
    s.append(text(64, 244, "六个模块 × 四个步骤 × 六个阶段", 14, INK2))
    s.append(line(64, 270, 300, 270, "#233149", 1))

    s.append(text(64, 302, "六模块 · 实验的组织单位", 11, "#5F7189", 500, ls=1.5))
    for i, (code, name, col, exps) in enumerate(MODS):
        y = 334 + i * 40
        s.append(rect(64, y - 9, 12, 12, col, 3))
        s.append(text(84, y + 1, code, 13, col, 700, family=MONO))
        s.append(text(106, y + 1, name, 14, "#D9E3F2", 500))
        s.append(text(300, y + 1, exps, 10, "#5F7189", 400, anchor="end"))

    # three questions card
    cy = 588
    s.append(rect(64, cy, 236, 150, "#0D1626", 12, "#1E2B40", 1))
    s.append(text(84, cy + 28, "要回答的三件事", 12, "#8FA3BE", 600, ls=0.5))
    qs = [("①", "模块内怎么配最好"), ("②", "模块间是否理所当然"), ("③", "系统好，还是 LLM 强")]
    for i, (n, q) in enumerate(qs):
        yy = cy + 60 + i * 30
        s.append(text(84, yy, n, 12, "#E9C46A", 700))
        s.append(text(102, yy, q, 12.5, "#C9D6E8"))

    s.append(text(64, 912, "先模块内 → 再模块间 → 再组合 → 再环境 → 最后确认",
                  12.5, "#7E90AA"))
    s.append(text(64, 936, "不要用一张全局 2^k 表代替模块设计", 11, "#53647D"))

    # time rail between left col and panels
    s.append(line(330, 854, 330, 100, "#2A3B57", 1, 0.9, dash="3 5"))
    s.append(f'<polygon points="330,88 325,100 335,100" fill="#3A4C68"/>')


    # ---------------- panels ----------------
    PX, PW = 352, 1100
    for code, name, weeks, title, l1, l2, out, accent, y, h in PHASES:
        s.append(slab(PX, y, PW, h, accent))
        # phase block
        s.append(text(PX + 22, y + 38, code, 27, accent, 700, family=MONO))
        s.append(text(PX + 24, y + 60, name, 12, "#A9B9D0", 500))
        s.append(text(PX + 24, y + 78, weeks, 10, "#63748F", 400))
        s.append(line(PX + 108, y + 18, PX + 108, y + h - 18, "#243350", 1))

        if code == "E1":
            s.append(text(PX + 130, y + 36, title, 18, INK, 600))
            s.append(text(PX + 130, y + 58, "W → S → R → M → U → K；每个模块四步走到局部最优", 12, INK2))
            cw, gap = 146, 10
            cx0 = PX + 130
            for i, (mc, mn, col, exps) in enumerate(MODS):
                cx = cx0 + i * (cw + gap)
                cyy = y + 72
                s.append(rect(cx, cyy, cw, 92, "#101A2B", 8, "#22304A", 1))
                s.append(rect(cx, cyy, cw, 3, col, 1.5))
                s.append(circle(cx + 15, cyy + 24, 5, col))
                s.append(text(cx + 27, cyy + 28, f"{mc} {mn}", 14, "#E6EEF9", 600))
                s.append(text(cx + cw - 10, cyy + 27, exps, 8.5, "#5F7189", 400, anchor="end"))
                for j in range(4):
                    bw = (cw - 24 - 9) / 4
                    bx = cx + 12 + j * (bw + 3)
                    by = cyy + 44
                    op = [0.22, 0.34, 0.46, 0.62][j]
                    s.append(rect(bx, by, bw, 16, col, 3, opacity=op))
                    s.append(text(bx + bw / 2, by + 11.5, "①②③④"[j], 8, "#0B1220", 700,
                                  anchor="middle", opacity=0.9))
                s.append(text(cx + 12, cyy + 80, "选型→参数→LLM→组合", 8.5, "#6B7C95"))
            s.append(text(PX + 130, y + 184,
                          "① 插拔/架构选型   ② 参数   ③ LLM 规模   ④ 模块内组合", 10.5, "#8FA3BE"))
            s.append(rect(PX + PW - 214, y + 174, 190, 22, "#1A2438", 11, "#33456A", 1))
            s.append(text(PX + PW - 119, y + 189, "→ 每模块 2–3 个 Pareto 候选", 9.5, "#E9C46A",
                          500, anchor="middle"))
        else:
            s.append(text(PX + 130, y + 32, title, 18, INK, 600))
            if l1:
                s.append(text(PX + 130, y + 55, l1, 12, "#AFC0D6"))
            if l2:
                s.append(text(PX + 130, y + 73, l2, 12, "#AFC0D6"))
            # output chip
            ox, ow = PX + PW - 286, 262
            s.append(rect(ox, y + 14, ow, h - 28, "#0B1422", 8, "#233149", 1))
            s.append(text(ox + 14, y + 31, "产出", 9, "#5F7189", 600, ls=2))
            s.append(text(ox + 14, y + 49, out, 11.5, "#DCE7F6", 600))
            if h > 80:
                s.append(text(ox + 14, y + 68, "写进 reports / Web 详情页", 9, "#5F7189"))

    # right cumulative axis
    ax = 1496
    s.append(line(ax, 100, ax, 846, "#233149", 1))
    centers = [(92 + 46, "21"), (208 + 46, "19"), (324 + 46, "15"),
               (440 + 46, "12"), (556 + 100, "8"), (770 + 42, "2")]
    for yy, lab in centers:
        s.append(line(ax - 4, yy, ax + 4, yy, "#3A4C68", 1))
        s.append(text(ax + 10, yy + 3.5, "≈" + lab, 9.5, "#5F7189"))
    s.append('<text transform="translate(1536,473) rotate(90)" font-family="PingFang SC" '
             'font-size="9" fill="#44546C" letter-spacing="2" text-anchor="middle">累计周</text>')

    # small connectors between panels
    for yy in (184, 300, 416, 532, 756):
        s.append(f'<polygon points="{PX-14},{yy+2} {PX-6},{yy+2} {PX-10},{yy+11}" fill="#3A4C68"/>')

    # top-right micro legend
    s.append(text(1480, 70, "ONE MAP · SIX PHASES", 9, "#44546C", 600, anchor="end", ls=2))
    s.append(text(1480, 84, "模块内插拔 → 模块间插拔 → 环境插拔", 10, "#5F7189", anchor="end"))

    write_page(os.path.join(os.path.dirname(__file__), "01-isometric-stack.html"),
               "".join(s), "A · 立体分层总览")


if __name__ == "__main__":
    build()
