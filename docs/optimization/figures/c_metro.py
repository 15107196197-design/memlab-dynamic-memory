# -*- coding: utf-8 -*-
"""C · 实验线路图：时间轴 × 六条模块线 × 阶段换乘。"""
import os
from _common import text, rect, line, path, circle, write_page, MONO

PAPER = "#FAF7F0"
INK = "#22303C"
MUT = "#7C8794"

LANES = [
    ("W", "写入", "#D08A1C", 260, [("W1", "架构插拔", 260), ("W2", "冲突更新", 380),
                                   ("W3", "写入审计", 500), ("W4", "参数扫描", 620),
                                   ("W5", "切分粒度", 740)], "①"),
    ("S", "存储", "#1F8F84", 348, [("S1", "存储单元", 300), ("S2", "图表示", 440),
                                   ("S3", "分层", 580), ("S4", "增量更新", 720)], "②"),
    ("R", "检索", "#2F6FD0", 436, [("R1", "规划器", 300), ("R2", "通道组合", 440),
                                   ("R3", "图检索", 580), ("R4", "参数", 720)], "③"),
    ("M", "合并", "#6D4FCC", 524, [("M1", "路线×融合", 250), ("M2", "重排×规模", 370),
                                   ("M3", "流水线顺序", 490), ("M4", "后处理参数", 610),
                                   ("M5", "动态权重", 730), ("M6", "候选深度", 850)], "④"),
    ("U", "使用", "#C9415C", 612, [("U1", "上下文格式", 300), ("U2", "状态解析", 440),
                                   ("U3", "回答 LLM", 580), ("U4", "验证/拒答", 720)], "⑤"),
    ("K", "维护", "#6D8A3C", 700, [("K1", "更新/遗忘", 300), ("K2", "合并", 500),
                                   ("K3", "一致性扫描", 700)], "⑥"),
]

BANDS = [
    ("E2", "耦合", "3–4 周", 960, 1075, "#E8EEF6", "#2F6FD0", "转化 · Oracle · 归因", 1017),
    ("E3", "组合", "2–3 周", 1075, 1190, "#F0ECF9", "#6D4FCC", "2×2 · 部分因子", 1132),
    ("E4", "环境", "3–4 周", 1190, 1320, "#E9F2F3", "#1F8F84", "36 格 · 条件最优", 1255),
    ("E5", "确认", "2 周", 1320, 1440, "#EDF4EA", "#6D8A3C", "留出 · κ · 复现", 1380),
]


