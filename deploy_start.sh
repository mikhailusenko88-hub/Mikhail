#!/bin/bash
# «Білесің бе?»: ролики гонок начинаются сразу с движения — без отсчёта «3-2-1» (шарики уже катятся).
#   Меняется только race_video.py. Темы, таблицы, расписание, города из комментариев — как были. Ролик короче на 2 секунды.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL --max-time 40 https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_start.sh | bash
# Вернуть отсчёт:  ... | bash -s -- --back
# Безопасно: прежний файл хранится как race_video.py.bak-countdown, при ошибке всё возвращается. Повтор ничего не ломает.
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
D=/root/kz-bot
[ -f "$D/run_daily.py" ] && [ -f "$D/race_video.py" ] || { echo "!! Нет папки бота $D"; echo "НЕ ВСТАЛО"; exit 1; }
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"
f=race_video.py
B=$f.bak-countdown

if [ "${1:-}" = "--back" ]; then
  [ -f "$B" ] || { echo "!! Нет сохранённого файла с отсчётом ($B)"; exit 1; }
  cp -p "$B" "$f" && "$PY" -m py_compile "$f" && echo "== Готово: отсчёт «3-2-1» возвращён." && exit 0
  echo "!! Не получилось вернуть"; exit 1
fi

if pgrep -f "run_daily.py" >/dev/null; then echo "Бот прямо сейчас делает ролик — запусти эту команду через 5 минут"; exit 0; fi

grep -q "^T0 = " "$f" || cp -p "$f" "$B"          # прежний файл (с отсчётом) сохраняем один раз
cp -p "$f" "$f.prev"
restore() { echo "!! Ошибка — возвращаю как было"; cp -p "$f.prev" "$f"; rm -f "$f.new" "$f.prev"; echo "НЕ ВСТАЛО"; exit 1; }

echo "== Скачиваю"
curl -fsSL --max-time 40 "$RAW/$f" -o "$f.new" || { echo "!! не скачался $f"; restore; }
grep -q "^T0 = GATE_T" "$f.new" || { echo "!! скачался не тот файл"; restore; }
mv "$f.new" "$f"
"$PY" -m py_compile "$f" || restore

echo "== Проверка"
"$PY" race_video.py --check | grep -E "cities|aimaq|names" || restore
"$PY" - <<'PY' || restore
import race_video as rv, race_leagues as RL
assert abs(rv.T0 - (rv.GATE_T + 0.8)) < 1e-9
RL.set_aimaq(0)
print("   старт ролика: с", rv.T0, "секунды заезда (отсчёта нет); участников в неделе области:", len(RL.entries("aimaq")))
PY
rm -f "$f.prev"

echo
echo "== Готово. Со следующего ролика гонки начинаются сразу с движения."
echo "   Вернуть отсчёт: та же команда с  -s -- --back  после bash"
