# -*- coding: utf-8 -*-
"""M3 · 图谱工作台：社区气泡 + 类型化边 + 选中节点证据。"""
import os
import math
from ui import (BG, PANEL, LINE, LINE2, INK, MUT, FAINT, ACCENT, ACCENT_BG, STATE,
                topbar, page_head, panel, text, rect, line, path, circle, write)

HERE = os.path.dirname(os.path.abspath(__file__))

CX0, CY0, CX1, CY1 = 286, 210, 1180, 930

C_COMM = {
    "support": ("#3F6E8C", "支持 / 身份"),
    "career": ("#8A6D3B", "职业 / 家庭"),
    "camping": ("#5E7A4E", "露营 / 社交"),
    "painting": ("#7A5A8E", "绘画 / 创作"),
}

TOPICS = [
    # id, label, x, y, r, community
    ("lgbtq_support", "lgbtq_support_participation", 700, 318, 18, "support"),
    ("gender_identity", "gender_identity", 790, 292, 14, "support"),
    ("advocacy_goal", "advocacy_goal", 640, 286, 13, "support"),
    ("emotional_state", "emotional_state", 768, 372, 15, "support"),
    ("career_interest", "career_interest", 396, 376, 15, "career"),
    ("adoption", "adoption_process", 470, 414, 14, "career"),
    ("family_goal", "family_goal", 356, 438, 13, "career"),
    ("camping_trip", "camping_trip", 466, 704, 16, "camping"),
    ("social", "social_gathering", 542, 748, 12, "camping"),
    ("painting_hobby", "painting_hobby", 916, 684, 17, "painting"),
    ("hobby_painting", "hobby_painting", 1002, 716, 15, "painting"),
    ("artwork", "artwork_embracing_identity", 960, 632, 12, "painting"),
]

UNITS = [
    # x, y, state, near topic
    (676, 356, "ACTIVE"), (726, 396, "HISTORICAL"), (694, 296, "ACTIVE"),
    (752, 330, "HISTORICAL"), (614, 316, "ACTIVE"),
    (414, 350, "ACTIVE"), (438, 446, "HISTORICAL"), (382, 402, "ACTIVE"),
    (500, 678, "ACTIVE"), (438, 734, "HISTORICAL"), (520, 716, "ACTIVE"),
    (930, 656, "ACTIVE"), (976, 690, "HISTORICAL"), (1016, 740, "ACTIVE"),
    (882, 714, "ACTIVE"), (700, 596, "ACTIVE"), (620, 512, "ACTIVE"), (700, 470, "HISTORICAL"),
    (902, 560, "HISTORICAL"), (1004, 544, "ACTIVE"), (760, 640, "ACTIVE"),
]

ENTITIES = [("Caroline", 660, 560, 34), ("Melanie", 958, 500, 30)]

ENT_EDGES = [
    # entity -> topic
    ("Caroline", "lgbtq_support"), ("Caroline", "emotional_state"), ("Caroline", "advocacy_goal"),
    ("Caroline", "career_interest"), ("Caroline", "adoption"), ("Caroline", "camping_trip"),
    ("Caroline", "artwork"), ("Caroline", "family_goal"),
    ("Melanie", "painting_hobby"), ("Melanie", "hobby_painting"), ("Melanie", "family_goal"),
    ("Melanie", "camping_trip"), ("Melanie", "lgbtq_support"), ("Melanie", "social"),
]

UNIT_EDGES = [
    (676, 356, "lgbtq_support"), (726, 396, "lgbtq_support"), (694, 296, "lgbtq_support"),
    (752, 330, "gender_identity"), (614, 316, "advocacy_goal"),
    (414, 350, "career_interest"), (438, 446, "adoption"), (382, 402, "career_interest"),
    (500, 678, "camping_trip"), (438, 734, "camping_trip"), (520, 716, "social"),
    (930, 656, "artwork"), (976, 690, "painting_hobby"), (1016, 740, "hobby_painting"),
    (882, 714, "painting_hobby"),
]

TOPIC_POS = {t[0]: (t[2], t[3], t[4]) for t in TOPICS}
ENT_POS = {e[0]: (e[1], e[2]) for e in ENTITIES}


def trim(a, b, ra, rb):
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    return (a[0] + ux * ra, a[1] + uy * ra, b[0] - ux * rb, b[1] - uy * rb)


