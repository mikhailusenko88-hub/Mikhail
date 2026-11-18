"""Ведро шариков: ~55 000 бусин сыплются из ведра, которое ездит над экраном; пока куча растёт, из неё проступает панда.
Два прохода одной и той же симуляции: 1) узнать, где каждый шарик остановится; 2) рисовать с цветом картинки.
python3 pour.py out.mp4 [TOT] [кадры t1,t2,...]"""
import colorsys
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fastvid as fv
import panda as PD

W, H, FPS = 1080, 1920, 30
CELL = 5
WC, HC = W // CELL, H // CELL                 # 216 × 384
STEPS = 11                                    # шагов песка на кадр (скорость падения ≈ 1650 px/с)
NT = 54000                                    # сколько шариков высыпать
LIP_Y = 96                                    # строка, где шарики выходят из ведра (≈480 px)
POUR_T = 12.0                                 # за сколько секунд высыпается ведро
SLIDE = 0.85
HOLD = 1.2                                    # потом куча замирает (кто ещё катится — останавливается)
OUT = sys.argv[1] if len(sys.argv) > 1 else "pour.mp4"
TOT = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
STILLS = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
SETTLE = 14                                   # шаг без движения → шарик «лёг» и показывает свой цвет


def lip_x(t):
    a = min(1.0, max(0.0, (t - 1.2) / 1.5))            # первые ~1,2 с ведро стоит в центре
    return 540 + 420 * a * math.sin(2 * math.pi * max(0.0, t - 1.2) / 4.0)


def simulate(record=None, on_frame=None, max_frames=None):
    """record: dict для финала; on_frame(i, grid, lastmove, step, info)"""
    rng = np.random.default_rng(42)
    g = -np.ones((HC, WC), np.int32)
    lastmove = np.zeros(NT + 10, np.int32)
    nid, step, f = 0, 0, 0
    quiet = 0
    while True:
        t = f / FPS
        spawned_this = 0
        for s in range(STEPS):
            # высыпать из ведра
            if nid < NT and t < POUR_T + 3:
                want = (NT - nid) / max(1, (POUR_T - t) * FPS * STEPS) if t < POUR_T else 30
                k = min(int(want) + (1 if rng.random() < want - int(want) else 0), 80)
                cx = int(lip_x(t + s / (FPS * STEPS)) / CELL)
                cols = cx + rng.integers(-18, 19, size=k * 3)
                rows = LIP_Y + rng.integers(0, 2, size=k * 3)
                for c, rw in zip(cols, rows):
                    if k <= 0 or nid >= NT:
                        break
                    if 0 <= c < WC and g[rw, c] < 0:
                        g[rw, c] = nid
                        lastmove[nid] = step
                        nid += 1
                        k -= 1
                        spawned_this += 1
            # вниз
            occ = g >= 0
            can = occ[:-1] & ~occ[1:]
            r, c = np.where(can)
            ids = g[r, c]
            g[r + 1, c] = ids
            g[r, c] = -1
            lastmove[ids] = step
            moved = len(ids)
            # по диагонали (сторона чередуется)
            occ = g >= 0
            d = 1 if step % 2 else -1
            blocked = occ[:-1] & occ[1:]
            te = np.zeros_like(blocked)
            se = np.zeros_like(blocked)
            if d > 0:
                te[:, :-1] = ~occ[1:, 1:]
                se[:, :-1] = ~occ[:-1, 1:]
            else:
                te[:, 1:] = ~occ[1:, :-1]
                se[:, 1:] = ~occ[:-1, :-1]
            mv = blocked & te & se
            r, c = np.where(mv)
            ids = g[r, c]
            g[r + 1, c + d] = ids
            g[r, c] = -1
            lastmove[ids] = step
            moved += len(ids)
            # растекание вбок по поверхности (как у жидкости, с вероятностью) — верх кучи ровнее
            occ = g >= 0
            sup = np.zeros_like(occ); sup[:-1] = occ[1:]; sup[-1] = True          # есть опора снизу
            side = np.zeros_like(occ)
            if d > 0:
                side[:, :-1] = ~occ[:, 1:]
            else:
                side[:, 1:] = ~occ[:, :-1]
            above_free = np.ones_like(occ); above_free[1:] = ~occ[:-1]              # только верхний слой
            sl = occ & sup & side & above_free & (rng.random(occ.shape) < SLIDE)
            r, c = np.where(sl)
            ids = g[r, c]
            g[r, c + d] = ids
            g[r, c] = -1
            lastmove[ids] = step
            moved += len(ids)
            step += 1
        info = {"t": t, "n": nid, "moved": moved, "spawned": spawned_this}
        if on_frame:
            on_frame(f, g, lastmove, step, info)
        f += 1
        quiet = quiet + 1 if (moved == 0 and (nid >= NT or t > POUR_T + 3)) else 0
        if (quiet > 10) or (max_frames and f >= max_frames) or t >= POUR_T + HOLD:
            break
    if record is not None:
        r, c = np.where(g >= 0)
        record["r"], record["c"], record["ids"], record["frames"], record["n"] = r, c, g[r, c], f, nid
    return f


