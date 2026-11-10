#!/usr/bin/env python3
"""Сборка фирменного стиля «Наш декор» (вариант 40 «Галерея», антрацит):
SVG-логотипы с текстом в кривых, PNG любых размеров, иконки сайта, favicon.ico.
Запуск: python brand/build.py (нужны fonttools, uharfbuzz, pillow, playwright + Chrome)."""
import io, os, json, re, urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import uharfbuzz as hb

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")
os.makedirs(OUT + "/svg", exist_ok=True); os.makedirs(OUT + "/png", exist_ok=True); os.makedirs(OUT + "/site", exist_ok=True)
A, G, B, D, K = "#26292E", "#F8F8F6", "#7E97AD", "#D9DEE3", "#A89F91"
SUB_ON_DARK, SUB_ON_LIGHT = "#C3CAD2", "#585E66"
WORD, SUB = "Наш декор", "панели · плинтусы · молдинги"

def get_font(urls, axes):
    for u in urls:
        try:
            data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            f = TTFont(io.BytesIO(data))
            if "fvar" in f:
                f = instancer.instantiateVariableFont(f, {k: v for k, v in axes.items() if k in [a.axisTag for a in f["fvar"].axes]})
            assert all(ord(c) in f.getBestCmap() for c in "Нашдекорплинтусымолдинги"), "нет кириллицы"
            b = io.BytesIO(); f.save(b); return f, b.getvalue()
        except Exception as e:
            print("font fail", u, e)
    raise SystemExit("шрифт не скачался")

SERIF, SERIF_B = get_font(["https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifdisplay/NotoSerifDisplay%5Bwdth,wght%5D.ttf"], {"wght": 600, "wdth": 100})
SANS, SANS_B = get_font(["https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"], {"wght": 600, "opsz": 14})

def shape(font, fbytes, text, size, x0, y0, ls_em=0.0):
    face = hb.Face(fbytes); hf = hb.Font(face); upem = face.upem
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(hf, buf, {"kern": True, "liga": True})
    gs = font.getGlyphSet(); order = font.getGlyphOrder(); sc = size / upem
    x, parts = 0.0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = SVGPathPen(gs)
        gs[order[info.codepoint]].draw(TransformPen(pen, (sc, 0, 0, -sc, x0 + (x + pos.x_offset) * sc, y0 - pos.y_offset * sc)))
        c = pen.getCommands()
        if c: parts.append(c)
        x += pos.x_advance + ls_em * upem
    width = (x - ls_em * upem) * sc
    return " ".join(parts), width

def cap(font, size): return font["OS/2"].sCapHeight / font["head"].unitsPerEm * size

def mark(x, y, s, fg, inner):
    k = s / 56.0
    r = lambda rx, ry, w, h, c, sw: f'<rect x="{x+rx*k:.2f}" y="{y+ry*k:.2f}" width="{w*k:.2f}" height="{h*k:.2f}" fill="none" stroke="{c}" stroke-width="{sw*k:.2f}"/>'
    return r(4, 9, 26, 38, fg, 2.5) + r(9, 14, 16, 28, inner, 1.6) + r(34, 17, 18, 24, fg, 2.5) + r(38.5, 21.5, 9, 15, inner, 1.6)

def svg(w, h, body, bg=None):
    b = f'<rect width="{w:.2f}" height="{h:.2f}" fill="{bg}"/>' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" width="{w:.0f}" height="{h:.0f}">{b}{body}</svg>'

def horizontal(fg, inner, word_c, sub_c, bg=None, with_sub=True, M=160.0):
    pad = M * 0.45 if bg else M * 0.06
    ws, ss = M * 0.58, M * 0.15
    cw, cs = cap(SERIF, ws), cap(SANS, ss)
    gap_t = M * 0.17
    block = cw + (gap_t + cs if with_sub else 0)
    top = pad + (M - block) / 2
    xb = pad + M + M * 0.32
    wp, ww = shape(SERIF, SERIF_B, WORD, ws, xb, top + cw)
    body = mark(pad, pad, M, fg, inner) + f'<path d="{wp}" fill="{word_c}"/>'
    width = ww
    if with_sub:
        sp, sw = shape(SANS, SANS_B, SUB, ss, xb + M * 0.01, top + cw + gap_t + cs, 0.02)
        body += f'<path d="{sp}" fill="{sub_c}"/>'; width = max(ww, sw)
    W, H = xb + width + pad, M + 2 * pad
    return svg(W, H, body, bg)

