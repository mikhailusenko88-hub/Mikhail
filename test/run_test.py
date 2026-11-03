#!/usr/bin/env python3
"""Пробные ролики «Почему так?» голосом Альбины — тем же кодом, что пойдёт на сервер.
  python3 test/run_test.py /tmp/bot out
Кладёт в out/: <имя>.mp4 (ролик), <имя>_voice.mp3 (только голос), lines/<имя>_<n>.wav (+ .txt эталон)
для проверки ударений (без мягкой обработки), report.md (ударения, скорость, память)."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

bot, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
here = Path(__file__).resolve().parent
sys.path.insert(0, str(bot))
import albina            # noqa: E402
import make_video as mv  # noqa: E402

out.mkdir(parents=True, exist_ok=True)
(out / "lines").mkdir(exist_ok=True)
scripts = json.loads((here / "scripts.json").read_text(encoding="utf-8"))
only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
logs = []


def log(m):
    print(m, flush=True)
    logs.append(m)


assert getattr(mv.speak, "_albina", False), "speak не обёрнут"
assert getattr(mv.build, "_albina", False), "build не обёрнут"
cfg = {"voices": ["albina"], "channel_handle": "@pochemu_tak_fakty", "music_volume": 0.15,
       "use_stock_video": False, "music_by_format": {}}
rep = ["# Пробные ролики «Почему так?» — Альбина, мягкий тон", ""]
for sc in scripts:
    if only and sc["name"] not in only:
        continue
    name = sc["name"]
    t0 = time.time()
    dur = mv.build(sc, cfg, out / f"{name}.mp4", bot / "work", log=log)
    took = time.time() - t0
    work = bot / "work"
    # только голос — для прослушивания
    a = sorted(work.glob("a[0-9][0-9].mp3"))
    lst = work / "voice_list.txt"
    lst.write_text("".join(f"file '{x}'\n" for x in a))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-af",
                    "apad=pad_dur=0.3", "-c:a", "libmp3lame", "-q:a", "2", str(out / f"{name}_voice.mp3")], check=True)
    rep.append(f"## {sc['title']} ({sc['format']}) — {dur:.1f} с ролика, сборка {took:.0f} с")
    # фразы без мягкой обработки — для анализатора ударений
    for i, line in enumerate(sc["lines"]):
        for var, voice, label in (("c", "albina@dry", "режим bot"),):
            w = out / "lines" / f"pt_{name}_{i}{var}.mp3"
            albina.say(line, voice, w)
            (out / "lines" / f"pt_{name}_{i}{var}.txt").write_text(albina.plain(line) + "\n", encoding="utf-8")
            (out / "lines" / f"pt_{name}_{i}{var}.voice").write_text(f"Альбина, бот ({label})\n", encoding="utf-8")
            rep.append(f"- {var}: {albina._st['last']}")
    rep.append("")
# вопросы без вопросительного слова: насколько поднимать голос на последнем слове
QS = ["Летучие мыши совсем слепые?", "Хамелеон подстраивается под фон?", "Великую стену видно из космоса?",
      "Мамонты застали пирамиды?", "Правда, что мы используем только 10% мозга?"]
rep.append("## Вопросы: подъём на последнем слове")
for i, qtext in enumerate(QS):
    for var, qp in (("n", ""), ("h", "high"), ("x", "x-high")):
        w = out / "lines" / f"pq_{i}{var}.mp3"
        albina.say(qtext, f"albina@dry,q={qp}", w)
        (out / "lines" / f"pq_{i}{var}.txt").write_text(albina.plain(qtext) + "\n", encoding="utf-8")
        (out / "lines" / f"pq_{i}{var}.voice").write_text(f"Альбина, вопрос (подъём: {qp or 'нет'})\n", encoding="utf-8")
        if var == "h":
            albina.say(qtext, f"albina@q={qp}", out / f"q_{i}_soft.mp3")
    rep.append(f"- {albina._st['last']}")
albina.close()
rep += ["## Скорость и память", f"- память озвучщика: {albina._st['rss']} МБ",
        f"- память бота: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} МБ", "",
        "## Лог", "```", *logs, "```"]
(out / "report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
print("\n".join(rep))
