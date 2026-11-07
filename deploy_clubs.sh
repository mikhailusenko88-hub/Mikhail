#!/bin/bash
# «Білесің бе?»: новая тема дня — «Қай клуб жеңеді?» (20 футбольных клубов Казахстана, шарик в цвете клуба).
# Темы по очереди: мүшел → регионы → имена → ру → клубы. Сезон у клубов — месяц (финал в последний заезд темы).
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_clubs.sh | bash
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
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

FILES="race_video.py race_bot.py race_leagues.py"
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
curl -fsSL "$RAW/srv?$STAMP" -o /usr/local/bin/srv.new && chmod +x /usr/local/bin/srv.new \
  && mv /usr/local/bin/srv.new /usr/local/bin/srv
"$PY" -m py_compile $FILES || restore

echo "== Проверка физики (несколько секунд)"
"$PY" race_video.py --check || restore

echo "== Настройки: клубы в очередь тем дня"
"$PY" - <<'PY' || restore
import json
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
th = cfg.get("theme_leagues") or ["mushel", "regions", "names", "ru"]
if "clubs" not in th:
    th.append("clubs")
cfg["theme_leagues"] = th
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   темы дня по очереди: " + " → ".join(th))
PY

echo
echo "== Готово. Клубы выйдут в свою очередь в 15:00 по Астане."
echo "   Выложить гонку клубов прямо сейчас:  srv race clubs"
echo "   Последние заезды:  srv bot"
