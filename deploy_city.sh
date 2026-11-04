#!/bin/bash
# «Білесің бе?»: добавить Талғар (Талгар) в гонку городов «Қай қала жеңеді?» — 21-й город.
# Запуск на сервере:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_city.sh | bash
# Безопасно: делает копию race_leagues.py.bak-ДАТА, при ошибке возвращает назад.
# Повторный запуск ничего не ломает (если Талгар уже есть — просто скажет об этом).
set -u
STAMP=$(date +%Y%m%d-%H%M%S)

D=""
for c in /root/kz-bot; do [ -f "$c/race_leagues.py" ] && D="$c"; done
if [ -z "$D" ]; then
  f=$(find / -xdev -name race_leagues.py -not -path '/proc/*' -not -path '*/.git/*' 2>/dev/null | head -1)
  [ -n "$f" ] && D=$(dirname "$f")
fi
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Білесің бе?»"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

if grep -q '"Талғар"' race_leagues.py; then
  echo "== Талгар уже в списке городов — ничего менять не нужно"
  exit 0
fi

cp -p race_leagues.py "race_leagues.py.bak-$STAMP"
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "race_leagues.py.bak-$STAMP" race_leagues.py
  exit 1
}

echo "== Добавляю Талгар"
"$PY" - <<'EOF' || restore
from pathlib import Path
p = Path("race_leagues.py")
s = p.read_text(encoding="utf-8")
old = '    ("Қонаев", "Конаев", 43.87, 77.07),\n]'
if old not in s:
    raise SystemExit("!! не нашёл конец списка городов (строку с Қонаев)")
s = s.replace(old, '    ("Қонаев", "Конаев", 43.87, 77.07),\n'
                   '    ("Талғар", "Талгар", 43.30, 77.24),        # попросили в комментариях (4.11.2026)\n]', 1)
s = s.replace("cities  — 20 городов Казахстана", "cities  — 21 город Казахстана")
s = s.replace("# ---------- 20 городов ----------", "# ---------- 21 город (Талғар добавлен по просьбе зрителей) ----------")
s = s.replace("Жиырма қала — бір мәре!", "Жиырма бір қала — бір мәре!")
s = s.replace("20 городов Казахстана в одной гонке.", "21 город Казахстана в одной гонке.")
p.write_text(s, encoding="utf-8")
EOF

"$PY" -m py_compile race_leagues.py || restore
N=$("$PY" -c "import race_leagues as RL; print(len(RL.entries('cities')))") || restore
[ "$N" = "21" ] || { echo "!! городов $N, а должно быть 21"; restore; }
"$PY" race_video.py --check || restore

echo
echo "== Готово: Талгар добавлен, в гонке городов теперь 21 город."
echo "   Появится в следующем заезде городов (12:00 или 18:00 по Астане)."
echo "   Выложить гонку городов прямо сейчас:  srv race cities"
