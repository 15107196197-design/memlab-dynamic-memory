# -*- coding: utf-8 -*-
"""M2 · 记忆时间轴：槽位版本、有效期、失效点与 as-of 快照。"""
import os
from datetime import date
from ui import (BG, PANEL, LINE, LINE2, INK, MUT, FAINT, ACCENT, ACCENT_BG, STATE,
                topbar, page_head, panel, state_pill, dot,
                text, rect, line, path, circle, write)

HERE = os.path.dirname(os.path.abspath(__file__))
D0 = date(2023, 5, 1).toordinal()
D1 = date(2023, 11, 1).toordinal()
X0, X1 = 300, 1150


def px(d):
    return X0 + (d.toordinal() - D0) / (D1 - D0) * (X1 - X0)


ROWS = [
    ("group", "Caroline", 191),
    ("row", "state", 7, [("D1_7_f0", date(2023, 5, 8), date(2023, 6, 27), "HISTORICAL",
                           "feels accepted…", None)]),
    ("row", "goal", 40, [("D1_9_f0", date(2023, 5, 8), None, "ACTIVE",
                          "continue education…", None)]),
    ("row", "career_interest", 6, [("D1_11_f0", date(2023, 5, 8), None, "ACTIVE",
                                    "counseling / mental health", None)]),
    ("row", "current_activity", 5, [("D2_8_f0", date(2023, 5, 25), date(2023, 7, 14), "HISTORICAL",
                                     "researching adoption", None)]),
    ("row", "event", 7, [("D1_3_f0", date(2023, 5, 7), None, "ACTIVE",
                          "LGBTQ support group", "point")]),
    ("group", "Melanie", 127),
    ("row", "state", 7, [("D1_2_f0", date(2023, 5, 8), None, "ACTIVE",
                          "swamped with kids & work", None)]),
    ("row", "hobby", 3, [("D1_16_f0", date(2023, 5, 8), None, "ACTIVE",
                          "painting", None)]),
    ("row", "planned_activity", 4, [("D2_7_f1", date(2023, 5, 25), date(2023, 6, 27), "HISTORICAL",
                                     "going camping", None)]),
    ("row", "current_activity", 5, [("D1_18_f0", date(2023, 5, 8), date(2023, 10, 13), "HISTORICAL",
                                     "swimming with kids", None)]),
    ("row", "family_members", 3, [("D3_14_f0", date(2023, 6, 9), None, "ACTIVE",
                                   "husband and kids", None)]),
]

SESSIONS = [(1, date(2023, 5, 8)), (2, date(2023, 5, 25)), (3, date(2023, 6, 9)),
            (4, date(2023, 6, 27)), (5, date(2023, 7, 3)), (6, date(2023, 7, 6)),
            (7, date(2023, 7, 12)), (8, date(2023, 7, 15)), (9, date(2023, 7, 17)),
            (10, date(2023, 7, 20)), (11, date(2023, 8, 14)), (12, date(2023, 8, 17)),
            (13, date(2023, 8, 23)), (14, date(2023, 8, 25)), (15, date(2023, 8, 28)),
            (16, date(2023, 9, 13)), (17, date(2023, 10, 13)), (18, date(2023, 10, 20)),
            (19, date(2023, 10, 22))]

ASOF = date(2023, 8, 1)


