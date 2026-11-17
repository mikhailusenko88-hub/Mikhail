"""Can 1 ball fill the CAT? — неоновый вид (как у соседей: чёрный фон, радужные шарики, без текста). python3 render.py out.mp4 [TOT] [только_кадры: t1,t2,...]"""
import colorsys
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fastvid as fv
import picture_bear as PC
import shape_bear as S
import subprocess

W, H, FPS = 1080, 1920, 30
R = 11.0
NT = 1140
OUT = sys.argv[1] if len(sys.argv) > 1 else "cat.mp4"
TOT = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
STILLS = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else None

# ---------- данные симуляции ----------
raw = np.fromfile("sim_bear.bin", dtype=np.uint8)
frames, off = [], 0
while off < len(raw):
    n = int(np.frombuffer(raw[off:off + 4], np.int32)[0]); off += 4
    xy = np.frombuffer(raw[off:off + 8 * n], np.float32).reshape(n, 2).copy(); off += 8 * n
    frames.append(xy)
birth = np.zeros(NT + 10)
N0 = 1
hits, spawns = [], []
for line in open("events_bear.txt"):
    p = line.split()
    if p[0] == "S":
        birth[int(p[2])] = float(p[1]); spawns.append((float(p[1]), int(p[2])))
    elif p[0] == "H":
        hits.append(float(p[1]))
    elif p[0] == "F":
        FULL = float(p[1])
    elif p[0] == "I":
        N0 = int(p[1])
hits = np.array(hits)
T_MUS = float(open('bear_grid.txt').read().split()[-1])   # конец мелодии = 100%
TR = T_MUS + 0.45         # «пык» — как в музыке
TA = TR + 0.9             # медведь оживает
TEND = TA + 4.3
if TOT:
    TEND = min(TEND, TOT)
NF = int(TEND * FPS)
final = frames[-1]
N = len(final)

# ---------- картинка ----------
cx0, cy0 = S.CX, S.CY + 40
dist = np.hypot(final[:, 0] - cx0, final[:, 1] - cy0)
WAVE_V = 1150.0
tw = TR + dist / WAVE_V
cols = {}
for st in ("center", "left", "right", "closed"):
    img = PC.make(st)
    cols[st] = np.clip(PC.sample(img, final[:, 0], final[:, 1], rad=5) * 0.97, 0, 255).astype(np.uint8)


def state_at(t):
    r = t - TA
    if 0.5 <= r < 0.68 or 2.5 <= r < 2.63 or 2.75 <= r < 2.88:
        return "closed"
    if 1.0 <= r < 1.6:
        return "left"
    if 1.6 <= r < 2.2:
        return "right"
    return "center"


# неоновая радуга до «пыка»
rng = np.random.default_rng(11)
pre = np.zeros((N, 3), np.uint8)
for i in range(N):
    h = rng.random()
    r, g, b = colorsys.hsv_to_rgb(h, 0.88, 1.0)
    pre[i] = (int(r * 255), int(g * 255), int(b * 255))

# ---------- спрайты ----------
_SP = {}


def sprite(col, rad, wh=0.35):
    key = (tuple(int(c) for c in col), rad, wh)
    s = _SP.get(key)
    if s is not None:
        return s
    ss = 4
    size = int(math.ceil(rad * 2 + 3))
    n = size * ss
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / ss - size / 2 + 0.5 / ss
    d = np.hypot(xx, yy) / rad
    a = np.clip((1 - d) * rad * 1.0 + 0.5, 0, 1)
    c = np.array(col, np.float32)[None, None, :]
    core = np.clip(1 - d / 0.55, 0, 1)[..., None] ** 1.5      # светлая середина — «светится»
    c = c * (0.85 + 0.15 * (1 - d[..., None])) + (255 - c) * wh * core
    rgba = np.dstack([np.clip(c, 0, 255), a * 255]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").resize((size, size), Image.LANCZOS)
    _SP[key] = (im, size)
    return _SP[key]


def glow_sprite(col, rad):
    key = ("g", tuple(col), rad)
    if key in _SP:
        return _SP[key]
    size = int(rad * 2)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) - size / 2 + 0.5
    a = np.exp(-(xx ** 2 + yy ** 2) / (rad * 0.42) ** 2) * 235
    rgba = np.dstack([np.full((size, size), c, np.float32) for c in col] + [a]).astype(np.uint8)
    _SP[key] = (Image.fromarray(rgba, "RGBA"), size)
    return _SP[key]


