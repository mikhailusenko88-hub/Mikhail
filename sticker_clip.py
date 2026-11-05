"""Короткие ролики под наклейку «Вопросы» (Q&A): Михаил выкладывает их с телефона и вешает наклейку.
    python sticker_clip.py cities out.mp4
    python sticker_clip.py cars out.mp4
Середина экрана (y 1130–1480) оставлена пустой — туда ставится наклейка."""
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import race_leagues as RL
import race_video as rv

W, H, FPS, DUR = 1080, 1920, 30, 12.0
BASE = Path(__file__).resolve().parent
TOP, BOT, WALL, ACC = rv.THEMES[0]


def bg():
    y = np.linspace(0, 1, H)[:, None]
    col = (np.array(TOP)[None] * (1 - y) + np.array(BOT)[None] * y).astype(np.uint8)
    im = Image.fromarray(np.repeat(col[:, None, :], W, axis=1).reshape(H, W, 3))
    d = ImageDraw.Draw(im)
    rnd = random.Random(3)
    for _ in range(140):
        x, yy = rnd.randrange(W), rnd.randrange(H)
        d.ellipse([x - 2, yy - 2, x + 2, yy + 2], fill=(60, 90, 130))
    return im.convert("RGBA")


def two_lines(d, y, a, b, size, col_a, col_b=(255, 255, 255)):
    sz = rv.pair_size([a, b], size, W - 140)
    rv.text_c(d, W / 2, y, a, sz, col_a, 8)
    rv.text_c(d, W / 2, y + sz + 10, b, sz, col_b, 8)
    return y + 2 * sz + 10


def make(kind, out):
    league = "cities" if kind == "cities" else "cars"
    rv.set_league(league)
    base = bg()
    frames_dir = None
    balls = [rv.ball_sprite(c, e["num"]) for c, e in zip(rv.COLORS, rv.ENT)]
    if league == "cities":
        mp, pts = rv.uz_map(470, -1, ACC)
        h1 = ("SHAHRING YOʻQMI?", "НЕТ ТВОЕГО ГОРОДА?")
        h2 = ("Yoz — keyingi poygaga qoʻshamiz!", "Напиши — добавим в следующую гонку!")
    else:
        cars = [rv.car_img(e["body"], rv.COLORS[i], 300) for i, e in enumerate(rv.ENT)]
        h1 = ("MASHINANG YOʻQMI?", "НЕТ ТВОЕЙ МАШИНЫ?")
        h2 = ("Yoz — keyingi poygaga qoʻshamiz!", "Напиши — добавим в следующую гонку!")
    hand = Image.new("RGBA", (420, 50), (0, 0, 0, 0))
    ImageDraw.Draw(hand).text((0, 0), "@kimyutadi_uz", font=rv.font(28), fill=(255, 255, 255, 170))
    rnd = random.Random(11)
    falling = [[rnd.uniform(40, W - 40), rnd.uniform(-1900, 0), rnd.uniform(380, 700), rnd.randrange(len(balls))]
               for _ in range(16)]
    n = int(DUR * FPS)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-b:v", "6000k",
                             "-pix_fmt", "yuv420p", "/tmp/sticker_v.mp4"], stdin=subprocess.PIPE)
    for fi in range(n):
        t = fi / FPS
        img = base.copy()
        # падающие шарики по краям (за надписями)
        for b in falling:
            y = b[1] + b[2] * t
            y = (y + 400) % (H + 400) - 200
            x = b[0]
            if 260 < x < W - 260 and 380 < y < 1560:
                continue
            img.alpha_composite(balls[b[3]], (int(x - 21), int(y - 21)))
        d = ImageDraw.Draw(img)
        k = min(1.0, t / 0.5)
        y = two_lines(d, 210, h1[0], h1[1], int(64 + 8 * k), ACC)
        if league == "cities":
            a = min(1.0, max(0.0, (t - 0.3) / 0.5))
            m2 = mp.copy()
            if a < 1:
                m2.putalpha(m2.getchannel("A").point(lambda v: int(v * a)))
            mx, my = (W - mp.size[0]) // 2, 430
            img.alpha_composite(m2, (mx, my))
            # точки городов загораются по очереди, «?» пульсирует там, где города нет
            for i, (px, py) in pts.items():
                if t > 0.8 + i * 0.12:
                    d.ellipse([mx + px - 9, my + py - 9, mx + px + 9, my + py + 9], fill=rv.COLORS[i] + (255,),
                              outline=(255, 255, 255, 255), width=3)
            pulse = 1 + 0.15 * math.sin(t * 5)
            q = rv.num_ball(ACC, "?", int(46 * pulse))
            img.alpha_composite(q, (int(mx + mp.size[0] * 0.30 - q.size[0] / 2), int(my + mp.size[1] * 0.55 - q.size[1] / 2)))
        else:
            # машины едут по двум рядам навстречу
            for row in range(2):
                yy = 470 + row * 170
                sp = 260 if row == 0 else -260
                for j in range(8):
                    i = (j * 2 + row) % len(cars)
                    x = (j * 330 + sp * t) % (8 * 330) - 330
                    c = cars[i] if sp > 0 else cars[i].transpose(Image.FLIP_LEFT_RIGHT)
                    img.alpha_composite(c, (int(x), yy))
            q = rv.num_ball(ACC, "?", int(52 * (1 + 0.15 * math.sin(t * 5))))
            img.alpha_composite(q, (int(W / 2 - q.size[0] / 2), 830))
        d = ImageDraw.Draw(img)
        a2 = min(1.0, max(0.0, (t - 1.2) / 0.5))
        if a2 > 0:
            lay = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            sz = rv.pair_size(list(h2), 44, W - 160)
            ld.rounded_rectangle([60, 0, W - 60, 2 * sz + 50], radius=30, fill=(0, 0, 0, 170), outline=ACC + (255,),
                                 width=4)
            rv.text_c(ld, W / 2, 16, h2[0], sz, ACC, 5)
            rv.text_c(ld, W / 2, 26 + sz, h2[1], sz, (255, 255, 255), 5)
            if a2 < 1:
                lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a2)))
            img.alpha_composite(lay, (0, 960))
        # стрелка вниз — к наклейке
        if t > 2.0:
            ay = 1100 + 14 * math.sin(t * 6)
            d.polygon([(W / 2 - 34, ay), (W / 2 + 34, ay), (W / 2, ay + 36)], fill=ACC + (255,))
        img.alpha_composite(hand, (150, 1560))
        proc.stdin.write(np.asarray(img.convert("RGB"), np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    music = BASE / "music" / "04_Toy_pozitiv.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/sticker_v.mp4", "-i", str(music),
                    "-filter_complex", f"[1:a]volume=0.5,afade=t=in:d=0.5,afade=t=out:st={DUR - 1.5}:d=1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", str(DUR),
                    "-movflags", "+faststart", out], check=True)


if __name__ == "__main__":
    make(sys.argv[1], sys.argv[2])
