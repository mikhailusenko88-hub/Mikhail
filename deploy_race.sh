#!/bin/bash
# «Білесің бе?»: новый формат «Қай қала жеңеді?» — гонка шариков 20 городов Казахстана.
# Запуск на сервере:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_race.sh | bash
# Вернуть старые ролики-факты:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_race.sh | bash -s -- --back
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
BACK=0; [ "${1:-}" = "--back" ] && BACK=1

echo "== Ищу бота «Білесің бе?»…"
D=""
while read -r f; do
  d=$(dirname "$f")
  [ -f "$d/config.json" ] && [ -f "$d/run_daily.py" ] || continue
  L=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$d/config.json" 2>/dev/null)
  [ "$L" = "kk" ] && D="$d" && break
done < <(find "${SEARCH_ROOT:-/}" -xdev -name make_video.py -not -path '*/proc/*' -not -path '*/.git/*' \
         -not -path '*/node_modules/*' 2>/dev/null)
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Білесің бе?»"; exit 1; }
echo "   $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

set_mode() {
  "$PY" - "$1" <<'PY'
import json, sys
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
cfg["mode"] = sys.argv[1]
if sys.argv[1] == "race":
    cfg["youtube_category_id"] = "24"
    cfg["yt_extra_tags"] = ["қазақстан", "казахстан", "жарыс", "marble race"]
else:
    cfg["youtube_category_id"] = "27"
    cfg["yt_extra_tags"] = ["білесің бе", "қазақша", "қызық деректер", "казахстан", "интересные факты"]
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   режим:", "гонка городов «Қай қала жеңеді?»" if sys.argv[1] == "race" else "старые ролики-факты")
PY
}

if [ $BACK = 1 ]; then
  cp -p config.json "config.json.bak-$STAMP"; set_mode facts; echo "== Готово, со следующего запуска — старые ролики."; exit 0
fi

echo "== Копии файлов (*.bak-$STAMP)"
cp -p config.json "config.json.bak-$STAMP"
cp -p run_daily.py "run_daily.py.bak-$STAMP"
restore() { echo "!! Ошибка — возвращаю как было"; cp -p "config.json.bak-$STAMP" config.json; cp -p "run_daily.py.bak-$STAMP" run_daily.py; exit 1; }

echo "== Скачиваю новый формат"
mkdir -p fonts
for f in race_video.py race_bot.py kz_outline.json fonts/DejaVuSans-Bold.ttf; do
  curl -fsSL "$RAW/$f" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
  echo "   $f"
done

echo "== numpy для физики"
if ! "$PY" -c "import numpy" 2>/dev/null; then
  "$PY" -m pip install -q numpy || pip3 install -q numpy || { echo "!! не поставился numpy"; restore; }
fi
"$PY" -c "import numpy; print('   numpy', numpy.__version__)" || restore

echo "== Подключаю режим гонки в run_daily.py"
"$PY" - <<'PY' || restore
from pathlib import Path
r = Path("run_daily.py")
s = r.read_text(encoding="utf-8")
if 'race_bot.run(' in s:
    print("   уже подключено")
else:
    old = 'def main():\n    load_env()\n'
    if old not in s:
        raise SystemExit("не нашёл def main() в run_daily.py")
    new = old + ('    _cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))\n'
                 '    if _cfg.get("mode") == "race":  # «Қай қала жеңеді?» — гонка городов (race_bot.py)\n'
                 '        import race_bot\n'
                 '        return race_bot.run(BASE, _cfg, log, notify, "--test" in sys.argv, "--no-youtube" in sys.argv)\n')
    r.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("   готово")
PY
"$PY" -m py_compile run_daily.py race_bot.py race_video.py || restore
set_mode race || restore

echo "== Пробный ролик (ничего не выкладывается, 1–3 минуты)…"
if "$PY" run_daily.py --test; then
  echo
  echo "== Всё готово. Новые ролики пойдут по старому расписанию (12:00 и 18:00 по Астане)."
  ls -t out/*race*.mp4 2>/dev/null | head -1 | sed 's/^/   пробный ролик: /'
else
  echo "!! Пробный ролик не собрался — возвращаю старый режим"; restore
fi
