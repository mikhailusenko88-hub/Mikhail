"""«1000 шарик: қай қала жеңеді?» — пробный ролик для «Білесің бе?» (15.11.2026).
1000 шариков десяти городов сыплются из воронки через штырьки и вертушки; чей город больше закатит в кубок — победил.
    python3 mass_video.py out.mp4 [seed]
"""
import math
import random
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import layout as L
import sim_run

BASE = Path(__file__).resolve().parent
KZ = BASE.parent
W, H, FPS = 1080, 1920, 30
PALETTE = [(240, 60, 60), (40, 190, 255), (255, 150, 30), (165, 95, 255), (60, 200, 90),
           (255, 225, 40), (255, 95, 185), (245, 245, 245), (170, 240, 60), (60, 100, 255)]
DEFAULT = [("Алматы", "Алматы"), ("Астана", "Астана"), ("Шымкент", "Шымкент"), ("Қарағанды", "Караганда"),
           ("Ақтөбе", "Актобе"), ("Тараз", "Тараз"), ("Павлодар", "Павлодар"), ("Өскемен", "Усть-Каменогорск"),
           ("Семей", "Семей"), ("Атырау", "Атырау")]
CITIES = [(k, r, c) for (k, r), c in zip(DEFAULT, PALETTE)]
BG0, BG1, GOLD = (6, 16, 38), (10, 44, 76), (255, 200, 40)
_F = {}