# ---------- проход 1: где кто ляжет
rec = {}
NFS = simulate(record=rec)
print("проход 1: кадров", NFS, "шариков", rec["n"])
POUR_END = NFS / FPS                           # всё легло
TR = POUR_END + 0.15                           # картинка готова
TA = TR + 0.8
TEND = TA + 4.2
if TOT:
    TEND = min(TEND, TOT)
NF = int(TEND * FPS)

# цвета: «радуга» в полёте и цвет картинки, когда лёг
ys = rec["r"] * CELL + CELL // 2
xs = rec["c"] * CELL + CELL // 2
TRUE = {}
for st in ("center", "left", "right", "closed"):
    img = PD.make(st).astype(np.float32)
    col = np.zeros((NT + 10, 3), np.float32)
    col[rec["ids"]] = np.clip(img[ys, xs] * 1.15, 0, 255)          # бусины затемняют края — чуть светлее, чтобы белое было белым
    TRUE[st] = col
rng = np.random.default_rng(5)
RAIN = np.array([colorsys.hsv_to_rgb(h, 0.85, 1.0) for h in rng.random(NT + 10)], np.float32) * 255
BG_TOP, BG_BOT = np.array([8, 10, 26], np.float32), np.array([20, 12, 40], np.float32)
BG = (BG_TOP + (BG_BOT - BG_TOP) * np.linspace(0, 1, HC)[:, None, None]) * np.ones((1, WC, 1), np.float32)

# бусина 5×5: светлая середина, тёмные уголки
yy, xx = np.mgrid[0:CELL, 0:CELL] + 0.5 - CELL / 2
dd = np.hypot(xx, yy) / (CELL / 2)
BEAD = np.clip(1.25 - 0.55 * dd ** 2, 0.25, 1.25)
BEAD[dd > 1.05] = 0.28
BEAD_T = np.tile(BEAD, (HC, WC))[..., None].astype(np.float32)


def state_at(t):
    r = t - TA
    if 0.5 <= r < 0.68 or 2.5 <= r < 2.63 or 2.75 <= r < 2.88:
        return "closed"
    if 1.0 <= r < 1.6:
        return "left"
    if 1.6 <= r < 2.2:
        return "right"
    return "center"