def build():
    s = []
    s.append('<defs>'
             '<filter id="st" x="-20%" y="-20%" width="140%" height="140%">'
             '<feDropShadow dx="0" dy="1" stdDeviation="1.2" flood-color="#6B5A3E" flood-opacity="0.18"/>'
             '</filter>'
             '<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
             '<path d="M40 0H0V40" fill="none" stroke="#E7DFCF" stroke-width="0.6" opacity="0.5"/>'
             '</pattern>'
             '</defs>')
    s.append(rect(0, 0, 1600, 1000, PAPER))
    s.append(rect(0, 0, 1600, 1000, "url(#grid)"))

    # header
    s.append(text(48, 66, "04 · EXPERIMENTS  /  TRANSIT MAP", 10, "#9A8F7C", 600, ls=2.2))
    s.append(text(48, 108, "实验线路图", 34, INK, 700))
    s.append(text(48, 134, "横向是时间，纵向是模块；竖带是阶段汇合。", 11.5, "#7C7264"))

    # three questions strip
    s.append(text(640, 88, "本图回答的三件事", 9, "#9A8F7C", 700, ls=2))
    s.append(text(640, 110, "① 模块内怎么配 —— 看 E1 六条线是否各自收敛", 10, "#4E5A66"))
    s.append(text(640, 130, "② 谁带动谁、谁卡住谁 —— 看 E2 竖带与转化率", 10, "#4E5A66"))
    s.append(text(640, 150, "③ 系统好还是 LLM 强 —— 看 E4 换模型后的条件最优", 10, "#4E5A66"))

    # reading aid
    s.append(rect(1042, 52, 510, 78, "#FFFDF8", 10, "#E2D8C6", 1, extra=' filter="url(#st)"'))
    s.append(text(1062, 76, "读 法", 9, "#9A8F7C", 700, ls=2))
    s.append(text(1062, 94, "横轴 = 时间 →      纵轴 = 模块（建议推进顺序 ①→⑥）", 9.5, "#4E5A66"))
    s.append(text(1062, 112, "实心站 = E1 实验      空心环 = 候选进入下一阶段", 9.5, "#4E5A66"))

    # phase bands
    for code, name, wk, x1, x2, fill, col, cap, cx in BANDS:
        s.append(rect(x1, 214, x2 - x1, 530, fill, 0, opacity=0.55))
        s.append(line(x1, 214, x1, 744, "#C9D1DA", 1, 0.7, dash="3 4"))
        s.append(text(cx, 236, f"{code} {name}", 12, "#33404C", 700, anchor="middle"))
        s.append(text(cx, 250, wk, 8.5, "#8A94A3", 400, anchor="middle"))
        s.append(text(cx, 756, cap, 8.2, "#7C8794", 400, anchor="middle"))
    s.append(line(1440, 214, 1440, 744, "#C9D1DA", 1, 0.7, dash="3 4"))

    # E1 band tint + header
    s.append(rect(168, 214, 792, 530, "#FBF4E4", 0, opacity=0.42))
    
    s.append(text(560, 192, "E1 模块内优化 · 5–6 周 · 每个模块四步走到局部最优 → 2–3 个候选",
                  11.5, "#6B5A38", 700, anchor="middle"))

    # E0 depot
    s.append(rect(110, 236, 48, 488, "#2A3542", 24, extra=' filter="url(#st)"'))
    s.append('<text transform="translate(141,480) rotate(-90)" font-family="PingFang SC" font-size="10.5" '
             'fill="#E9EEF4" letter-spacing="1.2" text-anchor="middle">B0 / R0 / 全文 / Oracle</text>')
    s.append(text(110, 192, "E0 测量 · 1–2 周", 12, "#33404C", 700))
    s.append(text(110, 208, "基线池 · 先定尺子再跑分", 8.8, "#8A94A3"))

    # lane lines
    for li, (code, name, col, y, stops, num) in enumerate(LANES):
        s.append(line(158, y, 1436, y, col, 6, 0.92))
        s.append(line(158, y, 1436, y, "#FFFFFF", 1.2, 0.35))
        s.append(f'<polygon points="1436,{y-6} 1448,{y} 1436,{y+6}" fill="{col}"/>')
        # label
        s.append(circle(1470, y - 4, 7, col, opacity=0.14))
        s.append(text(1470, y - 0.5, num, 8, col, 700, anchor="middle"))
        s.append(text(1484, y + 1, f"{code} {name}", 12, INK, 700))
        s.append(text(1484, y + 15, ["写入质量", "表示上限", "召回/规划", "融合/重排",
                                     "状态/答案", "更新/遗忘"][li], 8, "#8C8170"))

    # stops + labels
    for code, name, col, y, stops, num in LANES:
        for sid, sname, x in stops:
            s.append(circle(x, y, 6.4, col, "#FAF7F0", 2.2, extra=' filter="url(#st)"'))
            s.append(text(x, y - 22, sid, 8.2, col, 700, anchor="middle"))
            s.append(text(x, y - 11, sname, 8.2, "#5A6572", 400, anchor="middle"))

    # candidate bracket

    # phase nodes on each lane
    for code, name, col, y, stops, num in LANES:
        for bx in (1017, 1132, 1255, 1380):
            s.append(circle(bx, y, 7.2, "#FFFDF8", col, 2.4, extra=' filter="url(#st)"'))


    # legend
    ly = 820
    s.append(text(48, ly - 14, "图 例", 9, "#9A8F7C", 700, ls=2))
    items = [
        ("line", "模块线 · 6 条并行", "#6D4FCC"),
        ("dot", "E1 实验站点", "#D08A1C"),
        ("ring", "候选进入 E2–E5", "#2F6FD0"),
        ("dash", "阶段汇合边界", "#B9A98C"),
    ]
    for i, (kind, lab, col) in enumerate(items):
        x = 48 + i * 250
        if kind == "line":
            s.append(line(x, ly + 6, x + 34, ly + 6, col, 6))
        elif kind == "dot":
            s.append(circle(x + 16, ly + 6, 6.4, col, "#FAF7F0", 2.2))
        elif kind == "ring":
            s.append(circle(x + 16, ly + 6, 7, "#FFFDF8", col, 2.4))
        else:
            s.append(line(x + 16, ly - 2, x + 16, ly + 14, col, 1.2, 0.9, dash="3 4"))
        s.append(text(x + 46, ly + 10, lab, 10, "#4E5A66"))

    # bottom takeaway
    s.append(line(48, 878, 1552, 878, "#E0D6C4", 1))
    s.append(text(48, 910, "读这条线的方式：先看每条线在 E1 是否收敛到 2–3 个候选，再看竖带里候选如何汇合与再分流。",
                  11.5, "#5A5348"))
    s.append(text(48, 940, "E1 产出候选 → E2 解释耦合 → E3 组合候选 → E4 换环境 → E5 换数据确认",
                  12, "#8A7A5C", 500))

    write_page(os.path.join(os.path.dirname(__file__), "03-metro-map.html"),
               "".join(s), "C · 实验线路图", bg=PAPER)


if __name__ == "__main__":
    build()