# ---------- фон ----------
def make_bg():
    f = S.field()
    arr = np.zeros((H, W, 3), np.float32)
    halo = Image.fromarray((np.clip(1 - np.abs(f) / 26, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14))
    halo = np.asarray(halo, np.float32)[..., None] / 255
    arr = arr + halo * np.array([255, 140, 30], np.float32) * 0.9
    line = np.clip(1 - (np.abs(f + 1.0) - 2.0), 0, 1)[..., None]
    arr = arr * (1 - line) + line * np.array([255, 250, 240], np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


BG = make_bg()

# ---------- текст ----------
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FE = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
_F = {}


def font(sz):
    if sz not in _F:
        _F[sz] = ImageFont.truetype(FB, sz)
    return _F[sz]


_EM = {}


def emoji(ch, size):
    key = (ch, size)
    if key not in _EM:
        f = ImageFont.truetype(FE, 109)
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((8, 8), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        k = size / im.size[1]
        _EM[key] = im.resize((int(im.size[0] * k), size), Image.LANCZOS)
    return _EM[key]


def text_line(img, y, parts, size, stroke=8):
    """parts: [(текст, цвет) | ('emoji', символ)] — строка по центру."""
    d = ImageDraw.Draw(img)
    f = font(size)
    widths = []
    for p in parts:
        widths.append(emoji(p[1], int(size * 1.0)).size[0] + 14 if p[0] == "emoji" else d.textlength(p[0], font=f))
    x = (W - sum(widths)) / 2
    for p, w in zip(parts, widths):
        if p[0] == "emoji":
            e = emoji(p[1], int(size * 1.0))
            img.paste(e, (int(x + 10), int(y + size * 0.08)), e)
        else:
            d.text((x, y), p[0], font=f, fill=p[1], stroke_width=stroke, stroke_fill=(0, 0, 0))
        x += w


YEL, WHT, GRN, PNK = (255, 214, 64), (255, 255, 255), (120, 255, 140), (255, 120, 190)


def titles(img, t):
    if t < TA + 0.5:
        text_line(img, 150, [("Every bounce = +1 ball", WHT)], 66)
        text_line(img, 236, [("Can they fill the BEAR?", YEL), ("emoji", "🐻")], 80)
    elif t < TA + 3.0:
        text_line(img, 150, [("Wait...", WHT)], 72)
        text_line(img, 236, [("it BLINKED?!", PNK), ("emoji", "😳")], 96)
    else:
        text_line(img, 150, [("Which animal", WHT)], 72)
        text_line(img, 236, [("next?", YEL), ("emoji", "👇")], 104)


def counter(img, t, n):
    d = ImageDraw.Draw(img, "RGBA")
    full = t >= FULL
    pct = 100 if full else min(99, int(100 * n / NT))
    f = font(50)
    lab = f"{n:,} BALL" + ("" if n == 1 else "S")
    d.text((190, 392), lab, font=f, fill=WHT, stroke_width=6, stroke_fill=(0, 0, 0))
    ps = f"{pct}%"
    col = GRN if full else YEL
    d.text((890 - d.textlength(ps, font=f), 392), ps, font=f, fill=col, stroke_width=6, stroke_fill=(0, 0, 0))
    x0, x1, y0, y1 = 190, 890, 466, 492
    d.rounded_rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], radius=16, fill=(0, 0, 0, 200))
    d.rounded_rectangle([x0, y0, x1, y1], radius=13, fill=(40, 46, 80, 255))
    fr = 1.0 if full else n / NT
    if fr > 0.01:
        xe = x0 + max(26, (x1 - x0) * fr)
        d.rounded_rectangle([x0, y0, xe, y1], radius=13, fill=(GRN if full else (90, 220, 255)) + (255,))


# ---------- кадр ----------
def draw_frame(i):
    t = i / FPS
    fi = min(i, len(frames) - 1)
    xy = frames[fi]
    n = len(xy)
    img = BG.copy()
    if n < 48 and t < FULL:
        ga = 1.0 - n / 48
        g, gs = glow_sprite((255, 255, 255), 60)
        if ga < 1:
            g = g.copy(); g.putalpha(g.getchannel("A").point(lambda v: int(v * ga)))
        for j in range(n):
            img.paste(g, (int(xy[j, 0] - gs / 2), int(xy[j, 1] - gs / 2)), g)
        # хвост из прошлых кадров
        d = ImageDraw.Draw(img, "RGBA")
        for back in range(1, 7):
            if fi - back < 0:
                break
            pv = frames[fi - back]
            rr = 11 * (1 - back / 9)
            al = int(200 * (1 - back / 7) * ga)
            for j in range(min(n, len(pv))):
                x, y = pv[j]
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=tuple(int(v) for v in pre[j]) + (al,))
        # кольцо на каждом делении
        for (bt, bj) in spawns[:64]:
            a = t + 1 / FPS - bt
            if 0 <= a < 0.3 and bj < len(xy):
                x, y = xy[bj]
                rr = 12 + 70 * a / 0.3
                d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(255, 255, 255, int(230 * (1 - a / 0.3))), width=5)
    if t < TR:
        for j in range(n):
            age = max(0.0, t + 1 / FPS - birth[j]) if j >= N0 else 9
            if age < 0.2:
                c = np.clip(pre[j].astype(np.int32) + (255 - pre[j].astype(np.int32)) * (1 - age / 0.2), 0, 255).astype(np.uint8)
                sp, sz = sprite(c, 13 if age < 0.1 else 12)
            else:
                sp, sz = sprite(pre[j], 11)
            img.paste(sp, (int(round(xy[j, 0] - sz / 2)), int(round(xy[j, 1] - sz / 2))), sp)
    else:
        st = cols[state_at(t)]
        for j in range(n):
            dt_ = t - tw[j]
            if dt_ < 0:
                sp, sz = sprite(pre[j], 11)
            elif dt_ < 0.07:
                sp, sz = sprite((255, 255, 255), 14)
            else:
                rad = 12.5 if dt_ < 0.22 else 11.6
                sp, sz = sprite(st[j], rad, 0.12)
            img.paste(sp, (int(round(xy[j, 0] - sz / 2)), int(round(xy[j, 1] - sz / 2))), sp)
    # свечение: размытая уменьшенная копия поверх
    small = img.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    glow = np.asarray(small.resize((W, H), Image.BILINEAR), np.float32)
    out = np.asarray(img, np.float32) + glow * (0.85 if t < TR else 0.28)
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    titles(img, t)
    if t < TA + 0.5:
        counter(img, t, n)
    return img


if STILLS:
    for t in STILLS:
        draw_frame(int(t * FPS)).save(f"/tmp/still_{t:05.2f}.jpg", quality=90)
    print("кадры готовы")
    sys.exit()

# ---------- видео ----------
wr = fv.Writer(OUT, fps=FPS)
for i in range(NF):
    wr.add(draw_frame(i))
wr.close(None)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", OUT, "-i", "bear_music.m4a", "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", OUT + ".mux.mp4"], check=True)
import os
os.replace(OUT + ".mux.mp4", OUT)
print("длина", NF / FPS, "full", FULL, "TR", TR, "TA", TA)
