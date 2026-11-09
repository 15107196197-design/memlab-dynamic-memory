# -*- coding: utf-8 -*-
"""E · 瓶颈诊断树：从端到端结果倒推该修哪个模块。"""
import os
from _common import text, rect, line, path, circle, marker_defs, write_page, MONO

PAPER = "#FBFAF6"
INK = "#1F2A33"
INK2 = "#5A6672"
MUT = "#8B949E"

DARK = "#22303A"
C_W = "#C98A1E"
C_S = "#1F8F84"
C_R = "#2F6FD0"
C_M = "#6D4FCC"
C_U = "#C9415C"
C_N = "#55656F"
C_OK = "#4C8A5E"


def card(cx, cy, w, h, dark=False):
    x, y = cx - w / 2, cy - h / 2
    if dark:
        return rect(x, y, w, h, DARK, 12, extra=' filter="url(#sh)"'), x, y
    return rect(x, y, w, h, "#FFFFFF", 12, "#E3DED2", 1, extra=' filter="url(#sh)"'), x, y


def qcard(cx, cy, num, title, measure, w=446, h=88):
    out = []
    r_, x, y = card(cx, cy, w, h, dark=True)
    out.append(r_)
    out.append(rect(x, y + 14, 3, h - 28, "#E9C46A", 2, opacity=0.9))
    out.append(text(x + 20, y + 30, num, 10, "#E9C46A", 700, family=MONO))
    out.append(text(x + 40, y + 30, title, 14, "#F4F7F9", 700))
    out.append(text(x + 20, y + 56, measure, 9.2, "#A9B8C2"))
    return "".join(out)


def tcard(cx, cy, col, title, sub, w=300, h=80):
    out = []
    r_, x, y = card(cx, cy, w, h)
    out.append(r_)
    out.append(rect(x, y, 4, h, col, 2))
    out.append(text(x + 18, y + 30, title, 12, INK, 700))
    out.append(text(x + 18, y + 50, sub, 8.8, "#7A838C"))
    return "".join(out)


def alabel(x, y, t, col="#4C8A5E"):
    return text(x, y, t, 9, col, 700)