# ---------- ведро
def make_bucket():
    s = 2
    im = Image.new("RGBA", (300 * s, 260 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    body = [(40 * s, 40 * s), (260 * s, 40 * s), (230 * s, 230 * s), (70 * s, 230 * s)]
    d.polygon(body, fill=(70, 150, 235, 255))
    d.polygon([(40 * s, 40 * s), (110 * s, 40 * s), (100 * s, 230 * s), (70 * s, 230 * s)], fill=(120, 190, 255, 255))   # блик
    d.rounded_rectangle([30 * s, 26 * s, 270 * s, 52 * s], radius=10 * s, fill=(40, 110, 200, 255))
    d.arc([60 * s, -60 * s, 240 * s, 120 * s], 200, 340, fill=(200, 210, 230, 255), width=7 * s)                 # ручка
    for k in range(9):                                                                                        # шарики в ведре
        x = 60 + k * 22
        d.ellipse([x * s, 18 * s, (x + 20) * s, 38 * s], fill=tuple(int(v) for v in RAIN[k * 7]) + (255,))
    return im.resize((300, 260), Image.LANCZOS)


BUCKET = make_bucket()

# ---------- текст
FB = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FE = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
_F, _EM = {}, {}


def font(sz):
    if sz not in _F:
        _F[sz] = ImageFont.truetype(FB, sz)
    return _F[sz]


def emoji(ch, size):
    if (ch, size) not in _EM:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((8, 8), ch, font=ImageFont.truetype(FE, 109), embedded_color=True)
        im = im.crop(im.getbbox())
        k = size / im.size[1]
        _EM[(ch, size)] = im.resize((int(im.size[0] * k), size), Image.LANCZOS)
    return _EM[(ch, size)]


def text_line(img, y, parts, size, stroke=8):
    d = ImageDraw.Draw(img)
    f = font(size)
    ws = [emoji(p[1], size).size[0] + 14 if p[0] == "emoji" else d.textlength(p[0], font=f) for p in parts]
    x = (W - sum(ws)) / 2
    for p, w in zip(parts, ws):
        if p[0] == "emoji":
            e = emoji(p[1], size)
            img.paste(e, (int(x + 10), int(y + size * 0.08)), e)
        else:
            d.text((x, y), p[0], font=f, fill=p[1], stroke_width=stroke, stroke_fill=(0, 0, 0))
        x += w


YEL, WHT, PNK, GRN = (255, 214, 64), (255, 255, 255), (255, 120, 190), (120, 255, 140)


def overlay(img, t, n):
    if t < TR:
        text_line(img, 120, [("1 bucket = 54,000 balls", WHT)], 64)
        text_line(img, 204, [("What will they draw?", YEL), ("emoji", "🤔")], 80)
    elif t < TA + 0.5:
        text_line(img, 150, [("It's a PANDA!", GRN), ("emoji", "🐼")], 100)
    elif t < TA + 3.0:
        text_line(img, 120, [("Wait...", WHT)], 72)
        text_line(img, 204, [("it BLINKED?!", PNK), ("emoji", "😳")], 96)
    else:
        text_line(img, 120, [("Which animal", WHT)], 72)
        text_line(img, 204, [("next?", YEL), ("emoji", "👇")], 104)
    if t < TA + 0.5:
        d = ImageDraw.Draw(img)
        s = f"{n:,} BALLS"
        f = font(56)
        d.text(((W - d.textlength(s, font=f)) / 2, 312), s, font=f, fill=GRN if t >= TR else WHT, stroke_width=6, stroke_fill=(0, 0, 0))


# ---------- проход 2: рисуем
wr = None if STILLS else fv.Writer(OUT, fps=FPS)
want = set(int(s * FPS) for s in STILLS) if STILLS else None
stats = []
last = {}


CXW, CYW = PD.CX, PD.CY2
dist = np.full(NT + 10, 9e9, np.float32)
dist[rec["ids"]] = np.hypot(xs - CXW, ys - CYW)
TW = TR + dist / 1300.0                         # волна «пыка» от центра мордочки
_BEAD = {}


def bead(sz):
    if sz not in _BEAD:
        yy, xx = np.mgrid[0:sz, 0:sz] + 0.5 - sz / 2
        dd = np.hypot(xx + 0.18 * sz, yy + 0.22 * sz) / (sz / 2)          # блик сверху-слева
        r = np.hypot(xx, yy) / (sz / 2)
        sh = np.clip(1.15 - 0.55 * r ** 2, 0.35, 1.15) + 0.55 * np.exp(-(dd / 0.45) ** 2)
        alpha = np.clip((1.0 - r) * sz * 0.5 + 0.5, 0, 1)
        _BEAD[sz] = (sh.astype(np.float32), alpha.astype(np.float32))
    return _BEAD[sz]


Z0 = 2.4


def zoom_at(t):
    if t < 1.0:
        return Z0
    k = min(1.0, (t - 1.0) / 5.0)
    k = k * k * (3 - 2 * k)
    return Z0 + (1.0 - Z0) * k


def frame_img(t, g, lastmove, step, n):
    z = zoom_at(t)
    st = state_at(t)
    occ = g >= 0
    ids = np.where(occ, g, 0)
    col = BG.copy()
    if t < TR:
        col[occ] = RAIN[ids[occ]]
    else:
        tw = TW[ids]
        pre = occ & (t < tw)
        fl = occ & (t >= tw) & (t < tw + 0.07)
        tru = occ & (t >= tw + 0.07)
        col[pre] = RAIN[ids[pre]]
        col[fl] = 255
        col[tru] = TRUE[st][ids[tru]]
    # окно камеры в клетках: сначала крупно у ведра, потом весь экран
    wc, hc = WC / z, HC / z
    fx = lip_x(t) / CELL if t < 1.0 else WC / 2
    cxw = fx + (WC / 2 - fx) * min(1.0, max(0.0, (t - 1.0) / 5.0))
    y0c = max(0.0, LIP_Y - 640 / (CELL * z)) * ((z - 1) / (Z0 - 1))   # крупно: край ведра на ~640 px от верха
    cyw = y0c + hc / 2
    x0 = int(np.clip(cxw - wc / 2, 0, WC - wc)); y0 = int(np.clip(cyw - hc / 2, 0, HC - hc))
    x1 = min(WC, x0 + int(math.ceil(wc)) + 1); y1 = min(HC, y0 + int(math.ceil(hc)) + 1)
    sz = max(CELL, int(round(CELL * z)))
    sub = col[y0:y1, x0:x1]
    so = occ[y0:y1, x0:x1]
    sh, al = bead(sz)
    big = np.repeat(np.repeat(sub, sz, 0), sz, 1)
    bgb = np.repeat(np.repeat(BG[y0:y1, x0:x1], sz, 0), sz, 1)
    shT = np.tile(sh, so.shape)[..., None]
    alT = np.tile(al, so.shape)[..., None] * np.repeat(np.repeat(so, sz, 0), sz, 1)[..., None]
    out = bgb * (1 - alT) + big * shT * alT
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    # ведро в координатах окна
    if t < POUR_END + 1.0:
        up = max(0.0, t - POUR_T) * 420
        scale = sz / CELL
        b = BUCKET.rotate(-115, resample=Image.BICUBIC, expand=True)
        b = b.resize((max(1, int(b.size[0] * scale)), max(1, int(b.size[1] * scale))), Image.BILINEAR)
        lx, ly = lip_x(t) - 70, LIP_Y * CELL + 70 - up
        px = (lx / CELL - x0) * sz - (40 + 150) * scale
        py = (ly / CELL - y0) * sz - b.size[1]
        img.paste(b, (int(px), int(py)), b)
    # обрезать до точного окна и привести к 1080×1920
    ox, oy = (cxw - wc / 2 - x0) * sz, (cyw - hc / 2 - y0) * sz
    ox, oy = max(0, ox), max(0, oy)
    img = img.crop((int(ox), int(oy), int(ox + wc * sz), int(oy + hc * sz))).resize((W, H), Image.BILINEAR)
    overlay(img, t, n)
    return img


def on_frame(i, g, lastmove, step, info):
    t = i / FPS
    stats.append((t, info["moved"], info["spawned"], info["n"]))
    last["g"], last["lm"], last["step"], last["n"] = g.copy(), lastmove.copy(), step, info["n"]
    if i >= NF:
        return
    if want is not None:
        if i in want:
            frame_img(t, g, lastmove, step, info["n"]).save(f"/tmp/pour_{t:05.2f}.jpg", quality=88)
        return
    wr.add(frame_img(t, g, lastmove, step, info["n"]))


simulate(on_frame=on_frame)
# после конца симуляции — неподвижная куча до конца ролика
i = len(stats)
while i < NF:
    t = i / FPS
    if want is not None:
        if i in want:
            frame_img(t, last["g"], last["lm"], last["step"] + 999, last["n"]).save(f"/tmp/pour_{t:05.2f}.jpg", quality=88)
    else:
        wr.add(frame_img(t, last["g"], last["lm"], last["step"] + 999, last["n"]))
    i += 1
np.save("pour_stats.npy", np.array(stats))
print("POUR_END", round(POUR_END, 2), "TR", round(TR, 2), "TA", round(TA, 2), "TEND", round(TEND, 2))
if wr:
    wr.close(None)
