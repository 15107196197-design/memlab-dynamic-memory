# -*- coding: utf-8 -*-
"""M1 · 记忆记录工作台：把格式化记忆当作一等记录来读。"""
import os
from datetime import date
from ui import (BG, PANEL, LINE, LINE2, INK, MUT, FAINT, ACCENT, ACCENT_BG, STATE, KIND,
                topbar, page_head, panel, state_pill, kind_chip, dot,
                text, rect, line, path, circle, write)

HERE = os.path.dirname(os.path.abspath(__file__))

CARDS = [
    ("conv26_D1_7_f0", "HISTORICAL", "fact", "feels accepted and has courage to embrace…",
     "Caroline · state", "D1 · 2023-05-08 · 证据 1"),
    ("conv26_D1_9_f0", "ACTIVE", "fact", "continue education and check out career options",
     "Caroline · goal", "D1 · 2023-05-08 · 证据 1"),
    ("conv26_D1_3_f0", "ACTIVE", "fact", "attended an LGBTQ support group",
     "Caroline · event", "D1 · 2023-05-07 · 证据 1"),
    ("conv26_D2_8_f0", "HISTORICAL", "fact", "researching adoption agencies",
     "Caroline · current_activity", "D2 · 2023-05-25 · 证据 1"),
    ("conv26_D2_7_f1", "HISTORICAL", "fact", "going camping",
     "Melanie · planned_activity", "D2 · 2023-05-25 · 证据 1"),
    ("conv26_D1_16_f0", "ACTIVE", "fact", "painting",
     "Melanie · hobby", "D1 · 2023-05-08 · 证据 1"),
    ("conv26_D3_14_f0", "ACTIVE", "fact", "husband and kids",
     "Melanie · family_members", "D3 · 2023-06-09 · 证据 1"),
]


def sec(x, y, t, w=None):
    s = text(x, y, t, 8.5, "#A2967F", 600, ls=1.6)
    if w:
        s += line(x, y + 8, x + w, y + 8, LINE2, 1)
    return s


