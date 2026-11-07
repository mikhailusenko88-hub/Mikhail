"""Shorts 1080×1920 из заезда: финальный этап (последние ~22 с) + вылет, вырезан из горизонтального ролика
(кадр камеры 1440 px — берём центр 9:16), сверху «USA vs Brazil — WHO SURVIVES?», снизу «full race on channel».
python3 shorts.py part.mp4 part.json out.mp4"""
import json
import subprocess
import sys

from PIL import Image, ImageDraw

import countries
import popular
import race
from render import font, text_center

W, H = 1080, 1920
VIEW_W = 1440
SRC_H = 1080
CROP_W = 608            # 608/1080 ≈ 9/16 → scale ×1.777 = 1080×1920
TAIL = 22.0             # секунд финального этапа до финиша
GOLD = (255, 214, 64)
GREEN = (70, 235, 130)
WHITE = (255, 255, 255)


def overlay(codes, survive, n, out_png):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 300], fill=(0, 0, 0, 120))
    d.rectangle([0, H - 220, W, H], fill=(0, 0, 0, 120))
    vs = race.vs_line(codes, 2)
    f = 72
    while d.textlength(vs, font=font(f)) > W - 80 and f > 36:
        f -= 4
    text_center(d, W / 2, 60, vs, font(f), WHITE, 6)
    text_center(d, W / 2, 60 + f + 30, "WHO SURVIVES?", font(78), GOLD, 6)
    text_center(d, W / 2, H - 200, f"ONLY {survive} OF {n} SURVIVE", font(54), GREEN, 5)
    text_center(d, W / 2, H - 120, "FLAGBALL ARENA · full race on the channel", font(34), WHITE, 4)
    img.save(out_png)


def make(part_mp4, part_json, out_mp4):
    meta = json.load(open(part_json))
    spans = meta.get("spans") or []
    if not spans:
        raise SystemExit("в meta нет spans — race.py старый")
    s0, s1, s2 = spans[-1]                     # финальный этап: старт гонки, финиш, конец «вылетевших»
    total = meta.get("duration", s2)
    s1, s2 = min(s1, total), min(s2, total)
    start = max(s0, s1 - TAIL)
    dur = s2 - start
    if dur < 8:
        raise SystemExit("слишком короткий кусок для Shorts")
    ov = out_mp4 + ".png"
    overlay(meta["codes"], meta["survive"], meta["n"], ov)
    x0 = int(VIEW_W / 2 - CROP_W / 2)
    filt = (f"[0:v]crop={CROP_W}:{SRC_H}:{x0}:0,scale={W}:{H}:flags=lanczos,setsar=1[v0];"
            f"[1:v]format=rgba[ov];[v0][ov]overlay=0:0,fade=t=out:st={dur - 0.5:.2f}:d=0.5[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", part_mp4,
                    "-loop", "1", "-i", ov, "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "veryfast", "-b:v", "6000k", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_mp4], check=True)
    vs = race.vs_line(meta["codes"], 3)
    title = f"{vs} 😱 Who Survives? Country Marble Race #shorts"[:100]
    return {"title": title, "duration": dur, "vs": vs}


def description(meta, full_link):
    names = ", ".join(sorted(race.NAMES[c] for c in meta["codes"]))
    return (f"{meta['n']} countries, only {meta['survive']} survive.\n"
            f"▶ Full race on @FlagballArenaTV — {full_link}\n\n"
            f"Countries: {names}.\n\nLike 👍 if your country survived! Comment who you're cheering for.\n\n"
            f"#shorts #marblerace #countryballs #marblerun #survival #countries")


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2], sys.argv[3]))