def font(sz):
    if sz not in _F:
        for f in (KZ / "fonts" / "DejaVuSans-Bold.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
            if f.exists():
                _F[sz] = ImageFont.truetype(str(f), sz)
                break
    return _F[sz]


def ctext(d, cx, y, s, sz, fill, stroke=5):
    f = font(sz)
    while d.textlength(s, font=f) > W - 60 and sz > 20:
        sz -= 2
        f = font(sz)
    d.text((cx - d.textlength(s, font=f) / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))


def ball_sprite(col, r):
    s = int(r * 2 + 4)
    big = 4
    im = Image.new("RGBA", (s * big, s * big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s * big / 2
    rr = r * big
    d.ellipse([c - rr, c - rr, c + rr, c + rr], fill=tuple(int(v * 0.55) for v in col) + (255,))
    rr2 = rr * 0.86
    d.ellipse([c - rr2 - rr * 0.08, c - rr2 - rr * 0.1, c + rr2 - rr * 0.08, c + rr2 - rr * 0.1], fill=col + (255,))
    h = rr * 0.32
    d.ellipse([c - rr * 0.45 - h, c - rr * 0.5 - h, c - rr * 0.45 + h, c - rr * 0.5 + h], fill=(255, 255, 255, 190))
    return im.resize((s, s), Image.LANCZOS)


def static_layer(sc):
    NEON = sc.neon
    g = np.linspace(0, 1, H)[:, None, None]
    arr = np.array(BG0, np.float32) + (np.array(BG1, np.float32) - np.array(BG0, np.float32)) * g
    img = Image.fromarray(np.repeat(arr, W, 1).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    for x1, y1, x2, y2 in sc.segs():
        dg.line([x1, y1, x2, y2], fill=NEON + (255,), width=14)
    x0, x1, yt, yb = sc.cup
    dg.rectangle([x0 - 8, yt - 8, x1 + 8, yb + 8], outline=GOLD + (255,), width=16)
    for x, y, r in sc.pegs():
        dg.ellipse([x - r - 6, y - r - 6, x + r + 6, y + r + 6], fill=NEON + (200,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(9)))
    d = ImageDraw.Draw(img)
    for xa, ya, xb, yb2 in sc.segs():
        d.line([xa, ya, xb, yb2], fill=tuple(min(255, int(v * 0.4 + 160)) for v in NEON), width=5)
    tint = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(tint).rectangle([x0 + 3, yt + 4, x1 - 3, yb - 3], fill=(255, 200, 40, 34))
    img = Image.alpha_composite(img, tint)
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 2, yt, x1 + 2, yb + 3], outline=GOLD, width=6)
    lite = tuple(min(255, int(v * 0.4 + 160)) for v in NEON)
    for x, y, r in sc.pegs():
        d.ellipse([x - r, y - r, x + r, y + r], fill=lite)
    ctext(d, (x0 + x1) / 2, yb + 14, "КУБОК", 34, GOLD, 4)
    ctext(d, W / 2, 14, "1000 ШАРИК · ҚАЙ ҚАЛА ЖЕҢЕДІ?", 50, (255, 255, 255), 6)
    ctext(d, W / 2, 74, "1000 ШАРИКОВ · КАКОЙ ГОРОД ПОБЕДИТ?", 36, GOLD, 5)
    return img


def chips(d, counts, leader):
    order = sorted(range(len(CITIES)), key=lambda i: (-counts[i], i))
    for k, i in enumerate(order):
        col, row = k % 5, k // 5
        x = 22 + col * 208
        y = 128 + row * 66
        kk, _, c = CITIES[i]
        d.rounded_rectangle([x, y, x + 200, y + 58], 14, fill=(0, 0, 0, 150),
                            outline=GOLD if (i == leader and counts[i] > 0) else c, width=4 if i == leader else 2)
        d.ellipse([x + 8, y + 17, x + 32, y + 41], fill=c)
        sz = 22
        while d.textlength(kk, font=font(sz)) > 156 and sz > 15:
            sz -= 1
        d.text((x + 38, y + 4), kk, font=font(sz), fill=(255, 255, 255))
        d.text((x + 38, y + 28), str(counts[i]), font=font(26), fill=GOLD if i == leader else (230, 230, 230))


def render(out, seed=1, n=1000, cities=None, no=None, log=print):
    """cities — список (kk, ru) из 10 городов (цвета по PALETTE). Подбирает вариант трассы, где всё досыпается за 16–27 с."""
    global CITIES
    CITIES = [(k, r, c) for (k, r), c in zip(cities or DEFAULT, PALETTE)]
    for tr in range(8):
        s2 = seed + tr * 7919
        rnd = random.Random(s2)
        sc = L.Scene(rnd)
        colors = [i % len(CITIES) for i in range(n)]
        rnd.shuffle(colors)
        colors = np.array(colors)
        pos, hits = sim_run.run(sc, n=n, T=30.0, seed=s2)
        x0, x1, yt, yb = sc.cup
        al = pos[:, :, 0] > -500
        incup = al & (pos[:, :, 0] > x0) & (pos[:, :, 0] < x1) & (pos[:, :, 1] > yt - 4) & (pos[:, :, 1] < yb)
        cnt_t = incup.sum(1)
        hop_t = (al & (pos[:, :, 1] < 690)).sum(1)
        end = None
        for f in range(60, len(pos)):
            if hop_t[f] <= 30 and cnt_t[f] == cnt_t[f - 60]:
                end = f
                break
        if end is None or not (16 * FPS <= end <= 27 * FPS) or cnt_t[end] < 150:
            log(f"трасса {tr}: не подошла (конец {None if end is None else round(end / FPS, 1)} с, в кубке {cnt_t[-1]})")
            continue
        fin = sorted(((colors == i) & incup[min(len(pos) - 1, end + 15)]).sum() for i in range(len(CITIES)))
        if fin[-1] == fin[-2]:
            log(f"трасса {tr}: ничья за первое место — другая")
            continue
        break
    else:
        raise RuntimeError("не нашлась трасса для «1000 шарик»")
    end = min(len(pos) - 1, end + 15)
    final = [int(((colors == i) & incup[end]).sum()) for i in range(len(CITIES))]
    win = int(np.argmax(final))
    CARD = 4.5
    total_f = end + 1 + int(CARD * FPS)
    log(f"«1000 шарик»: действие {end / FPS:.1f} с, ролик {total_f / FPS:.1f} с; в кубке {sum(final)}; победа {CITIES[win][0]} {final[win]}")

    base = static_layer(sc)
    sprites = [ball_sprite(c, L.R) for _, _, c in CITIES]
    so = int(L.R + 2)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", str(out) + ".v.mp4"], stdin=subprocess.PIPE)
    spin = sc.spinners()
    for f in range(total_f):
        fi = min(f, end)
        img = base.copy()
        d = ImageDraw.Draw(img)
        t = fi / FPS
        for cx, cy, ln, w, a0 in spin:
            a = a0 + w * t
            dx, dy = math.cos(a) * ln / 2, math.sin(a) * ln / 2
            d.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=(255, 120, 200), width=12)
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=(255, 255, 255))
        p = pos[fi]
        for i in np.nonzero(al[fi])[0]:
            img.alpha_composite(sprites[colors[i]], (int(p[i, 0]) - so, int(p[i, 1]) - so))
        counts = [int(((colors == k) & incup[fi]).sum()) for k in range(len(CITIES))]
        leader = int(np.argmax(counts))
        d = ImageDraw.Draw(img)
        chips(d, counts, leader)
        if f > end:
            k = min(1.0, (f - end) / 12)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(165 * k)))
            img = Image.alpha_composite(img, ov)
            d = ImageDraw.Draw(img)
            kk, ru, c = CITIES[win]
            ctext(d, W / 2, 520, "ЖЕҢІМПАЗ · ПОБЕДИТЕЛЬ", 52, GOLD, 6)
            d.ellipse([W / 2 - 70, 610, W / 2 + 70, 750], fill=c, outline=(255, 255, 255), width=6)
            ctext(d, W / 2, 770, kk.upper(), 96, (255, 255, 255), 8)
            ctext(d, W / 2, 890, f"Кубокта {final[win]} шарик · в кубке {final[win]}", 40, GOLD, 5)
            top = sorted(range(len(CITIES)), key=lambda i: -final[i])[:5]
            for j, i in enumerate(top):
                yy = 990 + j * 62
                d.ellipse([300, yy + 6, 340, yy + 46], fill=CITIES[i][2])
                d.text((360, yy), f"{j + 1}. {CITIES[i][0]}", font=font(42), fill=(255, 255, 255), stroke_width=4,
                       stroke_fill=(0, 0, 0))
                d.text((700, yy), str(final[i]), font=font(42), fill=GOLD, stroke_width=4, stroke_fill=(0, 0, 0))
            ctext(d, W / 2, 1330, "Сен қай қалаға жанкүйерсің?", 46, (255, 255, 255), 5)
            ctext(d, W / 2, 1392, "А ты за какой город болеешь? Пиши!", 38, GOLD, 5)
        ff.stdin.write(img.convert("RGB").tobytes())
        if f % 150 == 0:
            log(f"кадр {f} / {total_f}")
    ff.stdin.close()
    ff.wait()
    # звук: музыка + «дождь» стуков по штырькам
    sr = 44100
    dur = total_f / FPS
    snd = np.zeros(int(dur * sr) + sr, np.float32)
    rg = np.random.default_rng(seed)
    click_len = int(0.012 * sr)
    tt = np.arange(click_len) / sr
    for f in range(min(end, len(hits))):
        k = min(int(hits[f]), 8)
        for _ in range(k):
            s0 = int((f + rg.random()) / FPS * sr)
            fr = rg.uniform(1800, 4200)
            snd[s0:s0 + click_len] += (np.sin(2 * np.pi * fr * tt) * np.exp(-tt * 380) * 0.10).astype(np.float32)
    s_end = int(end / FPS * sr)                          # фанфара победы: аккорд
    for fr in (523.3, 659.3, 784.0, 1046.5):
        tt2 = np.arange(int(1.6 * sr)) / sr
        snd[s_end:s_end + len(tt2)] += (np.sin(2 * np.pi * fr * tt2) * np.exp(-tt2 * 1.8) * 0.12).astype(np.float32)
    snd = np.clip(snd, -1, 1)
    wav = str(out) + ".sfx.wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((snd * 32000).astype(np.int16).tobytes())
    music = sorted((KZ / "music").glob("*.mp3"))
    mus = music[seed % len(music)] if music else None
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out) + ".v.mp4", "-i", wav]
    if mus:
        cmd += ["-i", str(mus), "-filter_complex",
                f"[2:a]volume=0.32,atrim=0:{dur:.2f},afade=t=out:st={dur - 1.5:.2f}:d=1.5[m];[1:a][m]amix=inputs=2:normalize=0,volume=2.2,alimiter=limit=0.95[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    Path(str(out) + ".v.mp4").unlink()
    Path(wav).unlink()
    order = sorted(range(len(CITIES)), key=lambda i: -final[i])
    return {"winner": CITIES[win][0], "ranking": [CITIES[i][0] for i in order],
            "counts": dict(zip([c[0] for c in CITIES], final)), "duration": dur, "in_cup": sum(final)}


if __name__ == "__main__":
    print(render(sys.argv[1] if len(sys.argv) > 1 else "mass.mp4", int(sys.argv[2]) if len(sys.argv) > 2 else 1))
