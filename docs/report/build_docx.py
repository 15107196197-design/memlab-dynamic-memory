#!/usr/bin/env python3
"""Build the MemLab course report DOCX from the Markdown sources.

The Markdown files are the single source of truth for the report text.  This
builder deliberately does not renumber figures or tables: captions are copied
verbatim from the source files (the numbering is fixed by docs/report/README.md).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

REPORT_DIR = Path(__file__).resolve().parent
ROOT = REPORT_DIR.parents[2]
OUT = REPORT_DIR / "MemLab-课程报告-2026-11-09.docx"

SOURCES = [
    "00-summary.md",
    "01-intro.md",
    "02-memory.md",
    "03-architecture.md",
    "04-state.md",
    "05-retrieval.md",
    "06-design.md",
    "07-results.md",
    "08-discussion.md",
    "A-appendix.md",
]

# A4 with 2.54 cm margins.
PAGE_W = Cm(21.0)
PAGE_H = Cm(29.7)
MARGIN = Cm(2.54)
TEXT_W = Cm(15.8)
FIG_W = Cm(15.5)

DARK = RGBColor(0x17, 0x36, 0x5D)
BLUE = RGBColor(0x1F, 0x4E, 0x79)
MID = RGBColor(0x2E, 0x74, 0xB5)
GRAY = RGBColor(0x59, 0x59, 0x59)
LIGHT_GRAY = RGBColor(0x7F, 0x7F, 0x7F)
CODE = RGBColor(0x1F, 0x3B, 0x57)

BODY_EA = "宋体"
HEAD_EA = "黑体"
LATIN = "Times New Roman"
MONO = "Consolas"


# ---------------------------------------------------------------------------
# low-level helpers


def set_run_font(run, *, latin=LATIN, eastasia=BODY_EA, size=None, bold=None,
                 italic=None, color=None):
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), eastasia)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def shade(element_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element_pr.append(shd)


def set_paragraph_shading(paragraph, fill):
    shade(paragraph._p.get_or_add_pPr(), fill)


def set_cell_shading(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shade(tcpr, fill)


def set_paragraph_border(paragraph, *, side="left", color="B4C6E7", size=12,
                         space=6):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    border = OxmlElement(f"w:{side}")
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), str(size))
    border.set(qn("w:space"), str(space))
    border.set(qn("w:color"), color)
    pbdr.append(border)


def set_cell_margins(cell, top=40, bottom=40, left=70, right=70):
    tcpr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for key, value in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{key}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tcpr.append(mar)


def set_table_borders(table, color="B4C6E7", size=4):
    tbl = table._tbl
    tblpr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)
        borders.append(node)
    tblpr.append(borders)


def set_repeat_table_header(row):
    trpr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:tblHeader")
    node.set(qn("w:val"), "true")
    trpr.append(node)


def set_cant_split(row):
    trpr = row._tr.get_or_add_trPr()
    node = OxmlElement("w:cantSplit")
    node.set(qn("w:val"), "true")
    trpr.append(node)


def add_page_field(paragraph, instr, placeholder="1"):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)

    run2 = paragraph.add_run()
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = f" {instr} "
    run2._r.append(instr_el)

    run3 = paragraph.add_run()
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    run3._r.append(fld_sep)

    paragraph.add_run(placeholder)

    run4 = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run4._r.append(fld_end)


def clear_cell(cell):
    cell.text = ""


def add_body_paragraph(doc, text, *, style=None, indent=True):
    p = doc.add_paragraph(style=style)
    pf = p.paragraph_format
    pf.first_line_indent = Pt(21) if indent else Cm(0)
    pf.space_before = Pt(0)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.5
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf.widow_control = True
    parse_inline(text, p)
    return p


def add_bullet(doc, text, marker="•"):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.75)
    pf.first_line_indent = Cm(-0.45)
    pf.space_before = Pt(0)
    pf.space_after = Pt(1)
    pf.line_spacing = 1.2
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(marker + " ")
    set_run_font(run, size=10.5)
    parse_inline(text, p)
    return p


def add_numbered(doc, number, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.75)
    pf.first_line_indent = Cm(-0.45)
    pf.space_before = Pt(0)
    pf.space_after = Pt(1)
    pf.line_spacing = 1.2
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(f"{number}. ")
    set_run_font(run, size=10.5, bold=True)
    parse_inline(text, p)
    return p


def add_caption(doc, text, *, figure=False, keep_with_next=None, bold=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.left_indent = Cm(0)
    pf.space_before = Pt(6 if figure else 8)
    pf.space_after = Pt(3 if figure else 4)
    pf.line_spacing = 1.15
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.keep_with_next = bool(keep_with_next)
    parse_inline(text, p, bold=bold, base_size=9.5, base_color=GRAY)
    return p


def add_blockquote(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.6)
    pf.right_indent = Cm(0.3)
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(4)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.2
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_shading(p, "F4F7FB")
    set_paragraph_border(p, side="left", color="8EAADB", size=18, space=8)
    parse_inline(text, p, base_size=10, base_color=GRAY)
    return p


def add_code_block(doc, lines):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.25)
    pf.right_indent = Cm(0.1)
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(4)
    pf.space_after = Pt(8)
    pf.line_spacing = 1.0
    pf.keep_together = True
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_paragraph_shading(p, "F5F7FA")
    set_paragraph_border(p, side="left", color="B4C6E7", size=14, space=6)
    for idx, line in enumerate(lines):
        run = p.add_run(line if line else " ")
        set_run_font(run, latin=MONO, eastasia=BODY_EA, size=8.5, color=CODE)
        if idx != len(lines) - 1:
            run.add_break()
    return p


def add_heading(doc, text, level, *, page_break=False):
    p = doc.add_paragraph(style=f"Heading {level}")
    pf = p.paragraph_format
    pf.page_break_before = page_break
    pf.keep_with_next = True
    pf.keep_together = True
    if level == 1:
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(0)
        pf.space_after = Pt(14)
    elif level == 2:
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.space_before = Pt(14)
        pf.space_after = Pt(6)
    else:
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.space_before = Pt(9)
        pf.space_after = Pt(4)
    run = p.add_run(text)
    set_run_font(
        run,
        eastasia=HEAD_EA,
        size={1: 17, 2: 13, 3: 11.5}[level],
        bold=True,
        color=DARK if level == 1 else BLUE,
    )
    # A thin rule under chapter titles.
    if level == 1:
        set_paragraph_border(p, side="bottom", color="8EAADB", size=8, space=6)
    return p


# ---------------------------------------------------------------------------
# inline markdown


def parse_inline(text, paragraph, *, bold=False, italic=False, base_size=10.5,
                 base_color=None):
    """Render a small, deliberately limited subset of inline Markdown."""
    text = text.replace("\\|", "|").replace("\\*", "*")
    i = 0
    while i < len(text):
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end != -1:
                parse_inline(text[i + 2:end], paragraph, bold=True, italic=italic,
                             base_size=base_size, base_color=base_color)
                i = end + 2
                continue
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                run = paragraph.add_run(text[i + 1:end])
                set_run_font(run, latin=MONO, eastasia=BODY_EA, size=base_size - 1,
                             bold=bold, italic=italic, color=CODE)
                i = end + 1
                continue
        if text[i] == "*" and not text.startswith("**", i):
            end = text.find("*", i + 1)
            if end != -1:
                parse_inline(text[i + 1:end], paragraph, bold=bold, italic=True,
                             base_size=base_size, base_color=base_color)
                i = end + 1
                continue
        if text[i] == "[":
            match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[i:])
            if match:
                run = paragraph.add_run(match.group(1))
                set_run_font(run, size=base_size, bold=bold, italic=italic,
                             color=base_color or RGBColor(0x1F, 0x4E, 0x79))
                i += match.end()
                continue
        next_positions = [p for p in (
            text.find("**", i + 1),
            text.find("`", i + 1),
            text.find("*", i + 1),
            text.find("[", i + 1),
        ) if p != -1]
        end = min(next_positions) if next_positions else len(text)
        run = paragraph.add_run(text[i:end])
        set_run_font(run, size=base_size, bold=bold, italic=italic,
                     color=base_color)
        i = end


# ---------------------------------------------------------------------------
# tables


def split_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, buf = [], []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def visual_len(value):
    value = re.sub(r"`|\*\*|\*", "", value)
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in value)


def set_col_widths(table, widths_cm):
    tbl = table._tbl
    tblpr = tbl.tblPr
    tblw = OxmlElement("w:tblW")
    tblw.set(qn("w:w"), str(int(sum(widths_cm) / 2.54 * 1440)))
    tblw.set(qn("w:type"), "dxa")
    tblpr.append(tblw)
    for idx, width in enumerate(widths_cm):
        table.columns[idx].width = Cm(width)
        for cell in table.columns[idx].cells:
            cell.width = Cm(width)


def add_table(doc, rows):
    header = split_table_row(rows[0])
    aligns = ["left"] * len(header)
    if len(rows) > 1:
        for idx, spec in enumerate(split_table_row(rows[1])):
            if idx >= len(aligns):
                break
            spec = spec.strip()
            if spec.endswith(":") and spec.startswith(":"):
                aligns[idx] = "center"
            elif spec.endswith(":"):
                aligns[idx] = "right"
    body = [split_table_row(row) for row in rows[2:] if row.strip()]
    ncols = len(header)
    for row in body:
        while len(row) < ncols:
            row.append("")
    table = doc.add_table(rows=len(body) + 1, cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    set_col_widths(table, compute_widths([header] + body, ncols))
    # header
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    set_cant_split(hdr)
    for idx, cell_text in enumerate(header):
        cell = hdr.cells[idx]
        clear_cell(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_shading(cell, "1F4E79")
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT,
                       "center": WD_ALIGN_PARAGRAPH.CENTER,
                       "right": WD_ALIGN_PARAGRAPH.RIGHT}[aligns[idx]]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        parse_inline(cell_text, p, bold=True, base_size=8.5,
                     base_color=RGBColor(0xFF, 0xFF, 0xFF))
    # body
    for r_idx, row in enumerate(body, start=1):
        tr = table.rows[r_idx]
        set_cant_split(tr)
        for c_idx, cell_text in enumerate(row):
            cell = tr.cells[c_idx]
            clear_cell(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            if r_idx % 2 == 0:
                set_cell_shading(cell, "F2F6FA")
            p = cell.paragraphs[0]
            p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT,
                           "center": WD_ALIGN_PARAGRAPH.CENTER,
                           "right": WD_ALIGN_PARAGRAPH.RIGHT}[aligns[c_idx]]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            parse_inline(cell_text, p, base_size=8.5)
    return table


def compute_widths(rows, ncols):
    lengths = [1] * ncols
    for row in rows:
        for idx in range(min(ncols, len(row))):
            lengths[idx] = max(lengths[idx], visual_len(row[idx]))
    weights = []
    for length in lengths:
        # Long evidence columns get room, short ID columns do not.
        weights.append(max(4.0, min(26.0, length * 0.9 + 3.0)))
    total = sum(weights)
    widths = [max(1.35, TEXT_W.cm * w / total) for w in weights]
    scale = TEXT_W.cm / sum(widths)
    widths = [w * scale for w in widths]
    return widths


# ---------------------------------------------------------------------------
# document setup


def configure_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), LATIN)
    rfonts.set(qn("w:hAnsi"), LATIN)
    rfonts.set(qn("w:eastAsia"), BODY_EA)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(4)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for level in (1, 2, 3):
        style = doc.styles[f"Heading {level}"]
        style.font.name = LATIN
        style.font.bold = True
        style.font.color.rgb = DARK if level == 1 else BLUE
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:ascii"), LATIN)
        rfonts.set(qn("w:hAnsi"), LATIN)
        rfonts.set(qn("w:eastAsia"), HEAD_EA)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.keep_together = True


def setup_section(section):
    section.page_width = PAGE_W
    section.page_height = PAGE_H
    section.top_margin = MARGIN
    section.bottom_margin = MARGIN
    section.left_margin = MARGIN
    section.right_margin = MARGIN
    section.header_distance = Cm(1.4)
    section.footer_distance = Cm(1.6)


def add_header_footer(section):
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hp.paragraph_format.space_after = Pt(0)
    run = hp.add_run("MemLab 课程报告 · 2026-11-09")
    set_run_font(run, size=8.5, color=LIGHT_GRAY)
    set_paragraph_border(hp, side="bottom", color="D9E2F3", size=4, space=4)

    fp = section.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(0)
    run = fp.add_run("第 ")
    set_run_font(run, size=8.5, color=LIGHT_GRAY)
    add_page_field(fp, "PAGE")
    run = fp.add_run(" 页")
    set_run_font(run, size=8.5, color=LIGHT_GRAY)


def start_page_numbering(section, start=1):
    sectpr = section._sectPr
    pg = sectpr.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        sectpr.append(pg)
    pg.set(qn("w:start"), str(start))


# ---------------------------------------------------------------------------
# cover and contents


def add_cover(doc):
    for _ in range(3):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run("MEMLAB · DYNAMIC MEMORY WORKBENCH")
    set_run_font(run, size=9.5, bold=True, color=MID)
    set_paragraph_border(p, side="bottom", color="8EAADB", size=10, space=8)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(38)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run("MemLab：可插拔的记忆系统\n与诚实的消融评测")
    set_run_font(run, eastasia=HEAD_EA, size=25, bold=True, color=DARK)
    p.paragraph_format.line_spacing = 1.35

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("课程项目报告")
    set_run_font(run, eastasia=HEAD_EA, size=15, bold=True, color=MID)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(30)
    run = p.add_run("动态记忆工作台 · 基于 LoCoMo 长期多会话对话")
    set_run_font(run, size=10.5, color=GRAY)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("2026-11-09")
    set_run_font(run, size=12, bold=True, color=BLUE)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(26)
    run = p.add_run("课程交付版")
    set_run_font(run, size=9.5, color=LIGHT_GRAY)

    # Scope statement in a single-cell table.
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_col_widths(table, [14.5])
    cell = table.rows[0].cells[0]
    clear_cell(cell)
    set_cell_shading(cell, "EAF1F8")
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    set_table_borders(table, color="B4C6E7", size=4)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("口径声明")
    set_run_font(run, eastasia=HEAD_EA, size=10, bold=True, color=DARK)
    for line in (
        "归档 27B：2026-11-04 的 test 2 段归档，QA 120 题；本轮不重跑。",
        "offline：hashing embedding + 抽取式回答，A 级接口指标，不是 LLM F1。",
        "online 27B：qwen3.8:27b-q4_K_M + bge-m3，B 级答案，无 Judge。",
        "数字以 docs/report/numbers.md 为唯一台账；图号、表号按 docs/report/README.md 固定。",
    ):
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.2
        run = p.add_run(line)
        set_run_font(run, size=9, color=RGBColor(0x33, 0x33, 0x33))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(28)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("MemLab 课程项目 · 2026-11-09")
    set_run_font(run, size=8.5, color=LIGHT_GRAY)


def add_toc(doc, headings):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("目录")
    set_run_font(run, eastasia=HEAD_EA, size=18, bold=True, color=DARK)
    set_paragraph_border(p, side="bottom", color="8EAADB", size=8, space=6)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run("章节按正文顺序；图号与表号沿用源文件，不按出现顺序重排")
    set_run_font(run, size=8, color=LIGHT_GRAY)

    for level, text in headings:
        if level == 2 and text == "本章结论":
            continue
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.0 if level == 1 else 0.65)
        pf.first_line_indent = Cm(0)
        pf.space_before = Pt(7 if level == 1 else 2)
        pf.space_after = Pt(1)
        pf.line_spacing = 1.0
        run = p.add_run(text)
        if level == 1:
            set_run_font(run, eastasia=HEAD_EA, size=10.5, bold=True, color=DARK)
        else:
            set_run_font(run, size=9.5, color=GRAY)


# ---------------------------------------------------------------------------
# markdown file rendering


def read_headings(text):
    headings = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,2})\s+(.+)$", stripped)
        if m:
            headings.append((len(m.group(1)), m.group(2).strip()))
    return headings


def render_image(doc, alt, rel_path):
    path = (REPORT_DIR / rel_path).resolve()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.first_line_indent = Cm(0)
    pf.space_before = Pt(6)
    pf.space_after = Pt(2)
    pf.keep_with_next = True
    if not path.exists():
        run = p.add_run(f"[缺图：{rel_path}]")
        set_run_font(run, size=10, bold=True, color=RGBColor(0xC0, 0x00, 0x00))
        return False
    run = p.add_run()
    inline = run.add_picture(str(path), width=FIG_W)
    docpr = inline._inline.docPr
    docpr.set("descr", alt)
    docpr.set("title", alt.split("：")[0][:80])
    return True


def render_markdown_file(doc, path, *, first_h1_page_break=False):
    lines = path.read_text(encoding="utf-8").splitlines()
    idx = 0
    first_heading = True
    while idx < len(lines):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped:
            idx += 1
            continue

        # fenced code block
        if stripped.startswith("```"):
            code_lines = []
            idx += 1
            while idx < len(lines) and not lines[idx].strip().startswith("```"):
                code_lines.append(lines[idx].rstrip())
                idx += 1
            if idx < len(lines):
                idx += 1
            add_code_block(doc, code_lines)
            continue

        # image
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            alt, rel = m.group(1), m.group(2)
            render_image(doc, alt, rel)
            idx += 1
            # consume a following italic figure caption, allowing blank lines
            look = idx
            while look < len(lines) and not lines[look].strip():
                look += 1
            if look < len(lines):
                candidate = lines[look].strip()
                if candidate.startswith("*图 ") and candidate.endswith("*"):
                    add_caption(doc, candidate[1:-1], figure=True)
                    idx = look + 1
                    continue
            if alt:
                add_caption(doc, alt, figure=True)
            continue

        # table
        if stripped.startswith("|"):
            table_rows = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                table_rows.append(lines[idx].strip())
                idx += 1
            add_table(doc, table_rows)
            continue

        # headings
        m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            page_break = False
            if level == 1:
                if first_heading and first_h1_page_break:
                    page_break = True
                elif not first_heading:
                    page_break = True
                first_heading = False
            add_heading(doc, text, level, page_break=page_break)
            idx += 1
            continue

        # table caption (bold paragraph beginning with 表 N-M)
        if re.match(r"^\*\*表\s+[0-9A-Z]+-[0-9]+\s", stripped) and stripped.endswith("**"):
            add_caption(doc, stripped[2:-2], figure=False, keep_with_next=True, bold=True)
            idx += 1
            continue

        # figure caption not following an image (fallback)
        if stripped.startswith("*图 ") and stripped.endswith("*"):
            add_caption(doc, stripped[1:-1], figure=True)
            idx += 1
            continue

        # blockquote
        if stripped.startswith("> "):
            add_blockquote(doc, stripped[2:].strip())
            idx += 1
            continue

        # bullet list
        if stripped.startswith("- "):
            add_bullet(doc, stripped[2:].strip())
            idx += 1
            continue

        # numbered list
        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            add_numbered(doc, m.group(1), m.group(2).strip())
            idx += 1
            continue

        # horizontal rule
        if re.match(r"^-{3,}$", stripped):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            set_paragraph_border(p, side="bottom", color="D9E2F3", size=4, space=2)
            idx += 1
            continue

        # ordinary paragraph
        add_body_paragraph(doc, stripped)
        idx += 1


# ---------------------------------------------------------------------------


def main() -> int:
    missing = [name for name in SOURCES if not (REPORT_DIR / name).exists()]
    if missing:
        print("missing source files:", ", ".join(missing), file=sys.stderr)
        return 2

    doc = Document()
    configure_styles(doc)

    section1 = doc.sections[0]
    setup_section(section1)
    section1.different_first_page_header_footer = True
    add_cover(doc)

    section2 = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_section(section2)
    section2.different_first_page_header_footer = False
    add_header_footer(section2)
    start_page_numbering(section2, 1)

    headings = []
    for name in SOURCES:
        headings.extend(read_headings((REPORT_DIR / name).read_text(encoding="utf-8")))
    add_toc(doc, headings)

    # Summary begins on a fresh page, then each chapter and the appendix.
    for name in SOURCES:
        render_markdown_file(
            doc,
            REPORT_DIR / name,
            first_h1_page_break=True,
        )

    # Update fields (page numbers) when the document is opened in Word.
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)

    doc.save(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
