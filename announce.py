"""Анонс гранд-финала (H13, «да» Михаила 23.11.2026): 28, 29 и 30.11 в 11:00 МСК — отдельный Shorts,
сезон не двигается (67 гонок идут своим ходом в слотах 07:00 / 15:00 / 23:00).

Что в ролике: старт гранд-финала с 32 лучшими странами «на сейчас» (по жизням, как season.finalists),
только начало — без развязки; сверху «GRAND FINAL · MON, NOV 30 · 23:00 MSK», в конце — карточка
«TOP 32 RIGHT NOW — IS YOUR COUNTRY IN?» с флагами. Трасса превью — своя (не та, что будет в финале):
это показ формата и текущей тридцатки, в описании так и сказано («right now»).
python3 announce.py 2026-11-28 out.mp4   — собрать локально (без выкладки)
"""
import copy
import datetime as dt
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw

import race
import render
import season
from render import font, text_center

ANNOUNCE_DATES = ("2026-11-28", "2026-11-29", "2026-11-30")
FINAL_DAY = dt.date(2026, 11, 30)
FINAL_MSK = "23:00 MSK"
FINAL_UTC = "20:00 UTC"
W, H = 1080, 1920
VIEW_W, SRC_H, CROP_W = 1440, 1080, 608
GOLD = (255, 214, 64)
GREEN = (70, 235, 130)
WHITE = (255, 255, 255)
SEG_START = 6.0         # с отсчёта в кольце: все 32 шара-флага вместе, сразу действие (без заставки)
SEG_LEN = 14.0          # гонка
CARD_LEN = 2.6          # карточка с флагами в конце
PREVIEW = SEG_START + SEG_LEN + CARD_LEN + 0.5


def days_left(d):
    return (FINAL_DAY - d).days


def when_line(d):
    k = days_left(d)
    if k <= 0:
        return f"TONIGHT · {FINAL_MSK}"
    if k == 1:
        return f"TOMORROW · {FINAL_MSK}"
    return f"MON, NOV 30 · {FINAL_MSK}"


def title(d):
    k = days_left(d)
    if k <= 0:
        t = "GRAND FINAL TONIGHT 23:00 MSK 🏆 32 countries, 1 champion — is yours in? #shorts"
    elif k == 1:
        t = "Grand Final TOMORROW 🏆 32 countries, 1 champion — is your country in? #shorts"
    else:
        t = f"Grand Final in {k} days 🏆 Top 32 right now — is your country in? Marble Race #shorts"
    return t[:100]


def lineup(state):
    """32 лучших «на сейчас» — как отберёт сезон (жизни, потом среднее место)."""
    return season.finalists(state)


def description(d, state, codes):
    lives = state["lives"]
    hearts = {3: "❤️❤️❤️", 2: "❤️❤️", 1: "❤️"}
    done = state.get("heat", 0)
    total = state.get("life_total", 0)
    left = max(0, total - done)
    k = days_left(d)
    when = "TONIGHT" if k <= 0 else ("TOMORROW" if k == 1 else f"Monday, November 30")
    lines = [
        f"🏆 Flagball Arena · Season {state['season']} GRAND FINAL — {when}, {FINAL_MSK} ({FINAL_UTC}).",
        "The 32 countries with the most lives race 7 stages — only one becomes champion.",
        "",
        f"Top 32 right now (after race {done} of {total}):",
        ", ".join(f"{race.NAMES[c]} {hearts.get(lives.get(c), '')}".strip() for c in codes) + ".",
        "",
    ]
    if left:
        lines.append(f"{left} race{'s' if left != 1 else ''} left before the final — every country can still "
                     f"move in or drop out.")
    lines += [
        "This clip is a preview of the final format with today's Top 32 — the real Grand Final is a new track.",
        "▶ 3 new races every day on @FlagballArenaTV — the full Grand Final goes live on the channel.",
        "",
        "Comment your country 👇 — will it make the final?",
        "",
        "#shorts #marblerace #grandfinal #countryballs #marblerun #countries #flags",
    ]
    if state.get("champions"):
        c = state["champions"][-1]
        lines.insert(2, f"Last champion: Season {c['season']} — {race.NAMES[c['code']]} 🏆")
    return "\n".join(lines)