def build():
    s = [topbar("图谱 Graph")]
    s.append(page_head("图谱工作台", "实体 / 主题 / 事件 / 记忆单元；社区气泡 + 类型化边 + 选中即证据",
                       "three_layer · 981 节点 / 1570 边（缓存构图）", eyebrow="GRAPH EXPLORER · 图谱"))

    # toolbar
    s.append(panel(24, 164, 1552, 766))
    tabs = [("实体三元组", False), ("稀疏事件图", False), ("状态槽", False), ("三层图", True)]
    x = 44
    for name, on in tabs:
        w = 104
        s.append(rect(x, 178, w, 26, "#FFFFFF" if on else "#F6F4EC", 6, LINE, 1))
        if on:
            s.append(rect(x, 178, w, 26, ACCENT_BG, 6, "#CFE0D6", 1))
        s.append(text(x + w / 2, 195, name, 9, ACCENT if on else "#5E6A72", 600 if on else 400, anchor="middle"))
        x += w + 6
    s.append(rect(492, 178, 300, 26, "#FCFBF7", 6, LINE, 1))
    s.append(text(504, 195, "搜索实体 / 主题 / 记忆…", 9, "#A9A294"))
    s.append(rect(806, 178, 96, 26, "#FCFBF7", 6, LINE, 1))
    s.append(text(816, 195, "深度 2 跳", 8.5, "#4E5A62"))
    s.append(rect(914, 178, 96, 26, "#FCFBF7", 6, LINE, 1))
    s.append(text(924, 195, "力导向 ⌄", 8.5, "#4E5A62"))
    s.append(text(1556, 195, "全屏", 8.5, "#3F5F86", anchor="end"))

    # ---------------- left panel ----------------
    s.append(rect(24, 218, 246, 700, "#FFFFFF", 10, LINE, 1))
    s.append(text(44, 244, "节点 NODE", 8, "#A2967F", 600, ls=1.5))
    for i, (lab, col, shape) in enumerate([("Memory unit", "#6E7A82", "dot"),
                                          ("Entity", "#2F5D8A", "big"),
                                          ("Topic", "#7A5A8E", "mid"),
                                          ("Event", "#8A6D3B", "dia")]):
        yy = 268 + i * 24
        if shape == "dot":
            s.append(circle(49, yy - 3, 3.5, col))
        elif shape == "big":
            s.append(circle(49, yy - 3, 6, "#E8EFF6", col, 2))
        elif shape == "mid":
            s.append(circle(49, yy - 3, 4.5, "#F1ECF5", col, 1.6))
        else:
            s.append(f'<polygon points="49,{yy-9} 54,{yy-3} 49,{yy+3} 44,{yy-3}" fill="{col}"/>')
        s.append(text(64, yy, lab, 8.8, "#4E5A62"))

    s.append(text(44, 386, "边 EDGE · 建议类型", 8, "#A2967F", 600, ls=1.5))
    for i, (lab, dash, col) in enumerate([("mentions  实体提及（绿色=选中）", None, "#9AA6AE"),
                                          ("about  记忆属于主题", None, "#B9A98C"),
                                          ("update  版本更新", "4 3", "#A33B3B"),
                                          ("duplicate  疑似重复", "4 3", "#B07A2A")]):
        yy = 410 + i * 24
        s.append(line(44, yy - 3, 66, yy - 3, col, 2, dash=dash))
        s.append(text(74, yy, lab, 8.5, "#4E5A62"))

    s.append(text(44, 522, "社区 COMMUNITY · 示意", 8, "#A2967F", 600, ls=1.5))
    for i, (key, (col, name)) in enumerate(C_COMM.items()):
        yy = 546 + i * 30
        s.append(circle(49, yy - 3, 5, col, opacity=0.18))
        s.append(circle(49, yy - 3, 2.2, col))
        s.append(text(64, yy, name, 9, "#3B4650", 500))

    s.append(text(44, 682, "状态过滤", 8, "#A2967F", 600, ls=1.5))
    for i, (st, zh) in enumerate([("ACTIVE", "有效"), ("HISTORICAL", "历史"), ("CONFLICT", "冲突")]):
        yy = 706 + i * 24
        s.append(rect(44, yy - 9, 10, 10, STATE[st][1], 3, STATE[st][0], 1))
        s.append(text(62, yy, zh, 8.8, "#4E5A62"))

    s.append(line(44, 792, 250, 792, LINE2, 1))
    s.append(text(44, 814, "981 nodes / 1570 edges", 7.8, FAINT))
    s.append(text(44, 830, "three_layer · cached", 7.8, FAINT))
    s.append(text(44, 852, "cached facts/states", 7.8, "#8A7A5C"))
    s.append(text(44, 880, "K 维护不在单题图谱执行", 7.4, FAINT))

    # ---------------- canvas ----------------
    s.append(rect(CX0, CY0, CX1 - CX0, CY1 - CY0, "#FEFDFB", 10, LINE, 1))
    for gx in range(CX0 + 20, CX1, 26):
        for gy in range(CY0 + 20, CY1, 26):
            s.append(circle(gx, gy, 0.8, "#DDD6C6", opacity=0.5))

    # community hulls
    hulls = [("support", 720, 332, 138, 100, 592, 247), ("career", 420, 404, 118, 92, 312, 327),
             ("camping", 492, 716, 112, 82, 390, 648), ("painting", 962, 686, 132, 98, 1028, 603)]
    for key, hx, hy, rx, ry, lx, ly in hulls:
        col = C_COMM[key][0]
        s.append(f'<ellipse cx="{hx}" cy="{hy}" rx="{rx}" ry="{ry}" fill="{col}" fill-opacity="0.05" '
                 f'stroke="{col}" stroke-opacity="0.22" stroke-dasharray="4 5"/>')
        s.append(text(lx, ly, C_COMM[key][1], 8.5, col, 600, opacity=0.8))

    # edges: entity -> topic
    for en, tid in ENT_EDGES:
        ex, ey = ENT_POS[en]
        tx, ty, tr = TOPIC_POS[tid]
        x1, y1, x2, y2 = trim((ex, ey), (tx, ty), 30 if en == "Caroline" else 26, tr)
        hot = en == "Caroline"
        s.append(line(x1, y1, x2, y2, ACCENT if hot else "#9AA6AE", 1.8 if hot else 1, 0.62 if hot else 0.32))

    # edges: unit -> topic
    for ux, uy, tid in UNIT_EDGES:
        tx, ty, tr = TOPIC_POS[tid]
        x1, y1, x2, y2 = trim((ux, uy), (tx, ty), 3, tr)
        s.append(line(x1, y1, x2, y2, "#C9C2B2", 0.8, 0.55))

    # special: update between two units
    s.append(line(700, 476, 700, 590, "#A33B3B", 1.6, 0.8, dash="4 3"))
    s.append(rect(712, 522, 58, 18, "#FBEFEF", 4, "#E3C2C2", 1))
    s.append(text(741, 535, "UPDATE", 7, "#8E2B2B", 700, anchor="middle"))
    # special: duplicate topics
    s.append(line(933, 688, 987, 712, "#B07A2A", 1.6, 0.9, dash="4 3"))
    s.append(line(960, 786, 960, 712, "#E5D2AC", 1, 0.9, dash="2 3"))
    s.append(rect(878, 788, 86, 18, "#FBF3E2", 4, "#E5D2AC", 1))
    s.append(text(921, 801, "疑似重复", 7, "#8A5D16", 700, anchor="middle"))

    # units
    for ux, uy, st in UNITS:
        s.append(circle(ux, uy, 5, STATE[st][1], STATE[st][0], 1.4))
        s.append(circle(ux, uy, 1.6, STATE[st][0]))

    # topics
    for tid, lab, tx, ty, tr, comm in TOPICS:
        col = C_COMM[comm][0]
        s.append(circle(tx, ty, tr, "#FFFFFF", col, 1.8, 0.95))
        s.append(circle(tx, ty, tr * 0.45, col, opacity=0.12))
        s.append(text(tx + tr + 6, ty + 3, lab, 7.4, "#5E6A72"))

    # event node
    s.append(line(620, 660, 480, 704, "#8A6D3B", 1, 0.5))
    s.append(line(620, 660, 542, 748, "#8A6D3B", 1, 0.5))
    s.append('<polygon points="620,650 632,660 620,670 608,660" fill="#FBF3E2" stroke="#8A6D3B" stroke-width="1.6"/>')
    s.append(text(640, 664, "event: camping trip", 7.2, "#8A6D3B", 600))

    # entities
    for name, ex, ey, r in ENTITIES:
        sel = name == "Caroline"
        s.append(circle(ex, ey, r + 7, "#FFFFFF", ACCENT if sel else "#2F5D8A", 1, 0.6 if sel else 0.25))
        s.append(circle(ex, ey, r, "#F4F8F5" if sel else "#F4F7FA", ACCENT if sel else "#2F5D8A", 2.2))
        s.append(text(ex, ey + 5, name, 13, "#23414F" if sel else "#243B55", 700, anchor="middle"))
        s.append(text(ex, ey + r + 16, "entity", 7, FAINT, anchor="middle"))

    # hint
    s.append(text(CX0 + 16, CY1 - 16, "拖拽平移 · 滚轮缩放 · 点击节点看证据", 7.5, FAINT))
    # minimap
    s.append(rect(1032, 830, 132, 84, "#FFFFFF", 8, LINE, 1))
    s.append(text(1042, 846, "minimap", 6.5, FAINT))
    for ux, uy, st in UNITS[::2]:
        s.append(circle(1042 + (ux - 300) / 900 * 112, 856 + (uy - 250) / 660 * 48, 1.2, "#9AA6AE"))
    s.append(rect(1042 + (600 - 300) / 900 * 112, 856 + (450 - 250) / 660 * 48, 20, 14, ACCENT, 2, opacity=0.25))

    # ---------------- right panel ----------------
    RX = 1196
    s.append(rect(RX, 218, 380, 700, "#FFFFFF", 10, LINE, 1))
    s.append(text(RX + 20, 246, "entity:caroline", 9, "#6E7A82", 500, family="SF Mono, Menlo, monospace"))
    s.append(rect(RX + 300, 236, 58, 18, "#E8EFF6", 9, "#C9D8E6", 1))
    s.append(text(RX + 329, 249, "Entity", 7.5, "#2F5D8A", 600, anchor="middle"))
    s.append(text(RX + 20, 280, "Caroline", 22, INK, 700))
    s.append(text(RX + 20, 302, "degree 402 · 191 facts", 8.5, MUT))

    s.append(line(RX + 20, 318, RX + 360, 318, LINE, 1))
    s.append(text(RX + 20, 342, "关联主题", 8, "#A2967F", 600, ls=1.2))
    rel = [("支持 / 身份", "lgbtq_support_participation", "#3F6E8C"),
           ("情绪", "emotional_state", "#3F6E8C"),
           ("职业", "career_interest", "#8A6D3B"),
           ("家庭", "adoption_process", "#8A6D3B")]
    for i, (zh, en, col) in enumerate(rel):
        yy = 366 + i * 42
        s.append(circle(RX + 26, yy - 3, 3.5, col))
        s.append(text(RX + 38, yy, zh, 9, "#3B4650", 600))
        s.append(text(RX + 38, yy + 14, en, 7.5, FAINT, family="SF Mono, Menlo, monospace"))

    s.append(line(RX + 20, 542, RX + 360, 542, LINE, 1))
    s.append(text(RX + 20, 566, "最近证据", 8, "#A2967F", 600, ls=1.2))
    s.append(rect(RX + 20, 578, 340, 84, "#FBF9F1", 7, "#E8E1CF", 1))
    s.append(text(RX + 32, 600, "D19:9", 7, "#2F6F9E", 600, family="SF Mono, Menlo, monospace"))
    s.append(text(RX + 32, 620, "“Transitioning wasn't easy and", 8.2, "#3B4650"))
    s.append(text(RX + 32, 636, "acceptance wasn't either…”", 8.2, "#3B4650"))
    s.append(text(RX + 32, 652, "点击打开记录页 → conv26_D19_9", 7.2, FAINT))

    s.append(text(RX + 20, 694, "数据质量", 8, "#A2967F", 600, ls=1.2))
    s.append(rect(RX + 20, 706, 340, 74, "#FBF7EA", 8, "#EADFC4", 1))
    s.append(text(RX + 32, 726, "painting_hobby 与 hobby_painting", 8, "#6E6448"))
    s.append(text(RX + 32, 742, "各 23 / 22 条边，疑似同一主题。", 8, "#6E6448"))
    s.append(text(RX + 32, 762, "建议：合并或建 alias 后再算社区。", 7.5, "#8A6D1F"))

    for i, (lab, primary) in enumerate([("以此为中心", True), ("只看 2 跳", False), ("只看冲突", False)]):
        xx = RX + 20 + i * 112
        s.append(rect(xx, 806, 104, 26, ACCENT if primary else "#FCFBF7", 13,
                      ACCENT if primary else LINE, 1))
        s.append(text(xx + 52, 823, lab, 8, "#FFFFFF" if primary else "#4E5A62",
                      600 if primary else 400, anchor="middle"))

    s.append(text(RX + 20, 872, "节点详情只读；证据在 M1 记录页打开。", 7.2, FAINT))
    s.append(text(RX + 20, 888, "4 种图表示共用同一交互与图例。", 7.2, FAINT))

    write(os.path.join(HERE, "m3-graph.html"), "".join(s), "M3 · 图谱工作台")


if __name__ == "__main__":
    build()
