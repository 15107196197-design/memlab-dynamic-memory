# -*- coding: utf-8 -*-
"""Shared helpers for the experiment-map figures (pure-SVG, no deps)."""

W, H = 1600, 1000
SANS = "PingFang SC, Hiragino Sans GB, Source Han Sans SC, Noto Sans CJK SC, sans-serif"
MONO = "SF Mono, JetBrains Mono, Menlo, monospace"


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, t, size=14, fill="#E8EEF8", weight=400, anchor="start",
         opacity=1.0, ls=0, family=SANS, extra=""):
    o = f' opacity="{opacity}"' if opacity != 1 else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{o}{l}{extra}>'
            f'{esc(t)}</text>')


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1, opacity=1.0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    o = f' opacity="{opacity}"' if opacity != 1 else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}"{s}{o}{extra}/>')


def line(x1, y1, x2, y2, stroke="#fff", sw=1, opacity=1.0, dash=None,
         cap="round", extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{opacity}"' if opacity != 1 else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}{o}{extra}/>')


def path(d, fill="none", stroke=None, sw=1, opacity=1.0, dash=None, cap="round",
         join="round", extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}" stroke-linejoin="{join}"' if stroke else ""
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{opacity}"' if opacity != 1 else ""
    return f'<path d="{d}" fill="{fill}"{s}{dd}{o}{extra}/>'


def circle(cx, cy, r, fill="none", stroke=None, sw=1, opacity=1.0, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    o = f' opacity="{opacity}"' if opacity != 1 else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"{s}{o}{extra}/>'


def marker_defs(colors):
    out = []
    for i, c in enumerate(colors):
        out.append(
            f'<marker id="ar{i}" viewBox="0 0 10 10" refX="8.5" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    return "".join(out)


def head(title, bg="#080D17", extra_css="", w=W, h=H):
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>
  html,body{{margin:0;padding:0;width:{w}px;height:{h}px;overflow:hidden;background:{bg};}}
  text{{white-space:pre;}}
  {extra_css}
</style></head><body>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
"""


TAIL = "</svg></body></html>\n"


def write_page(path, body, title, bg="#080D17", extra_css="", w=W, h=H):
    with open(path, "w", encoding="utf-8") as f:
        f.write(head(title, bg, extra_css, w, h))
        f.write(body)
        f.write(TAIL)
    print("wrote", path)
