#!/bin/bash
# «Білесің бе?» (15.11.2026): ставит сразу всё новое —
#   • шаг A: гонки ~30–38 с вместо минуты, 12 городов в заезде (по кругу), тема дня — только мүшел и имена;
#   • «1000 шарик: қай қала жеңеді?» — 1000 шариков 10 городов сыплются в кубок, чьих больше — победил
#     (каждый день свои города, трасса, цвет и музыка; ролик 22–31 с);
#   • расписание (Астана): 12:00 — «1000 шарик», 15:00 — тема дня, 18:00 — гонка городов (финал недели — как был).
#     Если «1000 шарик» почему-то не соберётся — в 12:00 выйдет обычная гонка городов.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL --max-time 40 https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_mass.sh | bash
# Вернуть как было:  ... | bash -s -- --back
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
D=${D:-/root/kz-bot}
[ -f "$D/run_daily.py" ] && [ -f "$D/race_video.py" ] && [ -f "$D/race_bot.py" ] || { echo "!! Нет папки бота $D"; echo "НЕ ВСТАЛО"; exit 1; }
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"
FILES="race_video.py race_bot.py config.json"

if [ "${1:-}" = "--back" ]; then
  for f in $FILES; do [ -f "$f.bak-mass" ] && cp -p "$f.bak-mass" "$f"; done
  "$PY" -m py_compile race_video.py race_bot.py && echo "== Готово: вернул как было до этой установки." && exit 0
  echo "!! Не получилось вернуть"; exit 1
fi

if pgrep -f "run_daily.py" >/dev/null; then echo "Бот прямо сейчас делает ролик — запусти эту команду через 5 минут"; exit 0; fi

grep -q "def run_mass" race_bot.py || { for f in $FILES; do cp -p "$f" "$f.bak-mass"; done; }   # прежнее — один раз
for f in $FILES; do cp -p "$f" "$f.prev"; done
restore() { echo "!! Ошибка — возвращаю как было"; for f in $FILES; do cp -p "$f.prev" "$f"; done; rm -f *.new *.prev; echo "НЕ ВСТАЛО"; exit 1; }

echo "== Скачиваю"
for f in race_video.py race_bot.py; do
  curl -fsSL --max-time 40 "$RAW/$f" -o "$f.new" || { echo "!! не скачался $f"; restore; }
done
grep -q "^SECTIONS = \[3, 4, 4\]" race_video.py.new || { echo "!! скачался не тот race_video.py"; restore; }
grep -q "def run_mass" race_bot.py.new || { echo "!! скачался не тот race_bot.py"; restore; }
mkdir -p mass
for f in mass_video.py layout.py sim_run.py mass_sim.c mass_sim.bin; do
  curl -fsSL --max-time 60 "$RAW/mass/$f" -o "mass/$f.new" || { echo "!! не скачался mass/$f"; restore; }
  mv "mass/$f.new" "mass/$f"
done
grep -q "def render(out, seed=1, n=1000, cities" mass/mass_video.py || { echo "!! скачался не тот mass_video.py"; restore; }
mv race_video.py.new race_video.py; mv race_bot.py.new race_bot.py
"$PY" -m py_compile race_video.py race_bot.py mass/mass_video.py mass/layout.py mass/sim_run.py || restore

echo "== Физика «1000 шарик»"
if command -v gcc >/dev/null && gcc -O2 -o mass/mass_sim mass/mass_sim.c -lm 2>/dev/null; then
  echo "   собрал на сервере (gcc)"
else
  cp mass/mass_sim.bin mass/mass_sim && echo "   взял готовую сборку"
fi
chmod +x mass/mass_sim
command -v ffmpeg >/dev/null || { echo "!! нет ffmpeg"; restore; }

echo "== Расписание"
"$PY" - <<'PY' || restore
import json
c = json.load(open("config.json", encoding="utf-8"))
c["mode"] = c.get("mode", "race")
c["race_slots"] = {"12": "mass", "15": "theme", "18": "cities"}
c["theme_leagues"] = ["mushel", "names"]
json.dump(c, open("config.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("   12:00 — «1000 шарик», 15:00 — тема дня (мүшел / имена), 18:00 — гонка городов (Астана)")
PY

echo "== Проверка"
"$PY" - <<'PY' || restore
import random, sys
from pathlib import Path
import race_bot as RB
ent = RB.city_subset({})
assert ent and len(ent) == 12, "нет 12 городов"
cities = RB.mass_cities({}, random.Random(5))
assert len(cities) == 10, "нет 10 городов для «1000 шарик»"
sys.path.insert(0, str(Path("mass").resolve()))
import layout as L, sim_run, mass_video as M
sc = L.Scene(random.Random(5))
pos, hits = sim_run.run(sc, T=2.0, seed=5)
moved = (pos[-1, :, 1] > pos[0, :, 1] + 5).sum()
assert moved > 100, "шарики не сыплются"
M.CITIES = [(k, r, c) for (k, r), c in zip(cities, M.PALETTE)]
M.static_layer(sc)
assert sorted(Path("music").glob("*.mp3")), "нет музыки"
print(f"   12 городов в гонке; «1000 шарик»: физика и картинка в порядке ({moved} шариков уже в пути за 2 с)")
PY
rm -f *.prev

echo
echo "== Готово. Завтра в 12:00 по Астане (10:00 МСК) — первый «1000 шарик», гонки короче, 12 городов."
echo "   Вернуть как было: та же команда с  -s -- --back  после bash"
