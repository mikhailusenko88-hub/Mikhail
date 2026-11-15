"""Can 1 ball fill the CAT? — рендер. python3 render.py out.mp4 [TOT] [только_кадры: t1,t2,...]"""
import colorsys
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fastvid as fv
import picture as PC
import shape as S

W, H, FPS = 1080, 1920, 30
R = 9.0
NT = 2000
OUT = sys.argv[1] if len(sys.argv) > 1 else "cat.mp4"
TOT = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
STILLS = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else None

# ---------- данные симуляции ----------
raw = np.fromfile("sim.bin", dtype=np.uint8)
frames, off = [], 0
while off < len(raw):
    n = int(np.frombuffer(raw[off:off + 4], np.int32)[0]); off += 4
    xy = np.frombuffer(raw[off:off + 8 * n], np.float32).reshape(n, 2).copy(); off += 8 * n
    frames.append(xy)
birth = np.zeros(NT + 10)
hits, spawns = [], []
for line in open("events.txt"):
    p = line.split()
    if p[0] == "S":
        birth[int(p[2])] = float(p[1]); spawns.append((float(p[1]), int(p[2])))
    elif p[0] == "H":
        hits.append(float(p[1]))
    elif p[0] == "F":
        FULL = float(p[1])
hits = np.array(hits)
TR = FULL + 0.75          # старт «пыка»
TA = TR + 1.05            # кот оживает
TEND = TA + 5.4
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
    cols[st] = np.clip(PC.sample(img, final[:, 0], final[:, 1]), 0, 255).astype(np.uint8)


def state_at(t):
    r = t - TA
    if 0.55 <= r < 0.74 or 3.15 <= r < 3.3 or 3.45 <= r < 3.6:
        return "closed"
    if 1.25 <= r < 2.05:
        return "left"
    if 2.05 <= r < 2.85:
        return "right"
    return "center"


# холодная палитра до «пыка»: по порядку рождения
pre = np.zeros((N, 3), np.uint8)
for i in range(N):
    k = math.log2(i + 1) / math.log2(NT)
    h = 0.52 + 0.30 * k + 0.04 * math.sin(i * 1.7)
    v = 0.92 + 0.08 * math.sin(i * 0.9)
    r, g, b = colorsys.hsv_to_rgb(h % 1, 0.62, v)
    pre[i] = (int(r * 255), int(g * 255), int(b * 255))

# ---------- спрайты ----------
_SP = {}


def sprite(col, rad):
    key = (tuple(int(c) for c in col), rad)
    s = _SP.get(key)
    if s is not None:
        return s
    ss = 4
    size = int(math.ceil(rad * 2 + 3))
    n = size * ss
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / ss - size / 2 + 0.5 / ss
    d = np.hypot(xx, yy) / rad
    a = np.clip((1 - d) * rad * 1.0 + 0.5, 0, 1)
    nz = np.sqrt(np.clip(1 - d * d, 0, 1))
    lam = np.clip(0.55 * nz + 0.45 * np.clip((-xx * 0.45 - yy * 0.6) / rad + 0.5, 0, 1), 0, 1)
    c = np.array(col, np.float32)[None, None, :] * (0.62 + 0.45 * lam[..., None])
    sx, sy = -0.35 * rad, -0.4 * rad
    spec = np.exp(-(((xx - sx) ** 2 + (yy - sy) ** 2) / (0.28 * rad) ** 2))
    c = c + 255 * 0.55 * spec[..., None]
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
    g = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([10, 12, 30], np.float32), np.array([24, 14, 48], np.float32)
    arr = (top + (bot - top) * g[..., None]) * np.ones((1, W, 1), np.float32)
    f = S.field()
    inside = f < 0
    # мягкое свечение вокруг силуэта
    halo = Image.fromarray((np.clip(1 - np.abs(f) / 60, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(28))
    halo = np.asarray(halo, np.float32)[..., None] / 255
    arr = arr + halo * np.array([40, 120, 170], np.float32) * 0.55
    arr[inside] = arr[inside] * 0.55 + np.array([6, 10, 22]) * 0.45
    line = np.clip(1 - (np.abs(f + 1.5) - 3.0), 0, 1)[..., None]
    arr = arr * (1 - line) + line * np.array([200, 245, 255], np.float32)
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
    if t < TA + 0.55:
        text_line(img, 92, [("Can 1 ball fill", WHT)], 86)
        text_line(img, 192, [("the CAT?", YEL), ("emoji", "🐱")], 112)
    elif t < TA + 3.75:
        text_line(img, 92, [("Wait...", WHT)], 86)
        text_line(img, 192, [("it BLINKED?!", PNK), ("emoji", "😳")], 104)
    else:
        text_line(img, 92, [("Which animal", WHT)], 86)
        text_line(img, 192, [("next?", YEL), ("emoji", "👇")], 112)


def counter(img, t, n):
    d = ImageDraw.Draw(img, "RGBA")
    full = t >= FULL
    pct = 100 if full else min(99, int(100 * n / NT))
    f = font(50)
    lab = f"{n:,} BALL" + ("" if n == 1 else "S")
    d.text((190, 318), lab, font=f, fill=WHT, stroke_width=6, stroke_fill=(0, 0, 0))
    ps = f"{pct}%"
    col = GRN if full else YEL
    d.text((890 - d.textlength(ps, font=f), 318), ps, font=f, fill=col, stroke_width=6, stroke_fill=(0, 0, 0))
    x0, x1, y0, y1 = 190, 890, 392, 418
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
        g, gs = glow_sprite((140, 235, 255), 74)
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
            rr = 10 * (1 - back / 9)
            al = int(200 * (1 - back / 7) * ga)
            for j in range(min(n, len(pv))):
                x, y = pv[j]
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(170, 240, 255, al))
        # кольцо на каждом делении
        for (bt, bj) in spawns[:64]:
            a = t + 1 / FPS - bt
            if 0 <= a < 0.3 and bj < len(xy):
                x, y = xy[bj]
                rr = 12 + 70 * a / 0.3
                d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(255, 255, 255, int(230 * (1 - a / 0.3))), width=5)
    if t < TR:
        for j in range(n):
            age = max(0.0, t + 1 / FPS - birth[j]) if j else 9
            if age < 0.2:
                c = np.clip(pre[j].astype(np.int32) + (255 - pre[j].astype(np.int32)) * (1 - age / 0.2), 0, 255).astype(np.uint8)
                sp, sz = sprite(c, 11 if age < 0.1 else 10)
            else:
                sp, sz = sprite(pre[j], 9)
            img.paste(sp, (int(round(xy[j, 0] - sz / 2)), int(round(xy[j, 1] - sz / 2))), sp)
    else:
        st = cols[state_at(t)]
        for j in range(n):
            dt_ = t - tw[j]
            if dt_ < 0:
                sp, sz = sprite(pre[j], 9)
            elif dt_ < 0.07:
                sp, sz = sprite((255, 255, 255), 12)
            else:
                rad = 10 if dt_ < 0.22 else 9.6
                sp, sz = sprite(st[j], rad)
            img.paste(sp, (int(round(xy[j, 0] - sz / 2)), int(round(xy[j, 1] - sz / 2))), sp)
    titles(img, t)
    if t < TA + 0.55:
        counter(img, t, n)
    return img