def build():
    s = [topbar("记忆库")]
    s.append(page_head("记忆库", "结构化 Memory v2 · 每条记录带 schema、双时间、证据与失效链",
                       "conv-26 · 754 条（fact 335 / event 146 / turn 419）"))

    # ---------------- left rail ----------------
    s.append(panel(24, 164, 248, 788))
    s.append(rect(40, 184, 216, 34, "#FCFBF7", 7, LINE, 1))
    s.append(text(52, 205, "搜索 content / entity / id…", 9.5, "#A9A294"))
    s.append(sec(40, 246, "状态 STATE · FACT"))
    states = [("ACTIVE", "有效", 287), ("HISTORICAL", "历史", 48),
              ("CONFLICT", "冲突", 0), ("UNRESOLVED", "未解析", 0)]
    for i, (k, zh, n) in enumerate(states):
        yy = 270 + i * 28
        s.append(rect(40, yy - 8, 10, 10, STATE[k][1], 3, STATE[k][0], 1))
        s.append(text(58, yy, zh, 10.5, "#3B4650", 500))
        s.append(text(256, yy, str(n), 9.5, FAINT, anchor="end"))

    s.append(sec(40, 400, "类型 KIND"))
    for i, (k, zh, n) in enumerate([("fact", "事实 Fact", 335), ("event", "事件 Event", 146), ("turn", "轮次 Turn", 419)]):
        yy = 424 + i * 28
        s.append(circle(45, yy - 3, 3, KIND[k]))
        s.append(text(58, yy, zh, 10.5, "#3B4650", 500))
        s.append(text(256, yy, str(n), 9.5, FAINT, anchor="end"))

    s.append(sec(40, 526, "实体 ENTITY"))
    for i, (nm, n) in enumerate([("Caroline", 191), ("Melanie", 127), ("其他", 17)]):
        yy = 550 + i * 28
        s.append(text(58, yy, nm, 10.5, "#3B4650", 500))
        s.append(text(256, yy, str(n), 9.5, FAINT, anchor="end"))

    s.append(sec(40, 646, "时间范围"))
    s.append(rect(40, 660, 216, 30, "#FCFBF7", 6, LINE, 1))
    s.append(text(52, 679, "2023-05-08  →  2023-10-22", 9.5, "#4E5A62", 500))
    s.append(sec(40, 716, "槽位 SLOT"))
    for i, t in enumerate(["state", "goal", "career_interest", "current_activity"]):
        yy = 740 + i * 26
        s.append(text(52, yy, t, 9.5, "#5E6A72"))
        s.append(text(256, yy, ["7", "40", "6", "5"][i], 9, FAINT, anchor="end"))

    s.append(line(40, 868, 256, 868, LINE2, 1))
    s.append(text(40, 892, "schema 2.0 · extractor legacy_flat", 8.2, FAINT))
    s.append(text(40, 910, "facts_model qwen3.8:27b-q4_K_M", 8.2, FAINT))
    s.append(rect(40, 924, 216, 16, "#F4F0E4", 4))
    s.append(text(48, 935, "缓存构图，不是实时抽取", 8.2, "#8A7A5C"))

    # ---------------- list ----------------
    s.append(panel(288, 164, 520, 788))
    s.append(text(304, 192, "事实 Fact", 13, INK, 700))
    s.append(text(374, 192, "335 条 · 按时间倒序", 9.5, FAINT))
    s.append(text(792, 192, "排序 ⌄", 9, "#5E6A72", anchor="end"))
    y = 210
    for i, (mid, st, kind, val, meta, sub) in enumerate(CARDS):
        h = 92
        sel = i == 0
        s.append(rect(300, y, 496, h, "#FCFBF6" if sel else "#FFFFFF", 8,
                      LINE if not sel else "#CBDDD2", 1))
        if sel:
            s.append(rect(300, y + 10, 3, h - 20, ACCENT, 1.5))
        s.append(text(318, y + 24, mid, 10, "#6E7A82", 500, family="SF Mono, Menlo, monospace"))
        p, w = state_pill(778 - 58, y + 12, st)
        s.append(rect(778 - 58, y + 12, 58, 18, STATE[st][1], 9, STATE[st][0], 0.9))
        s.append(text(778 - 29, y + 24.5, {"ACTIVE": "有效", "HISTORICAL": "历史"}.get(st, st), 8.5, STATE[st][2], 600, anchor="middle"))
        s.append(text(318, y + 50, val, 12.5, INK, 600))
        s.append(text(318, y + 70, meta, 9.5, "#6E7A82"))
        s.append(text(318, y + 86, sub, 8.5, FAINT))
        if sel:
            s.append(text(792, y + 50, "›", 18, ACCENT, 600, anchor="end"))
        y += h + 8

    s.append(text(304, 932, "显示 7 / 335 条", 9, FAINT))

    # ---------------- detail ----------------
    X, W = 824, 752
    s.append(panel(X, 164, W, 788))
    s.append(text(X + 24, 196, "conv26_D1_7_f0", 12.5, "#33404A", 600, family="SF Mono, Menlo, monospace"))
    s.append(rect(X + 186, 181, 68, 19, STATE["HISTORICAL"][1], 9, STATE["HISTORICAL"][0], 0.9))
    s.append(text(X + 220, 194, "历史", 8.5, STATE["HISTORICAL"][2], 600, anchor="middle"))
    s.append(text(X + 268, 195, "schema 2.0", 8.5, FAINT))
    s.append(text(X + 348, 195, "confidence 1.00", 8.5, FAINT))
    s.append(text(X + W - 24, 195, "导出 JSON", 9, "#3F5F86", anchor="end"))

    s.append(text(X + 24, 232, "feels accepted and has courage", 20, INK, 600))
    s.append(text(X + 24, 258, "to embrace herself", 20, INK, 600))
    s.append(text(X + 24, 282, "Caroline · state · slot emotional_state", 9.5, MUT))

    # fields
    s.append(sec(X + 24, 312, "结构化字段 STRUCTURED", W - 48))
    fields = [
        ("entity", "Caroline"), ("attribute", "state"),
        ("value", "feels accepted and has courage…"), ("slot", "emotional_state"),
        ("t_event", "unknown"), ("valid_interval", "start unknown  →  2023-06-27"),
        ("t_ingest", "2023-05-08 13:56"), ("evidence", "1 条 · span null"),
        ("source", "conv26_D1_7"), ("confidence", "1.00"),
    ]
    for i, (k, v) in enumerate(fields):
        col = i % 2
        row = i // 2
        xx = X + 24 + col * 356
        yy = 338 + row * 26
        s.append(text(xx, yy, k, 8.5, FAINT, family="SF Mono, Menlo, monospace"))
        s.append(text(xx + 92, yy, v, 9.5, "#33404A", 500))

    # time strip
    s.append(sec(X + 24, 492, "时间 BITEMPORAL", W - 48))
    d0 = date(2023, 5, 1).toordinal()
    d1 = date(2023, 11, 1).toordinal()

    def px(o):
        return X + 120 + (o - d0) / (d1 - d0) * 600

    axis_y = 560
    s.append(line(X + 120, axis_y, X + 720, axis_y, LINE, 1))
    for m in range(5, 12):
        o = date(2023, m, 1).toordinal()
        s.append(line(px(o), axis_y, px(o), axis_y + 5, "#CFC8B8", 1))
        s.append(text(px(o), axis_y + 16, f"{m}月", 8, FAINT, anchor="middle"))
    # rows
    ev_y, ig_y, va_y = 512, 528, 544
    s.append(text(X + 24, 516, "t_event", 8.5, FAINT, family="SF Mono, Menlo, monospace"))
    s.append(line(X + 120, ev_y, X + 300, ev_y, "#CFC8B8", 4, 0.5, dash="3 4"))
    s.append(text(X + 306, ev_y + 3, "unknown", 8, FAINT))
    s.append(text(X + 24, 532, "t_ingest", 8.5, FAINT, family="SF Mono, Menlo, monospace"))
    s.append(circle(px(date(2023, 5, 8).toordinal()), ig_y, 4.5, "#2F6F9E"))
    s.append(text(px(date(2023, 5, 8).toordinal()) + 10, ig_y + 3, "05-08", 8, "#2F6F9E"))
    s.append(text(X + 24, 548, "valid", 8.5, FAINT, family="SF Mono, Menlo, monospace"))
    vx0 = px(date(2023, 5, 8).toordinal())
    vx1 = px(date(2023, 6, 27).toordinal())
    s.append(rect(vx0, va_y - 5, vx1 - vx0, 10, "#B07A2A", 5, opacity=0.85))
    s.append(line(vx1, va_y - 7, vx1 + 4, va_y + 7, "#A33B3B", 1.6))
    s.append(line(vx1 + 4, va_y - 7, vx1 + 8, va_y + 7, "#A33B3B", 1.6))
    s.append(text(vx1 + 14, va_y + 3, "06-27 被 D4:15 更新", 8, "#8E2B2B"))

    # evidence
    s.append(sec(X + 24, 600, "证据 EVIDENCE", W - 48))
    s.append(rect(X + 24, 612, W - 48, 82, "#FBF9F1", 7, "#E8E1CF", 1))
    s.append(text(X + 40, 634, "D1:7", 9, "#2F6F9E", 600, family="SF Mono, Menlo, monospace"))
    s.append(text(X + 40, 656, "“The support group has made me feel accepted and", 10.5, "#3B4650"))
    s.append(text(X + 40, 674, "given me courage to embrace myself.”", 10.5, "#3B4650"))
    s.append(text(X + 40, 688, "机器抽取 quote：feels accepted and has courage…（span: null，未对齐原文）",
                  8, "#A9761F"))

    # invalidation
    s.append(sec(X + 24, 720, "失效链 INVALIDATION", W - 48))
    s.append(rect(X + 24, 732, 92, 24, "#EEF3F8", 5, "#C9D8E6", 1))
    s.append(text(X + 70, 748, "D1:7", 8.5, "#2F5D8A", 600, anchor="middle", family="SF Mono, Menlo, monospace"))
    s.append(path(f"M {X+120} 744 L {X+156} 744", stroke="#B9C2C9", sw=1.4))
    s.append(text(X + 160, 747, "UPDATE", 7.5, "#8A5D16", 600))
    s.append(path(f"M {X+204} 744 L {X+232} 744", stroke="#B9C2C9", sw=1.4))
    s.append(rect(X + 236, 732, 120, 24, "#FBEFEF", 5, "#E3C2C2", 1))
    s.append(text(X + 296, 748, "conv26_D4_15_f2", 8, "#8E2B2B", 600, anchor="middle", family="SF Mono, Menlo, monospace"))
    s.append(text(X + 368, 747, "endpoint t_ingest · end_known true", 8, FAINT))

    # provenance
    s.append(sec(X + 24, 786, "溯源 PROVENANCE", W - 48))
    steps = [("turn", "D1:7"), ("extractor", "legacy_flat"), ("fact", "D1_7_f0"), ("state", "HISTORICAL")]
    for i, (k, v) in enumerate(steps):
        xx = X + 24 + i * 172
        s.append(rect(xx, 798, 154, 30, "#FCFBF7", 6, LINE, 1))
        s.append(text(xx + 12, 810, k, 7, FAINT, ls=1))
        s.append(text(xx + 12, 822, v, 9, "#33404A", 600))
        if i < 3:
            s.append(text(xx + 160, 817, "→", 10, "#B9B09C"))

    # relations
    s.append(sec(X + 24, 862, "关系 RELATIONS", 200))
    for i, t in enumerate(["entity:caroline", "slot:emotional_state", "invalidated_by D4_15_f2"]):
        xx = X + 24 + i * 190
        s.append(rect(xx, 874, 180, 22, "#F4F7F5", 5, "#D8E4DC", 1))
        s.append(text(xx + 10, 889, t, 7.8, "#3C6B57", 500))

    s.append(text(X + W - 24, 932, "← 可切到「时间轴」看同一槽位的前后版本", 8.5, FAINT, anchor="end"))

    write(os.path.join(HERE, "m1-records.html"), "".join(s), "M1 · 记忆记录工作台")


if __name__ == "__main__":
    build()
