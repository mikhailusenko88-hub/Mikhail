#!/bin/bash
# «Білесің бе?»: новая гонка «Облыс апталығы / Неделя области» в 12:00 вместо первой гонки городов.
#   Каждую неделю одна область (начинаем с Мангистау): её города и аулы, в воскресенье в 12:00 — финал области.
#   Гонка городов остаётся в 18:00 (воскресный финал городов — как был). Теңге — в список просьб гонки городов.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL --max-time 40 https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_aimaq.sh | bash
# Вернуть как было (две гонки городов):  ... | bash -s -- --back
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
BACK=0; [ "${1:-}" = "--back" ] && BACK=1
D=/root/kz-bot
[ -f "$D/run_daily.py" ] && [ -f "$D/config.json" ] || { echo "!! Нет папки бота $D"; exit 1; }
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

set_slot() {
  "$PY" - "$1" <<'PY'
import json, sys
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
sl = cfg.get("race_slots") or {"12": "cities", "15": "theme", "18": "cities"}
want = sys.argv[1]
hours = sorted(sl, key=int)
if want == "aimaq":
    cities = [h for h in hours if sl[h] == "cities"]
    if not any(v == "aimaq" for v in sl.values()):
        if len(cities) < 2:
            sys.exit("!! в расписании меньше двух гонок городов — ничего не меняю")
        sl[cities[0]] = "aimaq"            # первая гонка городов за день → неделя области
else:
    for h in hours:
        if sl[h] == "aimaq":
            sl[h] = "cities"
cfg["race_slots"] = sl
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   расписание (Астана): " + ", ".join(f"{h}:00 — {sl[h]}" for h in hours))
PY
}

cp -p config.json "config.json.bak-$STAMP"
if [ $BACK = 1 ]; then set_slot cities && echo "== Готово: снова две гонки городов."; exit 0; fi

FILES="race_video.py race_bot.py race_leagues.py kz_places.py kz_aimaq.py"
for f in $FILES; do [ -f "$f" ] && cp -p "$f" "$f.bak-$STAMP"; done
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "config.json.bak-$STAMP" config.json
  for f in $FILES; do [ -f "$f.bak-$STAMP" ] && cp -p "$f.bak-$STAMP" "$f"; done
  [ -f kz_aimaq.py.bak-$STAMP ] || rm -f kz_aimaq.py
  rm -f ./*.new
  echo "НЕ ВСТАЛО"
  exit 1
}

echo "== Скачиваю"
for f in $FILES; do
  curl -fsSL --max-time 40 "$RAW/$f" -o "$f.new" || { echo "!! не скачался $f"; restore; }
done
for f in $FILES; do mv "$f.new" "$f"; done
"$PY" -m py_compile $FILES || restore

echo "== Проверка"
"$PY" race_video.py --check | grep -E "aimaq|cities" || restore
"$PY" - <<'PY' || restore
import race_leagues as RL
RL.set_aimaq(0)
t = RL.make_title("aimaq", 1, RL.entries("aimaq"))
assert len(t) <= 92 and len(RL.entries("aimaq")) >= 9, t
print("   " + t)
PY

echo "== Расписание"
set_slot aimaq || restore

# Теңге — в гонку городов по просьбе зрителей (один раз)
if ! grep -q "Теңге" state.json 2>/dev/null && ! grep -q "Теңге" city_requests.txt 2>/dev/null; then
  echo "город Теңге" >> city_requests.txt && echo "== Теңге добавится в следующую гонку городов"
fi

echo
echo "== Готово. Первая «Неделя области» (Мангистау) — завтра в 12:00 по Астане."
echo "   Выложить её прямо сейчас:  srv race aimaq"
