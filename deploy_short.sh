#!/bin/bash
# «Білесің бе?» (15.11.2026, по аналитике Studio):
#   • гонка короче: ролик ~30–38 с вместо минуты (смотрели в среднем 25–30 с и уходили до развязки);
#   • в гонке городов 12 участников (было 22–30 — свой город не найти); по кругу: кто реже бежал на неделе — тот первый,
#     города из комментариев — в ближайший заезд; таблица недели и финал в воскресенье — как были;
#   • расписание (Астана): 12:00 — гонка городов, 15:00 — тема дня (только мүшел и имена), 18:00 — гонка городов.
#     Убраны слабые: «Неделя области» (Маңғыстау), регионы, ру, клубы (у них были единицы–десятки просмотров).
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL --max-time 40 https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_short.sh | bash
# Вернуть как было:  ... | bash -s -- --back
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
D=${D:-/root/kz-bot}
[ -f "$D/run_daily.py" ] && [ -f "$D/race_video.py" ] && [ -f "$D/race_bot.py" ] || { echo "!! Нет папки бота $D"; echo "НЕ ВСТАЛО"; exit 1; }
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"
FILES="race_video.py race_bot.py config.json"

if [ "${1:-}" = "--back" ]; then
  for f in $FILES; do [ -f "$f.bak-short" ] && cp -p "$f.bak-short" "$f"; done
  "$PY" -m py_compile race_video.py race_bot.py && echo "== Готово: вернул как было (минута, все города, прежнее расписание)." && exit 0
  echo "!! Не получилось вернуть"; exit 1
fi

if pgrep -f "run_daily.py" >/dev/null; then echo "Бот прямо сейчас делает ролик — запусти эту команду через 5 минут"; exit 0; fi

grep -q "^CITY_RACE_N" race_bot.py || { for f in $FILES; do cp -p "$f" "$f.bak-short"; done; }   # прежнее — один раз
for f in $FILES; do cp -p "$f" "$f.prev"; done
restore() { echo "!! Ошибка — возвращаю как было"; for f in $FILES; do cp -p "$f.prev" "$f"; done; rm -f *.new *.prev; echo "НЕ ВСТАЛО"; exit 1; }

echo "== Скачиваю"
for f in race_video.py race_bot.py; do
  curl -fsSL --max-time 40 "$RAW/$f" -o "$f.new" || { echo "!! не скачался $f"; restore; }
done
grep -q "^SECTIONS = \[3, 4, 4\]" race_video.py.new || { echo "!! скачался не тот race_video.py"; restore; }
grep -q "^CITY_RACE_N = 12" race_bot.py.new || { echo "!! скачался не тот race_bot.py"; restore; }
mv race_video.py.new race_video.py; mv race_bot.py.new race_bot.py
"$PY" -m py_compile race_video.py race_bot.py || restore

echo "== Расписание"
"$PY" - <<'PY' || restore
import json
c = json.load(open("config.json", encoding="utf-8"))
c["mode"] = c.get("mode", "race")
c["race_slots"] = {"12": "cities", "15": "theme", "18": "cities"}
c["theme_leagues"] = ["mushel", "names"]
json.dump(c, open("config.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("   12:00 — гонка городов, 15:00 — тема дня (мүшел / имена), 18:00 — гонка городов (Астана)")
PY

echo "== Проверка"
"$PY" race_video.py --check | grep -E "cities|names" || restore
"$PY" - <<'PY' || restore
import random, race_video as rv, race_bot as RB
ent = RB.city_subset({})
assert ent and len(ent) == 12, "нет 12 городов"
rv.set_league("cities", ent)
ok = None
for k in range(10):
    s = 777 + k * 7919
    c = rv.Course(random.Random(s), rv.N, sections=random.Random(s).choice(rv.SECTIONS))
    sim = rv.Sim(c, s)
    sim.run(post=1.0, give_up=(rv.WIN_MIN - 6, rv.WIN_MAX + 6))
    if sim.finish and rv.WIN_MIN <= sim.finish[0][1] - rv.GATE_T <= rv.WIN_MAX:
        ok = round(sim.finish[0][1] - rv.GATE_T, 1)
        break
assert ok, "не нашлась короткая трасса"
print(f"   12 городов в заезде, пробная трасса: победа на {ok} с — ролик около {ok + 6:.0f}–{ok + 9:.0f} с")
PY
rm -f *.prev

echo
echo "== Готово. Со следующего ролика: гонки ~30–38 с, 12 городов, тема дня — мүшел и имена."
echo "   Вернуть как было: та же команда с  -s -- --back  после bash"
