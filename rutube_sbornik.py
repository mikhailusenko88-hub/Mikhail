#!/usr/bin/env python3
"""Сборник серий подряд для Rutube (Юля выкладывает руками): python3 rutube_sbornik.py <имя>   — по sborniki/<имя>.json.

Качает ep-<релиз>.mp4 из релизов studio-<релиз> и склеивает их с пересжатием в один ровный поток:
H.264 без B-кадров, 1080p 25 к/с (Rutube ломал движение на склейках и B-кадрах — поэтому не «-c copy», как на YouTube).
Итог в out/:
  rutube-<имя>.mp4        — видео для загрузки на Rutube
  rutube-<имя>.jpg        — обложка (sborniki/<имя>.jpg)
  rutube-<имя>.txt        — название и описание для Rutube с таймкодами серий (поля rt_title / rt_desc, {CHAPTERS})
  rutube-<имя>-kadry.jpg  — проверочный лист: кадры на стыках серий и в середине каждой
"""
import json
import os
import subprocess
import sys
import urllib.request

REPO = "mikhailusenko88-hub/Mikhail"
LIMIT = 1_950_000_000                  # релиз GitHub принимает файл до 2 ГБ


def say(*a):
    print(*a, flush=True)


def run(cmd):
    say("$", " ".join(cmd)[:300])
    subprocess.run(cmd, check=True)


def probe(f, what="format=duration"):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", what, "-of", "csv=p=0", f],
                          capture_output=True, text=True, check=True).stdout.strip()


def tc(sec):
    sec = int(round(sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main():
    name = sys.argv[1]
    sb = json.load(open(f"sborniki/{name}.json", encoding="utf-8"))
    os.makedirs("tmp", exist_ok=True)
    os.makedirs("out", exist_ok=True)
    loc = os.environ.get("SERII_JSON")                      # для проверки без сети
    serii = json.load(open(loc, encoding="utf-8")) if loc else json.load(urllib.request.urlopen(f"https://raw.githubusercontent.com/{REPO}/mebel/s9kbars/serii.json", timeout=60))

    def ep_name(num):
        it = next((x for x in serii.get("items", []) if str(x.get("num")) == str(num)), None)
        return it["title"].split(" | ")[0].strip() if it else f"Серия {num}"

    files, durs, chapters, t0 = [], [], [], 0.0
    for it in sb["items"]:
        f = f"tmp/ep-{it['rel']}.mp4"
        if not os.path.exists(f):
            run(["curl", "-sSL", "--fail", "--retry", "3", "-o", f,
                 f"https://github.com/{REPO}/releases/download/studio-{it['rel']}/ep-{it['rel']}.mp4"])
        if os.path.getsize(f) < int(os.environ.get("MIN_BYTES", "20000000")):
            raise SystemExit(f"слишком маленький файл {f}")
        d = float(probe(f))
        chapters.append(f"{tc(t0)} {it.get('name') or ep_name(it['num'])}")
        files.append(f)
        durs.append(d)
        t0 += d
        say(f"серия {it['num']} ({it['rel']}): {d / 60:.1f} мин")

    n = len(files)
    parts = []
    for i in range(n):
        parts.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                     f"fps=25,setsar=1,format=yuv420p[v{i}];"
                     f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono[a{i}]")
    fc = ";".join(parts) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    out = f"out/rutube-{name}.mp4"
    for crf in (21, 24, 27):
        cmd = ["ffmpeg", "-v", "error", "-stats", "-y"]
        for f in files:
            cmd += ["-i", f]
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-maxrate", "4000k", "-bufsize", "8000k",
                "-bf", "0", "-g", "50", "-keyint_min", "25", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out]
        run(cmd)
        if os.path.getsize(out) < LIMIT:
            break
        say(f"файл {os.path.getsize(out) / 1e9:.2f} ГБ — больше 2 ГБ, пересжимаю сильнее")
    else:
        raise SystemExit("не уложился в 2 ГБ")

    dur = float(probe(out))
    bfr = probe(out, "stream=has_b_frames").splitlines()[0]
    mb = os.path.getsize(out) / 1e6
    say(f"готово: {dur / 60:.1f} мин (серии в сумме {t0 / 60:.1f}), {mb:.0f} МБ, B-кадры: {bfr}")
    if abs(dur - t0) > 3:
        raise SystemExit(f"длина не совпала: {dur:.1f} против {t0:.1f}")

    # проверочный лист: на каждом стыке — последний кадр серии и первый следующей, плюс середина каждой
    marks, t = [], 0.0
    for i, d in enumerate(durs):
        marks.append(t + 1.0)
        marks.append(t + d / 2)
        t += d
        if i < n - 1:
            marks.append(t - 0.5)
    os.makedirs("tmp/kadry", exist_ok=True)
    for k, m in enumerate(marks):
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{m:.2f}", "-i", out, "-frames:v", "1", "-vf", "scale=384:216",
             f"tmp/kadry/{k:03d}.jpg"])
    cols = 6
    run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", "tmp/kadry/%03d.jpg",
         "-vf", f"tile={cols}x{(len(marks) + cols - 1) // cols}:padding=4:color=white", "-frames:v", "1",
         f"out/rutube-{name}-kadry.jpg"])

    if os.path.exists(sb.get("cover", "")):
        run(["cp", sb["cover"], f"out/rutube-{name}.jpg"])
    title = sb.get("rt_title") or sb["title"]
    desc = (sb.get("rt_desc") or sb["desc"]).replace("{CHAPTERS}", "\n".join(chapters))
    open(f"out/rutube-{name}.txt", "w", encoding="utf-8").write(
        f"НАЗВАНИЕ:\n{title}\n\nОПИСАНИЕ:\n{desc}\n\nКатегория: Детям. Длина: {tc(dur)}. Файл: rutube-{name}.mp4, {mb:.0f} МБ.\n")
    say(open(f"out/rutube-{name}.txt", encoding="utf-8").read())


if __name__ == "__main__":
    main()
