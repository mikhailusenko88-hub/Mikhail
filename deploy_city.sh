#!/bin/bash
# «Білесің бе?»: добавить города в гонку «Қай қала жеңеді?» по просьбам из комментариев.
#   Талғар (4.11.2026) и Жаркент (5.11.2026) → 22 города.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_city.sh | bash
# Безопасно: делает копии race_leagues.py / race_video.py (.bak-ДАТА), при любой ошибке возвращает как было.
# Повторный запуск ничего не ломает: если города уже есть — так и скажет.
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

cp -p race_leagues.py "race_leagues.py.bak-$STAMP"
cp -p race_video.py "race_video.py.bak-$STAMP"
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "race_leagues.py.bak-$STAMP" race_leagues.py
  cp -p "race_video.py.bak-$STAMP" race_video.py
  exit 1
}

echo "== Добавляю города"
"$PY" - <<'EOF' || restore
import re
from pathlib import Path

NEW = [
    ('    ("Талғар", "Талгар", 43.30, 77.24),        # попросили в комментариях (4.11.2026)', '"Талғар"'),
    ('    ("Жаркент", "Жаркент", 44.17, 80.00),      # попросили в комментариях (5.11.2026)', '"Жаркент"'),
]
KK = {20: "Жиырма", 21: "Жиырма бір", 22: "Жиырма екі", 23: "Жиырма үш", 24: "Жиырма төрт", 25: "Жиырма бес"}
def ru(n):
    w = "город" if n % 10 == 1 and n % 100 != 11 else ("города" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "городов")
    return f"{n} {w}"

# --- race_leagues.py: список городов ---
p = Path("race_leagues.py")
s = p.read_text(encoding="utf-8")
m = re.search(r"\nCITIES = \[\n(.*?)\n\]", s, re.S)
if not m:
    raise SystemExit("!! не нашёл список городов CITIES")
body = m.group(1)
for line, key in NEW:
    if key in body:
        print(f"   {key.strip(chr(34))} — уже в списке")
    else:
        body += "\n" + line
        print(f"   + {key.strip(chr(34))}")
s = s[:m.start(1)] + body + s[m.end(1):]
n = sum(1 for ln in body.splitlines() if ln.strip().startswith('("'))
# надписи с числом городов
s = re.sub(r"cities  — \d+ город\w* Казахстана", f"cities  — {ru(n)} Казахстана", s)
s = re.sub(r"# ---------- \d+ город\w*[^\n]*----------",
           f"# ---------- {ru(n)} (Талғар и Жаркент добавлены по просьбе зрителей) ----------", s, count=1)
s = re.sub(r"Жиырма(?: [а-яәғқңөұүһі]+)? қала — бір мәре!", f"{KK.get(n, 'Жиырма')} қала — бір мәре!", s)
s = re.sub(r"\d+ город\w* Казахстана в одной гонке\.", f"{ru(n)} Казахстана в одной гонке.", s)
p.write_text(s, encoding="utf-8")
print(f"   городов теперь: {n}")

# --- race_video.py: стартовая решётка была ровно на 21 шарик (3 ряда по 7) ---
v = Path("race_video.py")
t = v.read_text(encoding="utf-8")
old = "        self.start = [(60 + c * 76 + (38 if r_ % 2 else 0), 50 + r_ * 48) for r_ in range(3) for c in range(7)][:n]\n"
new = ("        if n <= 21:     # как было: 3 ряда по 7\n"
       "            self.start = [(60 + c * 76 + (38 if r_ % 2 else 0), 50 + r_ * 48) for r_ in range(3) for c in range(7)][:n]\n"
       "        else:           # городов больше 21 (просят в комментариях) — те же 3 ряда, но плотнее\n"
       "            cols = math.ceil(n / 3)\n"
       "            sp = min(76.0, (CW - 90) / (cols - 0.5))\n"
       "            self.start = [(45 + c * sp + (sp / 2 if r_ % 2 else 0), 50 + r_ * 48)\n"
       "                          for r_ in range(3) for c in range(cols)][:n]\n")
if "городов больше 21" in t:
    print("   старт на 22+ шарика — уже есть")
elif old in t:
    t = t.replace(old, new, 1)
    v.write_text(t, encoding="utf-8")
    print("   старт расширен под 22+ шарика")
else:
    raise SystemExit("!! не нашёл строку старта в race_video.py")
EOF

"$PY" -m py_compile race_leagues.py race_video.py || restore
N=$("$PY" -c "import race_leagues as RL; print(len(RL.entries('cities')))") || restore
[ "$N" -ge 22 ] || { echo "!! городов $N, а должно быть 22"; restore; }
"$PY" race_video.py --check || restore

echo
echo "== Готово: городов в гонке теперь — $N (Жаркент — №22)."
echo "   Появится в следующем заезде городов (12:00 или 18:00 по Астане)."
echo "   Выложить гонку городов прямо сейчас:  srv race cities"