def build():
    s = [topbar("记忆库")]
    s.append(page_head("记忆时间轴", "槽位版本、有效期与失效点；虚线表示起点未知，用首次写入时间近似",
                       "19 个会话 · 2023-05-08 → 2023-10-22"))

    # toolbar
    s.append(panel(24, 164, 1552, 786))
    s.append(text(44, 190, "实体", 8.5, FAINT))
    s.append(rect(78, 178, 86, 24, "#FCFBF7", 6, LINE, 1))
    s.append(text(88, 194, "全部", 9.5, "#4E5A62", 500))
    s.append(text(180, 190, "状态", 8.5, FAINT))
    s.append(rect(214, 178, 86, 24, "#FCFBF7", 6, LINE, 1))
    s.append(text(224, 194, "全部", 9.5, "#4E5A62", 500))
    s.append(text(316, 190, "粒度", 8.5, FAINT))
    s.append(rect(350, 178, 86, 24, "#FCFBF7", 6, LINE, 1))
    s.append(text(360, 194, "会话", 9.5, "#4E5A62", 500))
    s.append(text(1560, 195, "导出", 8.5, "#3F5F86", anchor="end"))

    # month grid
    for m in range(5, 12):
        d = date(2023, m, 1)
        x = px(d)
        s.append(line(x, 224, x, 826, LINE2, 1))
        if m < 11:
            s.append(text(x + 6, 222, f"{m} 月", 8, FAINT))
    # session ticks
    for i, (n, d) in enumerate(SESSIONS):
        x = px(d)
        s.append(line(x, 230, x, 236, "#D8D2C2", 1))
        if i % 2 == 0:
            s.append(text(x, 248, f"D{n}", 7, "#A9A294", anchor="middle"))
    s.append(line(X0, 236, X1, 236, "#E4DED0", 1))

    # rows
    y = 268
    row_idx = 0
    for item in ROWS:
        if item[0] == "group":
            _, name, n = item
            y += 4
            s.append(rect(44, y - 12, 3, 16, ACCENT if name == "Caroline" else "#8A6D3B", 1.5))
            s.append(text(54, y, name, 11.5, INK, 700))
            s.append(text(54 + len(name) * 8 + 10, y, f"{n} facts", 8.5, FAINT))
            y += 14
            continue
        _, attr, n, items = item
        # row guide
        s.append(line(44, y + 22, X1, y + 22, "#F5F2EA", 1))
        s.append(text(56, y + 18, attr, 9.5, "#4E5A62", 500))
        for (mid, ds, de, st, lab, kind) in items:
            col = STATE[st][0]
            cy = y + 14
            bx = px(ds)
            if kind == "point":
                s.append(f'<polygon points="{bx},{cy-6} {bx+6},{cy} {bx},{cy+6} {bx-6},{cy}" '
                         f'fill="{col}" opacity="0.9"/>')
                s.append(text(bx + 12, cy - 8, lab, 7.5, STATE[st][2]))
                s.append(text(bx + 12, cy + 4, mid, 6.5, FAINT, family="SF Mono, Menlo, monospace"))
            else:
                ex = px(de) if de else X1 - 8
                # unknown start: dashed lead-in
                s.append(line(bx - 26, cy, bx - 2, cy, col, 3, 0.35, dash="2 4"))
                s.append(rect(bx, cy - 6, max(8, ex - bx), 12, col, 6, opacity=0.72 if st == "ACTIVE" else 0.5))
                s.append(circle(bx, cy, 3.2, "#FFFFFF", col, 1.4))
                if de:
                    s.append(line(ex, cy - 7, ex, cy + 7, col, 1.4))
                    s.append(text(ex + 5, cy + 3, "×", 8, "#8E2B2B", 700))
                else:
                    s.append(text(X1 - 2, cy + 3, "→", 9, col, 600, anchor="end"))
                s.append(text(bx + 4, cy - 9, lab, 7.5, STATE[st][2]))
                s.append(text(bx + 4, cy + 15, mid, 6.5, FAINT, family="SF Mono, Menlo, monospace"))
        # annotation for the update chain
        if attr == "state" and row_idx == 0:
            ex = px(date(2023, 6, 27))
            s.append(text(ex + 10, y + 42, "06-27 被 D4:15_f2 更新", 7.2, "#8E2B2B"))
        row_idx += 1
        y += 50

    # as-of line
    ax = px(ASOF)
    s.append(rect(ax, 224, X1 - ax, 602, "#F4F1E7", 0, opacity=0.45))
    s.append(line(ax, 224, ax, 826, ACCENT, 1.4, 0.8, dash="4 4"))
    s.append(rect(ax - 62, 832, 124, 20, "#FFFFFF", 10, "#CFE0D6", 1))
    s.append(text(ax, 846, "as_of 2023-08-01", 8.5, ACCENT, 600, anchor="middle"))

    # legend
    ly = 858
    s.append(line(44, 838, 1150, 838, LINE2, 1))
    s.append(text(44, ly, "图例", 8, FAINT, 600, ls=1.5))
    lx = 100
    for st, lab in [("ACTIVE", "有效"), ("HISTORICAL", "历史")]:
        s.append(rect(lx, ly - 8, 22, 8, STATE[st][0], 4, opacity=0.72))
        s.append(text(lx + 28, ly, lab, 8, "#5E6A72"))
        lx += 70
    s.append(line(lx, ly - 4, lx + 26, ly - 4, "#B9A98C", 2, 0.5, dash="2 4"))
    s.append(text(lx + 32, ly, "起点未知", 8, "#5E6A72"))
    lx += 96
    s.append(text(lx, ly, "→ 开区间", 8, "#5E6A72"))
    lx += 70
    s.append(text(lx, ly, "× 失效", 8, "#8E2B2B"))
    lx += 62
    s.append(f'<polygon points="{lx},{ly-5} {lx+5},{ly} {lx},{ly+5} {lx-5},{ly}" fill="#8A6D3B"/>')
    s.append(text(lx + 10, ly, "事件", 8, "#5E6A72"))
    s.append(text(1150, 922, "多数 fact 的 t_event 缺失；条形起点为首次写入时间，虚线表示真实起点未知。",
                  8.5, FAINT, anchor="end"))

    # ---------------- right: as-of snapshot ----------------
    RX = 1170
    s.append(rect(RX, 214, 388, 612, "#FCFBF7", 10, LINE, 1))
    s.append(text(RX + 20, 242, "as_of  2023-08-01", 13, INK, 700))
    s.append(text(RX + 20, 260, "6 条有效 · 3 条已失效", 8.5, FAINT))
    s.append(line(RX + 20, 270, RX + 368, 270, LINE, 1))

    active = [
        ("Caroline · goal", "continue education and check out career options", "ACTIVE", "05-08 →"),
        ("Caroline · career_interest", "counseling or working in mental health", "ACTIVE", "05-08 →"),
        ("Melanie · state", "swamped with kids and work", "ACTIVE", "05-08 →"),
        ("Melanie · hobby", "painting", "ACTIVE", "05-08 →"),
        ("Melanie · current_activity", "swimming with the kids", "ACTIVE", "05-08 → 10-13"),
        ("Melanie · family_members", "husband and kids", "ACTIVE", "06-09 →"),
    ]
    yy = 292
    for i, (k, v, st, tm) in enumerate(active):
        s.append(text(RX + 20, yy, k, 8.5, "#3B4650", 600))
        s.append(text(RX + 368, yy, tm, 7.5, FAINT, anchor="end"))
        s.append(text(RX + 20, yy + 14, v, 8.5, "#5E6A72"))
        s.append(circle(RX + 20, yy + 28, 2.5, STATE[st][0]))
        s.append(text(RX + 28, yy + 30, "有效", 7, STATE[st][2]))
        yy += 50
        if i < 5:
            s.append(line(RX + 20, yy - 10, RX + 368, yy - 10, LINE2, 1))

    s.append(line(RX + 20, 612, RX + 368, 612, LINE, 1))
    s.append(text(RX + 20, 634, "已失效 3", 8.5, "#8E2B2B", 600))
    expired = ["Caroline · state（06-27 被更新）", "Caroline · current_activity（07-14）",
               "Melanie · planned_activity（06-27）"]
    for i, t in enumerate(expired):
        s.append(text(RX + 20, 654 + i * 18, t, 8, "#8A8F94"))

    s.append(rect(RX + 20, 712, 348, 96, "#FBF7EA", 8, "#EADFC4", 1))
    s.append(text(RX + 34, 734, "数据质量提示", 8.5, "#8A6D1F", 700))
    s.append(text(RX + 34, 752, "goal 槽位全库 40 条 fact；", 8, "#6E6448"))
    s.append(text(RX + 34, 768, "同名主题 painting_hobby / hobby_painting", 8, "#6E6448"))
    s.append(text(RX + 34, 784, "在图谱里各占 23 / 22 条边，尚未归一。", 8, "#6E6448"))
    s.append(text(RX + 34, 798, "建议：槽位合并 + 主题归一化后再看趋势。", 7.6, "#8A6D1F"))

    write(os.path.join(HERE, "m2-timeline.html"), "".join(s), "M2 · 记忆时间轴")


if __name__ == "__main__":
    build()
