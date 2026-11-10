#!/bin/bash
# «Білесің бе?»: названия гонок городов и клубов начинаются с трёх участников (каждый заезд — другие, по кругу):
#   «Қонаев, Талғар, Жаркент… Қай қала жеңеді? Какой город победит? 🏁 №21» вместо одинаковых «№20».
# Меняется только race_leagues.py (названия). Города из комментариев, таблица, расписание — как были.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_titles.sh | bash
# Безопасно: делает копию (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}

D=""
for c in /root/kz-bot; do [ -f "$c/run_daily.py" ] && [ -f "$c/config.json" ] && D="$c"; done
if [ -z "$D" ]; then
  f=$(find / -xdev -name race_leagues.py -not -path '/proc/*' -not -path '*/.git/*' 2>/dev/null | head -1)
  [ -n "$f" ] && D=$(dirname "$f")
fi
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Білесің бе?»"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

f=race_leagues.py
cp -p "$f" "$f.bak-$STAMP"
restore() { echo "!! Ошибка — возвращаю как было"; cp -p "$f.bak-$STAMP" "$f"; exit 1; }

echo "== Скачиваю"
curl -fsSL "$RAW/$f?$STAMP" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
"$PY" -m py_compile "$f" || restore

echo "== Проверка названий"
"$PY" - <<'PY' || restore
import race_leagues as RL
for lg in ("cities", "clubs"):
    for no in (1, 2):
        t = RL.make_title(lg, no, RL.entries(lg))
        assert len(t) <= 92 and "…" in t, t
        print("   " + t)
PY

echo
echo "== Готово. Новые названия — со следующего ролика."
