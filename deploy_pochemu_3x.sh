#!/bin/bash
# «Почему так?»: 3 ролика в день — 13:00, 17:00 и 21:00 по Астане (11:00, 15:00, 19:00 по Москве)
# и сразу выпустить один ролик сейчас.
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_pochemu_3x.sh | bash
# Другое время:  ... | TIMES="12:00 16:00 21:00" bash      Без ролика сейчас:  ... | NOW=0 bash
# Безопасно: копия расписания /root/crontab.bak-ДАТА. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
TIMES=${TIMES:-"13:00 17:00 21:00"}
NOW=${NOW:-1}

echo "== Ищу бота «Почему так?»…"
D=""
while read -r f; do
  d=$(dirname "$f")
  [ -f "$d/config.json" ] && [ -f "$d/run_daily.py" ] || continue
  L=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$d/config.json" 2>/dev/null || echo ru)
  [ "$L" = "kk" ] && continue
  python3 -c "import json,sys;sys.exit(0 if json.load(open(sys.argv[1],encoding='utf-8')).get('mode')=='race' else 1)" "$d/config.json" 2>/dev/null && continue
  D="$d"; break
done < <(find / -xdev -name make_video.py -not -path '/proc/*' -not -path '*/.git/*' -not -path '*/.bak*' 2>/dev/null | sort)
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Почему так?»"; exit 1; }
echo "   бот: $D"
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

echo
echo "== Расписание: $TIMES по Астане"
crontab -l > "/root/crontab.bak-$STAMP" 2>/dev/null || true
python3 - "$D" "$TIMES" <<'PY'
import re, subprocess, sys, time
d, times = sys.argv[1], [tuple(map(int, t.split(":"))) for t in sys.argv[2].split()]
off = time.localtime().tm_gmtoff // 60                 # часы сервера относительно UTC, мин
def srv(h, m):                                         # Астана = UTC+5
    t = (h * 60 + m - 300 + off) % 1440
    return t // 60, t % 60
lines = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
pat = re.compile(re.escape(d) + r"(?=[/\s;&|)'\"]|$)")
idx = [i for i, l in enumerate(lines) if not l.lstrip().startswith("#") and "run_daily" in l and pat.search(l)]
if not idx:
    print("!! в crontab нет запуска «Почему так?». Пришли вывод:  crontab -l"); sys.exit(1)
l = lines[idx[0]].strip()
p = l.split()
cmd = l.split(None, 1)[1] if p[0].startswith("@") else l.split(None, 5)[5]
print("   было:", "; ".join(" ".join(lines[i].split()[:5]) for i in idx), "(cron, часы сервера)")
drop = set(idx) | {i - 1 for i in idx if i > 0 and lines[i - 1].startswith("# Почему так?:")}
first = min(drop)
new = [f"# Почему так?: {len(times)} раза в день (по Астане {', '.join('%02d:%02d' % t for t in times)})"]
for h, m in times:
    sh, sm = srv(h, m)
    new.append(f"{sm} {sh} * * * {cmd}")
out = lines[:first] + new + [x for i, x in enumerate(lines) if i > first and i not in drop]
if subprocess.run(["crontab", "-"], input="\n".join(out) + "\n", text=True).returncode:
    print("!! crontab не принял — старое расписание не тронуто"); sys.exit(1)
print("   стало:", ", ".join("%02d:%02d" % t for t in times), "по Астане =",
      ", ".join("%02d:%02d" % ((h - 2) % 24, m) for h, m in times), "по Москве")
PY
[ $? -eq 0 ] || exit 1
echo "   копия старого: /root/crontab.bak-$STAMP"
crontab -l | grep -A3 "^# Почему так?"

# квота YouTube: 1 загрузка = 1600 из 10000 в сутки на проект Google Cloud
Q=$(ls "$D"/yt_queue/*.mp4 2>/dev/null | wc -l)
[ "$Q" -gt 0 ] && echo "   ! в очереди yt_queue $Q роликов — каждый запуск выкладывает ещё и 1 из очереди (2 загрузки за раз)"

if [ "$NOW" = "1" ]; then
  echo
  echo "== Выпускаю ролик прямо сейчас (сборка ~1–2 мин, потом загрузка на YouTube)…"
  cd "$D" || exit 1
  START=$(wc -l < bot.log 2>/dev/null || echo 0)
  setsid nohup "$PY" run_daily.py >> "$D/now-$STAMP.out" 2>&1 < /dev/null &
  PID=$!
  for i in $(seq 1 30); do                       # ждём до 5 минут
    sleep 10
    NEWL=$(tail -n +"$((START + 1))" bot.log 2>/dev/null)
    echo "$NEWL" | grep -q "YouTube:\|Сбой\|Уже идёт\|не выложен" && break
  done
  echo "--- журнал этого запуска:"
  tail -n +"$((START + 1))" bot.log 2>/dev/null | tail -n 12
  kill -0 "$PID" 2>/dev/null && echo "   (ещё работает в фоне — доделает сам, проверить: tail -5 $D/bot.log)"
fi
echo
echo "== Готово."