def build():
    s = []
    s.append('<defs>'
             '<filter id="sh" x="-20%" y="-20%" width="140%" height="150%">'
             '<feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#5B4A33" flood-opacity="0.10"/>'
             '</filter>'
             + marker_defs(["#AEB6BD", "#8B949E"]) +
             '<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">'
             '<circle cx="1" cy="1" r="0.9" fill="#D9D2C2" opacity="0.55"/></pattern>'
             '</defs>')
    s.append(rect(0, 0, 1600, 1000, PAPER))
    s.append(rect(0, 0, 1600, 1000, "url(#dots)"))

    # header
    s.append(text(64, 76, "04 · EXPERIMENTS  /  DIAGNOSIS TREE", 10, "#A2967F", 600, ls=2.2))
    s.append(text(64, 122, "瓶颈诊断树", 36, INK, 700))
    s.append(text(64, 150, "结果不对时，按顺序问五个问题，别一上来就加模块。", 11.5, "#7C7264"))

    # legend card
    s.append(rect(1128, 62, 408, 96, "#FFFDF8", 12, "#E3DED2", 1, extra=' filter="url(#sh)"'))
    s.append(text(1148, 86, "判 定 顺 序", 9, "#A2967F", 700, ls=2))
    s.append(text(1148, 106, "上限 → 召回 → 使用 → LLM 归因", 10.5, "#3F4B56", 500))
    s.append(text(1148, 126, "每一步都带：质量 + Tokens + P95", 9.5, "#7C7264"))
    s.append(text(1148, 144, "并用 Oracle 干预给出该模块的上界", 9.5, "#7C7264"))

    # arrows first (behind cards)
    def arr(d, dash=None):
        return path(d, stroke="#AEB6BD", sw=1.8, dash=dash, extra=' marker-end="url(#ar0)"')

    s.append(arr("M700,181 L700,214"))
    s.append(arr("M700,309 L700,351"))
    s.append(arr("M700,447 L700,489"))
    s.append(arr("M700,585 L700,712"))
    s.append(arr("M700,807 L700,853"))

    s.append(arr("M477,262 L425,262"))
    s.append(arr("M477,400 L425,400"))
    s.append(arr("M920,566 C 956,566 940,643 974,643"))
    s.append(arr("M478,760 L435,760"))
    s.append(arr("M1105,690 L1052,726"))
    s.append(arr("M1258,690 L1252,726"))

    # labels
    s.append(alabel(712, 200, "是"))
    s.append(alabel(712, 336, "是"))
    s.append(alabel(712, 474, "是"))
    s.append(alabel(712, 654, "是"))
    s.append(alabel(712, 836, "否"))
    s.append(alabel(404, 250, "否", "#B4553A"))
    s.append(alabel(404, 388, "否", "#B4553A"))
    s.append(alabel(938, 600, "否", "#B4553A"))
    s.append(alabel(414, 748, "是"))
    s.append(alabel(1064, 700, "是"))
    s.append(alabel(1280, 700, "否", "#B4553A"))

    # start
    s.append(rect(520, 123, 360, 58, "#2A3742", 14, extra=' filter="url(#sh)"'))
    s.append(text(700, 149, "端到端结果不理想", 15, "#F4F7F9", 700, anchor="middle"))
    s.append(text(700, 168, "或：系统增益不稳定、跑不出差异", 9, "#A9B8C2", anchor="middle"))

    # questions
    s.append(qcard(700, 262, "Q1", "存储 / 检索上限 ceiling 够高吗？",
                   "测法：gold 证据的 memory_id 在不在索引里；低 → 任何检索器都救不了"))
    s.append(qcard(700, 400, "Q2", "R 的实际召回接近上限吗？",
                   "测法：Recall@K ÷ ceiling；差距大 → 是 R 的问题，不是 S 的问题"))
    s.append(qcard(700, 538, "Q3", "P(A=1 | R=1) 高吗？",
                   "测法：检索成功时答案正确的条件概率；这是“检索好=答案好”的试金石"))
    s.append(qcard(1180, 643, "Q4", "给 oracle context 能答对吗？",
                   "测法：只放 gold 证据，看 P(A | oracle context)", w=400, h=86))
    s.append(qcard(700, 760, "Q5", "系统增益随 LLM 变强而消失吗？",
                   "测法：G = metric(system) − metric(full_text)，逐档 LLM 对比", w=440))

    # terminals
    s.append(tcard(270, 262, C_W, "W / S：写入或表示不足", "先修 Schema / 图表示，不要调检索"))
    s.append(tcard(270, 400, C_R, "R：检索 / 规划是瓶颈", "查规划正确率、通道独有命中、k"))
    s.append(tcard(1052, 769, C_M, "M：合并 / 上下文构造", "查排序、去重、压缩、格式", w=196, h=78))
    s.append(tcard(1268, 769, C_U, "U：使用 / LLM / 提示词", "换格式、证据链、回答模型", w=196, h=78))
    s.append(tcard(275, 760, C_N, "系统在补偿弱 LLM", "定位模块；弱模型部署，别宣称普适"))
    s.append(tcard(700, 890, C_OK, "设计有独立价值", "进 E3 组合 / E4 环境网格，再确认稳健性", w=440, h=62))

    # side note: oracle ladder
    s.append(rect(1060, 880, 476, 86, "#FFFDF8", 10, "#E3DED2", 1))
    s.append(text(1080, 904, "Oracle 六件套 = 六次“换成金标准”的干预", 9.5, "#5A6672", 600))
    s.append(text(1080, 924, "write / store / retrieval / merge / state / answer", 8.8, "#8B949E", family=MONO))
    s.append(text(1080, 944, "正常系统与它的差距，就是该模块的贡献", 8.8, "#8B949E"))

    # bottom
    s.append(line(64, 946, 1000, 946, "#E0D8C8", 1))
    s.append(text(64, 972, "任一路径的结论都要写清：适用条件、边界、质量 / Tokens / P95；否则只是“跑过”。",
                  10, "#7C7264"))

    write_page(os.path.join(os.path.dirname(__file__), "05-diagnosis-tree.html"),
               "".join(s), "E · 瓶颈诊断树", bg=PAPER)


if __name__ == "__main__":
    build()