def stacked(fg, inner, word_c, sub_c, bg=None, side=1080.0):
    M = side * 0.30; ws, ss = side * 0.115, side * 0.03
    cw, cs = cap(SERIF, ws), cap(SANS, ss)
    total = M + side * 0.07 + cw + side * 0.045 + cs
    y0 = (side - total) / 2
    wp, ww = shape(SERIF, SERIF_B, WORD, ws, 0, 0)
    sp, sw = shape(SANS, SANS_B, SUB, ss, 0, 0, 0.02)
    wp, _ = shape(SERIF, SERIF_B, WORD, ws, (side - ww) / 2, y0 + M + side * 0.07 + cw)
    sp, _ = shape(SANS, SANS_B, SUB, ss, (side - sw) / 2, y0 + M + side * 0.07 + cw + side * 0.045 + cs, 0.02)
    body = mark((side - M) / 2, y0, M, fg, inner) + f'<path d="{wp}" fill="{word_c}"/><path d="{sp}" fill="{sub_c}"/>'
    return svg(side, side, body, bg)

def icon(side=1024.0, scale=0.60, bg=A, round_=False):
    M = side * scale
    b = f'<circle cx="{side/2}" cy="{side/2}" r="{side/2}" fill="{bg}"/>' if round_ else f'<rect width="{side}" height="{side}" fill="{bg}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {side} {side}" width="{side:.0f}" height="{side:.0f}">{b}{mark((side-M)/2, (side-M)/2, M, G, B)}</svg>'

files = {
 "logo-horizontal-on-anthracite.svg": horizontal(G, B, G, SUB_ON_DARK, bg=A),
 "logo-horizontal-on-white.svg": horizontal(A, B, A, SUB_ON_LIGHT, bg="#FFFFFF"),
 "logo-horizontal-for-dark-transparent.svg": horizontal(G, B, G, SUB_ON_DARK),
 "logo-horizontal-for-light-transparent.svg": horizontal(A, B, A, SUB_ON_LIGHT),
 "logo-horizontal-mono-anthracite.svg": horizontal(A, A, A, A),
 "logo-horizontal-mono-white.svg": horizontal(G, G, G, G),
 "logo-short-for-light-transparent.svg": horizontal(A, B, A, SUB_ON_LIGHT, with_sub=False),
 "logo-short-for-dark-transparent.svg": horizontal(G, B, G, SUB_ON_DARK, with_sub=False),
 "logo-stacked-on-anthracite-1080.svg": stacked(G, B, G, SUB_ON_DARK, bg=A),
 "logo-stacked-on-white-1080.svg": stacked(A, B, A, SUB_ON_LIGHT, bg="#FFFFFF"),
 "mark-anthracite.svg": svg(56, 56, mark(0, 0, 56, A, B)),
 "mark-white.svg": svg(56, 56, mark(0, 0, 56, G, B)),
 "icon-square-anthracite.svg": icon(),
 "avatar-round-anthracite.svg": icon(round_=True, scale=0.56),
}
for n, s in files.items():
    open(f"{OUT}/svg/{n}", "w").write(s)

# PNG через Chrome
from playwright.sync_api import sync_playwright
def size_of(s):
    m = re.search(r'width="([\d.]+)" height="([\d.]+)"', s); return float(m.group(1)), float(m.group(2))
renders = []
for n, s in files.items():
    w, h = size_of(s)
    if n.startswith("logo-horizontal") or n.startswith("logo-short"):
        renders.append((n, s, 2400, round(2400 * h / w)))
    elif n.startswith("logo-stacked"):
        renders.append((n, s, 1080, 1080))
    elif n.startswith("mark"):
        renders.append((n, s, 1024, 1024))
    elif n.startswith("icon-square"):
        for px in (1024, 512, 192, 180, 48, 32, 16):
            renders.append((f"icon-square-anthracite-{px}.svg", s, px, px))
    elif n.startswith("avatar"):
        renders.append((n, s, 1024, 1024))
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for n, s, w, h in renders:
        pg = br.new_page(viewport={"width": int(w), "height": int(h)})
        s2 = re.sub(r'width="[\d.]+" height="[\d.]+"', f'width="{w}" height="{h}"', s, count=1)
        pg.set_content(f'<html><head><style>html,body{{margin:0;background:transparent}}svg{{display:block}}</style></head><body>{s2}</body></html>')
        name = n.replace(".svg", "") + ("" if re.search(r"-\d+$", n.replace(".svg", "")) else f"-{w}")
        pg.screenshot(path=f"{OUT}/png/{name}.png", omit_background=True)
        pg.close()
    br.close()

# иконки для сайта
import shutil
from PIL import Image
sq = lambda px: f"{OUT}/png/icon-square-anthracite-{px}.png"
Image.open(sq(48)).save(f"{OUT}/site/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[Image.open(sq(32)), Image.open(sq(16))])
shutil.copy(sq(512), f"{OUT}/site/icon-512.png"); shutil.copy(sq(192), f"{OUT}/site/icon-192.png"); shutil.copy(sq(180), f"{OUT}/site/apple-touch-icon.png")
shutil.copy(f"{OUT}/svg/icon-square-anthracite.svg", f"{OUT}/site/icon.svg")
print("готово:", sorted(os.listdir(OUT + "/png")))
