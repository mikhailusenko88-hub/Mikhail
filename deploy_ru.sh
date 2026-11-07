#!/bin/bash
# «Білесің бе?»: новая тема дня — «Қай ру жеңеді? Какой род победит?» (19 руов трёх жузов).
# Попросили зрители в комментариях. Тема встаёт в очередь тем дня: мүшел → регионы → имена → ру.
# Запуск на сервере:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_ru.sh | bash
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}

D=""
for c in /root/kz-bot; do [ -f "$c/run_daily.py" ] && [ -f "$c/config.json" ] && D="$c"; done
[ -n "$D" ] || { echo "!! Не нашёл папку бота /root/kz-bot"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

FILES="race_leagues.py race_video.py race_bot.py"
cp -p config.json "config.json.bak-$STAMP"
for f in $FILES; do [ -f "$f" ] && cp -p "$f" "$f.bak-$STAMP"; done
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "config.json.bak-$STAMP" config.json
  for f in $FILES; do [ -f "$f.bak-$STAMP" ] && cp -p "$f.bak-$STAMP" "$f"; done
  exit 1
}

echo "== Скачиваю"
for f in $FILES; do
  curl -fsSL "$RAW/$f?$STAMP" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
done
"$PY" -m py_compile $FILES || restore

echo "== Проверка физики"
"$PY" race_video.py --check || restore

echo "== Тема «ру» в очереди тем дня"
"$PY" - <<'PY' || restore
import json
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
th = cfg.get("theme_leagues") or ["mushel", "regions", "names"]
if "ru" not in th:
    th.append("ru")
cfg["theme_leagues"] = th
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   темы дня (15:00 по Астане): " + " → ".join(th))
PY

echo
echo "== Готово. Первую гонку родов можно выложить прямо сейчас:  srv race ru"
