#!/bin/bash
# «Почему так»: новый вид роликов (v2) — крючок с первой секунды, рисованная картинка по теме,
# ролики 15–20 с, концовка «А ты это знал? ДА / НЕТ», сценарии по формулам «Самый жуткий…», «Вот почему нельзя…»,
# «Никогда не…», «Хватит верить…». Запасной банк — 33 новых сценария (topics_ru_v2.json).
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_pochemu_v2.sh | bash
# Безопасно: копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
# Вернуть старый вид: в config.json поставить "style": "v1".
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}

echo "== Ищу бота «Почему так» (make_video.py + config.json, lang не kk)…"
D=""
while read -r f; do
  d=$(dirname "$f")
  [ -f "$d/config.json" ] && [ -f "$d/run_daily.py" ] || continue
  L=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$d/config.json" 2>/dev/null || echo ru)
  [ "$L" = "kk" ] && continue
  D="$d"; break
done < <(find / -xdev -name make_video.py -not -path '/proc/*' -not -path '*/.git/*' -not -path '*/.bak*' 2>/dev/null)
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Почему так»"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

FILES="make_video.py icons.py topics_ru_v2.json"
cp -p config.json "config.json.bak-$STAMP"
for f in $FILES; do [ -f "$f" ] && cp -p "$f" "$f.bak-$STAMP"; done
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "config.json.bak-$STAMP" config.json
  for f in $FILES; do
    if [ -f "$f.bak-$STAMP" ]; then cp -p "$f.bak-$STAMP" "$f"; else rm -f "$f"; fi
  done
  exit 1
}

echo "== Скачиваю"
for f in $FILES; do
  curl -fsSL "$RAW/$f?$STAMP" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
done
"$PY" -m py_compile make_video.py icons.py || restore

echo "== Настройки"
"$PY" - <<'PY' || restore
import json
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
old = {k: cfg.get(k) for k in ("style", "formats", "bank_file", "use_ai", "use_stock_video", "voice_rate", "post_to_youtube", "post_to_vk", "channel_handle")}
cfg["style"] = "v2"
cfg["max_lines"] = 5
cfg["voice_rate_v2"] = "+8%"
cfg["formats"] = ["Жуткий факт", "Нельзя", "Миф или правда", "Самый"]
cfg["subtopics"] = ["космос: жуть и масштаб", "тело человека и смерть", "опасные животные", "еда и химия: что нельзя смешивать",
                    "опасные места и рекорды Земли", "шокирующая история", "мифы, в которые верят все", "сон и мозг"]
cfg["bank_file"] = "topics_ru_v2.json"
cfg["use_stock_video"] = False
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   было:", json.dumps(old, ensure_ascii=False))
print("   стало: style=v2, рубрики:", " / ".join(cfg["formats"]), "| банк: topics_ru_v2.json | ИИ-сценарии:", cfg.get("use_ai"))
PY

echo "== Пробная сборка (без выкладки, ~1 мин)"
"$PY" run_daily.py --test 2>&1 | tail -6 || restore
LAST=$(ls -t out/*.mp4 2>/dev/null | head -1)
if [ -n "$LAST" ]; then
  echo "   ролик: $LAST"
  ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$LAST" | awk '{printf "   длина: %.0f с\n",$1}'
else
  echo "!! тестовый ролик не собрался — смотри bot.log"; restore
fi

echo
echo "== Готово. Следующий ролик по расписанию выйдет уже в новом виде."
echo "   Выложить прямо сейчас:  cd $D && $PY run_daily.py"
echo "   Вернуть старый вид:     в $D/config.json поставить \"style\": \"v1\""
