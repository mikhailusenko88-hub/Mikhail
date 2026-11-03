#!/usr/bin/env python3
"""Озвучка заранее (в GitHub Actions): тексты будущих роликов «Почему так?» -> готовые фразы голосом Альбины.
Бот на сервере (961 МБ памяти) голос не запускает — только скачивает эти фразы.
  ALBINA_NO_GH=1 python farm.py <bank.json или адрес> <папка озвучки>
В папке: v/<ключ>.mp3 (ключ — albina.cache_key), index.json {ключ: {"t": текст, "m": с ударениями}}, report.md"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

os.environ["ALBINA_NO_GH"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import albina  # noqa: E402

src, out = sys.argv[1], Path(sys.argv[2])
if src.startswith("http"):
    with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "albina-farm"}), timeout=60) as r:
        bank = json.load(r)
else:
    bank = json.loads(Path(src).read_text(encoding="utf-8"))
(out / "v").mkdir(parents=True, exist_ok=True)
ip = out / "index.json"
index = json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else {}
if str(bank.get("ver", albina.VOICE_VER)) != albina.VOICE_VER:
    print(f"! версия озвучки на сервере {bank.get('ver')} ≠ {albina.VOICE_VER} — обнови albina.py на сервере")

need = {}
for voice in bank.get("voices") or ["albina"]:
    for s in bank.get("scripts", []):
        for line in s.get("lines", []):
            need[albina.cache_key(line, voice)] = (line, voice)
    st = bank.get("selftest") or albina.SELFTEST_TEXT
    need[albina.cache_key(st, voice)] = (st, voice)

t0, made, kept, fail = time.time(), 0, 0, []
for i, (key, (line, voice)) in enumerate(need.items()):
    f = out / "v" / f"{key}.mp3"
    if f.exists() and f.stat().st_size > 2000 and key in index:
        kept += 1
        continue
    try:
        albina.say(line, voice, f)
        index[key] = {"t": line, "m": albina._st["last"]}
        made += 1
    except Exception as e:
        fail.append(f"{line} — {e}")
    if made and made % 25 == 0:
        ip.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"  озвучено {made}, {time.time() - t0:.0f} с", flush=True)
albina.close()

# лишнее (сценарии уже вышли) — убрать, чтобы ветка не росла
removed = 0
if bank.get("scripts"):
    for f in (out / "v").glob("*.mp3"):
        if f.stem not in need:
            f.unlink(); removed += 1
    index = {k: v for k, v in index.items() if k in need}
ip.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
size = sum(f.stat().st_size for f in (out / "v").glob("*.mp3")) / 1e6
rep = [f"# Озвучка заранее — {time.strftime('%Y-%m-%d %H:%M')} UTC",
       f"- сценариев в банке: {len(bank.get('scripts', []))}, фраз: {len(need)}",
       f"- новых озвучено: {made}, уже были: {kept}, убрано старых: {removed}, не вышло: {len(fail)}",
       f"- папка озвучки: {size:.1f} МБ, время: {time.time() - t0:.0f} с",
       f"- тексты выложены сервером: {bank.get('updated')}, ИИ-сценарии: {'включены' if bank.get('use_ai') else 'нет'}"]
if fail:
    rep += ["", "## Не озвучилось"] + [f"- {x}" for x in fail[:30]]
rep += ["", "## Пример ударений"] + [f"- {v['m']}" for v in list(index.values())[:12]]
(out / "report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
print("\n".join(rep))
sys.exit(1 if fail and not made and not kept else 0)
