"""Shorts 1080×1920 из заезда: финальный этап (последние ~22 с) + вылет, вырезан из горизонтального ролика
(кадр камеры 1440 px — берём центр 9:16). С первого кадра идёт гонка (без заставки-надписи, с 15.11.2026):
сверху три крупных шара-флага «лицом к лицу» и «WHO SURVIVES?», снизу сколько теряют жизнь.
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
TAIL = 22.0             # секунд финального этапа до финиша (если старт не берём)
HEAD = 6.0              # с 15.11.2026: первые секунды — старт этапа, все шары-флаги вместе (с первого кадра действие)
TAIL2 = 16.0            # …потом склейка на последние секунды до финиша и вылет
GOLD = (255, 214, 64)
GREEN = (70, 235, 130)
WHITE = (255, 255, 255)


def overlay(codes, survive, n, out_png, lives=False):
    """Видна с первого кадра: три шара-флага (те же страны, что в названии) + вопрос. Фон полосы — мягкий градиент,
    чтобы не закрывать трассу."""
    import popular
    import render
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("L", (1, 430))
    for y in range(430):
        band.putpixel((0, y), 150 if y <= 300 else int(150 * (1 - (y - 300) / 130)))
    img.paste(Image.new("RGBA", (W, 430), (0, 0, 0, 255)), (0, 0), band.resize((W, 430)))
    d = ImageDraw.Draw(img)
    feat = popular.featured(codes, 3)
    xs = [210, 540, 870] if len(feat) == 3 else [330, 750]
    for x, c in zip(xs, feat):
        render.paste_center(img, render.ball_sprite(c, 92, 0.0), x, 125)
        text_center(d, x, 228, race.cname(c).upper(), font(40), WHITE, 5)
    for a, b in zip(xs, xs[1:]):
        text_center(d, (a + b) / 2, 92, "VS", font(56), GOLD, 6)
    text_center(d, W / 2, 292, "WHO SURVIVES?", font(92), GOLD, 7)
    d.rectangle([0, H - 220, W, H], fill=(0, 0, 0, 120))
    text_center(d, W / 2, H - 200, f"{n - survive} OF {n} LOSE A LIFE" if lives else f"ONLY {survive} OF {n} SURVIVE",
                font(54), GREEN, 5)
    text_center(d, W / 2, H - 120, "FLAGBALL ARENA · new races every day", font(34), WHITE, 4)
    img.save(out_png)


def make(part_mp4, part_json, out_mp4, pre=None):
    meta = json.load(open(part_json))
    spans = meta.get("spans") or []
    if not spans:
        raise SystemExit("в meta нет spans — race.py старый")
    s0, s1, s2 = spans[-1]                     # финальный этап: старт гонки, финиш, конец «вылетевших»
    total = meta.get("duration", s2)
    s1, s2 = min(s1, total), min(s2, total)
    if s1 - TAIL2 > s0 + HEAD + 2:              # два куска: старт этапа (все флаги вместе) + концовка
        segs = [(s0, HEAD), (s1 - TAIL2, s2 - (s1 - TAIL2))]
    else:
        start = max(s0, s1 - TAIL)
        segs = [(start, s2 - start)]
    dur = sum(t for _, t in segs)
    if dur < 8:
        raise SystemExit("слишком короткий кусок для Shorts")
    ov = out_mp4 + ".png"
    overlay(meta["codes"], meta["survive"], meta["n"], ov, lives=meta.get("lives_mode", False))
    x0 = int(VIEW_W / 2 - CROP_W / 2)
    has_a = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                 "-of", "csv=p=0", part_mp4], capture_output=True, text=True).stdout.strip())
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for a, t in segs:
        cmd += ["-ss", f"{a:.2f}", "-t", f"{t:.2f}", "-i", part_mp4]
    cmd += ["-loop", "1", "-i", ov]
    n = len(segs)
    if has_a:
        cat = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca];"
    else:
        cat = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cv];"
    filt = (cat + f"[cv]crop={CROP_W}:{SRC_H}:{x0}:0,scale={W}:{H}:flags=lanczos,setsar=1[v0];"
            f"[{n}:v]format=rgba[ov];[v0][ov]overlay=0:0:shortest=1,fade=t=out:st={dur - 0.5:.2f}:d=0.5[v]")
    cmd += ["-filter_complex", filt, "-map", "[v]"] + (["-map", "[ca]", "-c:a", "aac", "-b:a", "160k"] if has_a else [])
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-b:v", "6000k", "-pix_fmt", "yuv420p", "-r", "30",
            "-t", f"{dur:.2f}", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    vs = race.vs_line(meta["codes"], 3)
    try:
        title = story_title(meta, pre)
    except Exception:  # noqa: BLE001 — название не должно ломать выкладку
        title = f"{vs} 😱 Who Survives? Country Marble Race #shorts"[:100]
    return {"title": title, "duration": dur, "vs": vs, "pre": pre}


def description(meta, full_link=""):
    names = ", ".join(sorted(race.NAMES[c] for c in meta["codes"]))
    head = (f"{meta['n']} countries, 3 lives each ❤️ — the last {meta['n'] - meta['survive']} lose a life."
            if meta.get("lives_mode") else f"{meta['n']} countries, only {meta['survive']} survive.")
    return (f"{head}\n"
            + (f"▶ Full race on @FlagballArenaTV — {full_link}\n\n" if full_link else
               "▶ New races every day on @FlagballArenaTV · full Sunday Mega Track race every week\n\n")
            + f"Countries: {names}.\n\nLike 👍 if your country survived! Comment who you're cheering for.\n\n"
            f"#shorts #marblerace #countryballs #marblerun #survival #countries")


# ---------- название и описание из сюжета сезона (15.11.2026) ----------
# Чтобы ролики не выглядели «по одному шаблону» (правило YouTube о неоригинальном контенте для монетизации)
# и зритель видел историю: у кого сколько жизней, сколько стран ещё в игре, сколько до финала.

import datetime as _dt

HEARTS = {3: "❤️❤️❤️", 2: "❤️❤️", 1: "❤️"}
TAG_POOL = ["#countryballs", "#marblerun", "#survival", "#countries", "#simulation", "#satisfying", "#race",
            "#worldcup", "#flags", "#whowillwin"]


def _hashtag(c):
    return "#" + "".join(ch for ch in race.cname(c) if ch.isalnum())


def story_title(meta, pre):
    """Одна из нескольких формул — по сюжету гонки; без спойлеров (кто потеряет жизнь — не пишем)."""
    pre = pre or {}
    feat = popular.featured(meta["codes"], 3)
    a, b, c = (race.cname(x) for x in (feat + feat[:1] * 3)[:3])
    vs = " vs ".join(race.cname(x) for x in feat)
    lives = pre.get("lives") or {}
    n, lose = meta["n"], meta["n"] - meta["survive"]
    rno = meta.get("race_no", 0)
    opts = []
    last = [x for x in feat if lives.get(x) == 1]
    if last:
        opts += [f"{race.cname(last[0])} on its LAST life ❤️ {vs} — Who Survives? #shorts",
                 f"Last chance for {race.cname(last[0])} 😱 {vs} | Country Marble Race #shorts"]
    if lives and all(lives.get(x) == 3 for x in feat):
        opts.append(f"{a}, {b} or {c}: who loses the first life? 💔 Marble Race #shorts")
    if lives:
        opts.append(" vs ".join(f"{race.cname(x)} {HEARTS.get(lives.get(x), '')}".strip() for x in feat)
                    + " — Who Survives? #shorts")
    if meta.get("mega"):
        opts.append(f"SUNDAY MEGA TRACK 🔥 {vs} — who loses a life? #shorts")
    heat, total = pre.get("heat"), pre.get("heats")
    if heat and total:
        opts.append(f"Race {heat}/{total}: {lose} of {n} lose a life 😱 {vs} #shorts")
    if pre.get("alive") and pre["alive"] <= 120:
        opts.append(f"Only {pre['alive']} countries still alive 🌍 {vs} — who drops out? #shorts")
    fd = pre.get("final_date")
    if fd and meta.get("date"):
        try:
            days = (_dt.date.fromisoformat(fd) - _dt.date.fromisoformat(meta["date"])).days
            if days > 0:
                opts.append(f"{days} days to the Grand Final ⏳ {vs} — Who Survives? #shorts")
        except ValueError:
            pass
    opts.append(f"{vs} 😱 Who Survives? Country Marble Race #shorts")
    # «последняя жизнь» — самая сильная история, но не в каждом ролике, иначе снова одна формула
    t = opts[(rno // 2) % 2] if last and rno % 2 == 0 else opts[rno % len(opts)]
    return t if len(t) <= 100 else f"{vs} 😱 Who Survives? #shorts"[:100]


def story_description(meta, pre, full_link=""):
    pre = pre or {}
    feat = popular.featured(meta["codes"], 3)
    lives = pre.get("lives") or {}
    lines = []
    if meta.get("lives_mode"):
        lines.append(f"{meta['n']} countries, 3 lives each ❤️ — the last {meta['n'] - meta['survive']} lose a life.")
    else:
        lines.append(f"{meta['n']} countries, only {meta['survive']} survive.")
    if pre.get("heat") and pre.get("heats"):
        part = f"Season {meta.get('season', '')} · race {pre['heat']} of {pre['heats']}"
        if pre.get("alive"):
            part += f" · {pre['alive']} countries still alive"
        if pre.get("eliminated"):
            part += f" · {len(pre['eliminated'])} out"
        lines.append(part + ".")
    if lives:
        lines.append("Lives before this race: " + ", ".join(f"{race.NAMES[x]} {HEARTS.get(lives.get(x), '💀')}"
                                                             for x in feat) + ".")
    if pre.get("eliminated"):
        lines.append("Already out: " + ", ".join(race.NAMES[x] for x in pre["eliminated"][-4:]) + ".")
    if pre.get("final_date"):
        try:
            fd = _dt.date.fromisoformat(pre["final_date"])
            lines.append(f"Grand Final: {fd.strftime('%B')} {fd.day} — the 32 countries with the most lives.")
        except ValueError:
            pass
    lines.append(f"▶ Full race on @FlagballArenaTV — {full_link}" if full_link else
                 "▶ New races every day on @FlagballArenaTV · full Sunday Mega Track race every week")
    names = ", ".join(sorted(race.NAMES[c] for c in meta["codes"]))
    lines += ["", f"Countries in this race: {names}.", "",
              "Comment your country 👇 — is it still alive?"]
    rno = meta.get("race_no", 0)
    extra = [TAG_POOL[(rno + k * 3) % len(TAG_POOL)] for k in range(3)]
    tags = ["#shorts", "#marblerace"] + [_hashtag(x) for x in feat] + extra
    lines += ["", " ".join(dict.fromkeys(tags))]
    return "\n".join(lines)


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2], sys.argv[3]))
