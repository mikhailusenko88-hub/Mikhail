#!/bin/bash
# «Білесің бе?»: 3 гонки в день — города 12:00 и 18:00, тема дня 15:00 (по Астане).
# Темы по очереди: мүшел → регионы по кодам номеров 01–20 → имена (мальчики vs девочки).
# Трасса длиннее (~1 мин), новые препятствия: туннели, лестницы, кочки, батуты, молоты, развилки.
# Сезоны: города — неделя (финал в воскресенье 18:00), темы — месяц (финал в последний заезд темы
# в месяце). Чемпион получает звезду ★, история чемпионов хранится всегда.
# Запуск на сервере:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_leagues.sh | bash
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}

D=""
for c in /root/kz-bot; do [ -f "$c/run_daily.py" ] && [ -f "$c/config.json" ] && D="$c"; done
if [ -z "$D" ]; then
  while read -r f; do
    d=$(dirname "$f")
    [ -f "$d/config.json" ] && [ -f "$d/run_daily.py" ] || continue
    L=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$d/config.json" 2>/dev/null)
    [ "$L" = "kk" ] && D="$d" && break
  done < <(find / -xdev -name run_daily.py -not -path '/proc/*' -not -path '*/.git/*' 2>/dev/null)
fi
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Білесің бе?»"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

FILES="race_video.py race_bot.py race_leagues.py"
cp -p config.json "config.json.bak-$STAMP"
for f in $FILES; do [ -f "$f" ] && cp -p "$f" "$f.bak-$STAMP"; done
crontab -l > "crontab.bak-$STAMP" 2>/dev/null || true
restore() {
  echo "!! Ошибка — возвращаю как было"
  cp -p "config.json.bak-$STAMP" config.json
  for f in $FILES; do
    if [ -f "$f.bak-$STAMP" ]; then cp -p "$f.bak-$STAMP" "$f"; else rm -f "$f"; fi
  done
  [ -s "crontab.bak-$STAMP" ] && crontab "crontab.bak-$STAMP"
  exit 1
}

echo "== Скачиваю"
for f in $FILES; do
  curl -fsSL "$RAW/$f?$STAMP" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
done
curl -fsSL "$RAW/srv?$STAMP" -o /usr/local/bin/srv.new && chmod +x /usr/local/bin/srv.new \
  && mv /usr/local/bin/srv.new /usr/local/bin/srv
"$PY" -m py_compile $FILES || restore
grep -q 'race_bot.run(' run_daily.py || { echo "!! run_daily.py без режима гонки — сначала deploy_race.sh"; restore; }

echo "== Проверка физики (несколько секунд)"
"$PY" race_video.py --check || restore

echo "== Настройки"
"$PY" - <<'PY' || restore
import json
from pathlib import Path
cp = Path("config.json")
cfg = json.loads(cp.read_text(encoding="utf-8"))
cfg["mode"] = "race"
cfg["race_slots"] = {"12": "cities", "15": "theme", "18": "cities"}
cfg.setdefault("theme_leagues", ["mushel", "regions", "names"])
cfg.setdefault("first_comment", True)
cfg.setdefault("read_comments", True)
cfg["youtube_category_id"] = "24"
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   12:00 города · 15:00 тема дня (" + " → ".join(cfg["theme_leagues"]) + ") · 18:00 города")
PY

echo "== Расписание: 3 раза в день"
"$PY" - "$D" <<'PY' || restore
import re, subprocess, sys, time
d = sys.argv[1]
TIMES = [(12, 0), (15, 0), (18, 0)]                 # по Астане (UTC+5)
off = time.localtime().tm_gmtoff // 60
def server_time(h, m):
    t = (h * 60 + m - 300 + off) % 1440
    return t // 60, t % 60
lines = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
pat = re.compile(re.escape(d) + r"(?=[/\s;&|)'\"]|$)")
idx = [i for i, l in enumerate(lines) if not l.lstrip().startswith("#") and "run_daily" in l and pat.search(l)]
if not idx:
    sys.exit("!! в crontab нет строки запуска бота — расписание не трогаю")
l = lines[idx[0]].strip()
cmd = l.split(None, 1)[1] if l.split()[0].startswith("@") else l.split(None, 5)[5]
cmd = re.sub(r"\s--league\s+\S+", "", cmd)
new = ["# Білесің бе?: 3 раза в день (по Астане 12:00 города, 15:00 тема дня, 18:00 города)"]
for h, m in TIMES:
    sh, sm = server_time(h, m)
    new.append(f"{sm} {sh} * * * {cmd}")
drop = set(idx) | {i - 1 for i in idx if i > 0 and lines[i - 1].startswith("# Білесің бе?")}
first = min(drop)
out = lines[:first] + new + [x for i, x in enumerate(lines) if i > first and i not in drop]
r = subprocess.run(["crontab", "-"], input="\n".join(out) + "\n", text=True)
if r.returncode:
    sys.exit("!! crontab не принял изменения")
print("   готово: 12:00, 15:00, 18:00 по Астане")
PY

echo
echo "== Всё готово. Следующая тема дня — завтра в 15:00 по Астане."
echo "   Выложить тему прямо сейчас:  srv race mushel   (или regions / names / cities)"
echo "   Последние заезды:  srv bot"
