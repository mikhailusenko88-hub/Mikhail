#!/bin/bash
# «Білесің бе?» (18.11.2026, по «да» Михаила): в 18:00 Астаны (16:00 МСК) вместо гонки 12 городов — второй «1000 шарик».
#   Почему: гонка 12 городов в 18:00 Астаны 16 и 17.11 — 7 и 2 просмотра, «1000 шарик» в 12:00 — 770 и 578 за сутки.
#   Расписание (Астана): 12:00 — «1000 шарик», 15:00 — тема дня (мүшел / имена), 18:00 — «1000 шарик».
#   У каждого «1000 шарик» свои 10 городов (Алматы, Астана, Шымкент всегда), своя трасса, цвет и музыка.
#   Гонок городов за неделю больше нет — поэтому и в воскресенье в 18:00 выйдет «1000 шарик», а не финал недели.
#   Если «1000 шарик» почему-то не соберётся — как и раньше, выйдет гонка городов (слот не пропадает).
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL --max-time 40 https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_mass2.sh | bash
# Вернуть гонку городов в 18:00:  ... | bash -s -- --back
set -u
D=${D:-/root/kz-bot}
[ -f "$D/config.json" ] && [ -f "$D/race_bot.py" ] || { echo "!! Нет папки бота $D"; echo "НЕ ВСТАЛО"; exit 1; }
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"
grep -q "def run_mass" race_bot.py && [ -x mass/mass_sim ] || { echo "!! «1000 шарик» на сервере не стоит"; echo "НЕ ВСТАЛО"; exit 1; }
if pgrep -f "run_daily.py" >/dev/null; then echo "Бот прямо сейчас делает ролик — запусти эту команду через 5 минут"; exit 0; fi

SLOT=mass; [ "${1:-}" = "--back" ] && SLOT=cities
cp -p config.json config.json.bak-mass2

echo "== Расписание"
"$PY" - "$SLOT" <<'PY' || { cp -p config.json.bak-mass2 config.json; echo "НЕ ВСТАЛО (ничего не поменял)"; exit 1; }
import json, sys
slot = sys.argv[1]
c = json.load(open("config.json", encoding="utf-8"))
s = dict(c.get("race_slots") or {})
if s.get("12") != "mass":
    sys.exit("!! сейчас в 12:00 не «1000 шарик»: " + json.dumps(s, ensure_ascii=False))
s["18"] = slot
c["race_slots"] = s
json.dump(c, open("config.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
names = {"mass": "«1000 шарик»", "theme": "тема дня", "cities": "гонка городов"}
for h in sorted(s, key=int):
    print(f"   {h}:00 Астаны ({int(h) - 2:02d}:00 МСК) — {names.get(s[h], s[h])}")
PY

"$PY" -c "import json; json.load(open('config.json', encoding='utf-8'))" || { cp -p config.json.bak-mass2 config.json; echo "НЕ ВСТАЛО (ничего не поменял)"; exit 1; }
echo
if [ "$SLOT" = mass ]; then
  echo "== Готово. Ближайший слот 18:00 Астаны (16:00 МСК) — второй «1000 шарик»."
  echo "   Вернуть гонку городов: та же команда с  -s -- --back  после bash"
else
  echo "== Готово: в 18:00 Астаны снова гонка городов."
fi