def band_png(d, out_png):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("L", (1, 360))
    for y in range(360):
        band.putpixel((0, y), 170 if y <= 250 else int(170 * (1 - (y - 250) / 110)))
    img.paste(Image.new("RGBA", (W, 360), (0, 0, 0, 255)), (0, 0), band.resize((W, 360)))
    dr = ImageDraw.Draw(img)
    text_center(dr, W / 2, 50, "GRAND FINAL", font(118), GOLD, 8)
    text_center(dr, W / 2, 196, when_line(d), font(60), GREEN, 6)
    dr.rectangle([0, H - 230, W, H], fill=(0, 0, 0, 130))
    text_center(dr, W / 2, H - 205, "32 COUNTRIES · 1 CHAMPION", font(56), WHITE, 5)
    text_center(dr, W / 2, H - 120, "FLAGBALL ARENA · top 32 right now", font(36), GOLD, 4)
    img.save(out_png)


def card_png(d, codes, out_png):
    """Последние секунды: «TOP 32 RIGHT NOW — IS YOUR COUNTRY IN?», 32 шара-флага сеткой 4×8."""
    img = Image.new("RGBA", (W, H), (8, 8, 20, 255))
    dr = ImageDraw.Draw(img)
    text_center(dr, W / 2, 120, "TOP 32 RIGHT NOW", font(92), GOLD, 7)
    text_center(dr, W / 2, 240, "IS YOUR COUNTRY IN?", font(76), WHITE, 6)
    cols, rows = 4, 8
    x0, dx = 150, 260
    y0, dy = 420, 158
    for i, c in enumerate(codes[:32]):
        r, k = divmod(i, cols)
        cx, cy = x0 + k * dx, y0 + r * dy
        render.paste_center(img, render.ball_sprite(c, 50, 0.0), cx, cy)
        text_center(dr, cx, cy + 56, race.cname(c).upper()[:14], font(28), WHITE, 3)
    text_center(dr, W / 2, H - 230, f"GRAND FINAL · {when_line(d)}", font(52), GREEN, 5)
    text_center(dr, W / 2, H - 150, "FLAGBALL ARENA", font(40), WHITE, 4)
    img.save(out_png)


def make(d, state, out_mp4, work):
    """Собрать анонс. state — season_state (не меняется). Вернёт title, description, duration, codes."""
    os.makedirs(work, exist_ok=True)
    s = copy.deepcopy(state)
    codes = lineup(s)
    s["round"], s["heats"], s["survive"] = 4, [codes], [1]
    tmp_state = os.path.join(work, "announce_state.json")
    json.dump(s, open(tmp_state, "w"))
    src = os.path.join(work, "announce_src.mp4")
    cmd = [sys.executable, "race.py", "--date", d.isoformat(), "--slot", "1", "--state", tmp_state, "--out", src,
           "--preview", f"{PREVIEW:.1f}", "--no-save", "--no-next"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit("race.py (анонс) упал: " + (p.stdout + p.stderr)[-800:])
    band = os.path.join(work, "announce_band.png")
    card = os.path.join(work, "announce_card.png")
    band_png(d, band)
    card_png(d, codes, card)
    dur = SEG_LEN + CARD_LEN
    x0 = int(VIEW_W / 2 - CROP_W / 2)
    has_a = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                 "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    filt = (f"[0:v]crop={CROP_W}:{SRC_H}:{x0}:0,scale={W}:{H}:flags=lanczos,setsar=1[v0];"
            f"[1:v]format=rgba[b];[2:v]format=rgba[c];"
            f"[v0][b]overlay=0:0:shortest=1[v1];"
            f"[v1][c]overlay=0:0:enable='gte(t,{SEG_LEN:.2f})':shortest=1,"
            f"fade=t=out:st={dur - 0.4:.2f}:d=0.4[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{SEG_START:.2f}", "-t", f"{dur:.2f}", "-i", src,
           "-loop", "1", "-i", band, "-loop", "1", "-i", card, "-filter_complex", filt, "-map", "[v]"]
    if has_a:
        cmd += ["-map", "0:a", "-af", f"afade=t=out:st={dur - 0.8:.2f}:d=0.8", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "6000k", "-pix_fmt", "yuv420p", "-r", "30",
            "-t", f"{dur:.2f}", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return {"title": title(d), "description": description(d, state, codes), "duration": dur, "codes": codes}


if __name__ == "__main__":
    d = dt.date.fromisoformat(sys.argv[1])
    st = json.load(open("season_state.json"))
    r = make(d, st, sys.argv[2], "/tmp/fb_announce")
    print(r["title"], f"{r['duration']:.1f} с")
    print(r["description"])