if STILLS:
    for t in STILLS:
        draw_frame(int(t * FPS)).save(f"/tmp/still_{t:05.2f}.jpg", quality=90)
    print("кадры готовы")
    sys.exit()

# ---------- звук ----------
au = fv.Audio(TEND + 1)
PENTA = [0, 2, 4, 7, 9]
sp_t = np.array([s[0] for s in spawns])
for fi in range(int(FULL * FPS) + 1):
    t0, t1 = fi / FPS, (fi + 1) / FPS
    idx = np.where((sp_t >= t0) & (sp_t < t1))[0]
    if not len(idx):
        continue
    nn = spawns[idx[-1]][1] + 1
    prog = math.log2(nn) / math.log2(NT)
    k = min(len(idx), 3)
    for q in range(k):
        step = int(prog * 14) + q * 2
        semi = PENTA[step % 5] + 12 * (step // 5)
        vol = 0.22 if nn < 40 else 0.11 / math.sqrt(k)
        au.put(au.tone(392 * 2 ** (semi / 12), 0.22, vol, decay=14), sp_t[idx[q]])
    if nn < 40:
        for q in idx[:2]:
            au.put(au.noise_burst(0.03, 0.12, decay=90, smooth=6), sp_t[q])
# шипение толпы шариков
hz, edges = np.histogram(hits[hits < FULL], bins=np.arange(0, FULL + 0.05, 0.05))
for b, c in enumerate(hz):
    if c > 30:
        au.put(au.noise_burst(0.06, min(0.05, 0.006 * math.log(c)), decay=30, smooth=12), b * 0.05)
# подъём к 100%
t0r = 4.0
tt = np.arange(int((FULL - t0r) * au.sr)) / au.sr
fr = 110 * 2 ** (2 * tt / (FULL - t0r))
ph = 2 * np.pi * np.cumsum(fr) / au.sr
env = (tt / (FULL - t0r)) ** 2 * 0.07
au.put(env * (np.sin(ph) + 0.5 * np.sin(1.5 * ph)), t0r)
# 100%
for semi in (0, 7, 12):
    au.put(au.tone(1046.5 * 2 ** (semi / 12), 1.2, 0.12, decay=3.5, h2=0.1), FULL)
# «пык» — волна вверх
for q in range(14):
    semi = PENTA[q % 5] + 12 * (q // 5)
    au.put(au.tone(523.25 * 2 ** (semi / 12), 0.5, 0.11, decay=7), TR + q * 0.045)
for semi in (0, 4, 7, 11, 14):
    au.put(au.tone(261.6 * 2 ** (semi / 12), 3.2, 0.07, decay=0.9, h2=0.1), TR + 0.1)
# моргания и взгляды


def blip(f0, f1, dur, vol):
    m = int(dur * au.sr)
    tt = np.arange(m) / au.sr
    fq = f0 + (f1 - f0) * tt / dur
    return vol * np.sin(2 * np.pi * np.cumsum(fq) / au.sr) * np.exp(-tt * 18) * np.minimum(1, tt * 400)


for r in (0.55, 3.15, 3.45):
    au.put(blip(1400, 800, 0.12, 0.25), TA + r)
au.put(blip(500, 700, 0.18, 0.18), TA + 1.25)
au.put(blip(700, 500, 0.18, 0.18), TA + 2.05)
for semi in (0, 4, 7, 12):
    au.put(au.tone(392 * 2 ** (semi / 12), 1.8, 0.07, decay=1.6), TA + 3.75)

# ---------- видео ----------
wr = fv.Writer(OUT, fps=FPS)
for i in range(NF):
    wr.add(draw_frame(i))
wr.close(au.a[:int((NF / FPS) * au.sr)])
print("длина", NF / FPS, "full", FULL, "TR", TR, "TA", TA)
