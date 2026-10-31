#!/bin/bash
# Боты роликов: выкладка 2 раза в день (время Астаны/Алматы, UTC+5)
#   «Білесің бе?»  — 12:00 и 18:00
#   «Почему так?»  — 13:00 и 19:00
# Плюс для «Білесің бе?»: только рубрики-факты (без «слова дня» и пословиц),
# название на YouTube только на казахском.
# Запуск на сервере:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_2x.sh | bash
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает назад. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)

echo "== Ищу боты (папки с make_video.py и config.json)…"
mapfile -t DIRS < <(find "${SEARCH_ROOT:-/}" -xdev -name make_video.py -not -path '*/proc/*' -not -path '*/.git/*' \
                    -not -path '*/node_modules/*' -not -path '*/music_tmp/*' 2>/dev/null | xargs -r -n1 dirname | sort -u)
BOTS=""
for D in "${DIRS[@]}"; do
  [ -f "$D/config.json" ] && [ -f "$D/run_daily.py" ] || continue
  LANG_=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$D/config.json" 2>/dev/null || echo ru)
  if [ "$LANG_" = "kk" ]; then KIND=kz; else KIND=ru; fi
  echo "   $D  → $([ $KIND = kz ] && echo 'Білесің бе?' || echo 'Почему так?')"
  BOTS="$BOTS $D:$KIND"

  if [ $KIND = kz ]; then
    cp -p "$D/config.json" "$D/config.json.bak-$STAMP"
    cp -p "$D/run_daily.py" "$D/run_daily.py.bak-$STAMP"
    cp -p "$D/make_video.py" "$D/make_video.py.bak-$STAMP"
    python3 - "$D" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
cp = d / "config.json"
cfg = json.loads(cp.read_text(encoding="utf-8"))
cfg["formats"] = ["Білесің бе?", "Аңыз ба, шындық па?", "Топ-3", "Қай қала?"]
cfg["yt_title_ru"] = False
cp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("   config: рубрики —", ", ".join(cfg["formats"]))

r = d / "run_daily.py"
s = r.read_text(encoding="utf-8")
old = 'yt_title = script["title"] + (" | " + script["title_ru"] if script.get("title_ru") else "")'
new = 'yt_title = script["title"] + (" | " + script["title_ru"] if script.get("title_ru") and cfg.get("yt_title_ru", True) else "")'
if 'cfg.get("yt_title_ru"' in s:
    print("   код: название только на казахском — уже есть")
elif old in s:
    r.write_text(s.replace(old, new), encoding="utf-8"); print("   код: название на YouTube только на казахском")
else:
    print("   ! код: не нашёл строку названия — название останется двуязычным")

m = d / "make_video.py"
s = m.read_text(encoding="utf-8")
old = '    fresh = [s for s in bank if s["title"] not in used_titles] or bank\n    formats = (cfg or {}).get("formats") or []\n'
new = old + '    if formats:  # только рубрики из config.json (остальные отключены)\n        fresh = [s for s in fresh if s.get("format") in formats] or fresh\n'
if "остальные отключены" in s:
    print("   код: фильтр рубрик — уже есть")
elif old in s:
    m.write_text(s.replace(old, new), encoding="utf-8"); print("   код: отключённые рубрики больше не выбираются")
else:
    print("   ! код: не нашёл выбор сценария — фильтр рубрик не добавлен")
PY
    RC=$?
    if [ $RC -ne 0 ] || ! python3 -m py_compile "$D/run_daily.py" "$D/make_video.py" \
       || ! python3 -c "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))" "$D/config.json"; then
      echo "   ! ошибка — возвращаю копии назад"
      for f in config.json run_daily.py make_video.py; do cp -p "$D/$f.bak-$STAMP" "$D/$f"; done
    fi
  fi
done
[ -n "$BOTS" ] || { echo "!! Не нашёл ни одного бота."; exit 1; }

echo
echo "== Расписание (cron)"
crontab -l > "/root/crontab.bak-$STAMP" 2>/dev/null || true
python3 - "$STAMP" $BOTS <<'PY'
import re, subprocess, sys, time
stamp, bots = sys.argv[1], [b.rsplit(":", 1) for b in sys.argv[2:]]
TIMES = {"kz": [(12, 0), (18, 0)], "ru": [(13, 0), (19, 0)]}   # время Астаны/Алматы
NAMES = {"kz": "Білесің бе?", "ru": "Почему так?"}
off = time.localtime().tm_gmtoff // 60          # смещение часов сервера от UTC, мин
def server_time(h, m):                          # Астана = UTC+5
    t = (h * 60 + m - 300 + off) % 1440
    return t // 60, t % 60
print(f"   часовой пояс сервера: UTC{off/60:+g} (время ниже — по Астане)")

try:
    lines = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.splitlines()
except FileNotFoundError:
    print("!! на сервере нет crontab"); sys.exit(1)

out, done = lines[:], []
for d, kind in bots:
    pat = re.compile(re.escape(d) + r"(?=[/\s;&|)'\"]|$)")
    idx = [i for i, l in enumerate(out) if not l.lstrip().startswith("#") and "run_daily" in l and pat.search(l)]
    if not idx:
        print(f"   ! {NAMES[kind]}: в crontab нет строки запуска для {d} — пропускаю")
        continue
    l = out[idx[0]].strip()
    parts = l.split()
    cmd = l.split(None, 1)[1] if parts[0].startswith("@") else l.split(None, 5)[5]
    new = [f"# {NAMES[kind]}: 2 раза в день (по Астане {', '.join('%02d:%02d' % t for t in TIMES[kind])})"]
    for h, m in TIMES[kind]:
        sh, sm = server_time(h, m)
        new.append(f"{sm} {sh} * * * {cmd}")
    marker = f"# {NAMES[kind]}: 2 раза"
    drop = set(idx) | {i - 1 for i in idx if i > 0 and out[i - 1].startswith(marker)}
    first = min(drop)
    out = out[:first] + new + [l for i, l in enumerate(out) if i > first and i not in drop]
    done.append(kind)
    print(f"   {NAMES[kind]}: было «{' '.join(parts[:1] if parts[0].startswith('@') else parts[:5])}», "
          f"стало {' и '.join('%02d:%02d' % t for t in TIMES[kind])} по Астане")

if done:
    r = subprocess.run(["crontab", "-"], input="\n".join(out) + "\n", text=True)
    if r.returncode:
        print("!! crontab не принял изменения — старое расписание не тронуто"); sys.exit(1)
    print(f"   копия старого расписания: /root/crontab.bak-{stamp}")
else:
    print("!! Расписание не изменено. Пришли вывод команды:  crontab -l ; ls /etc/cron.d ; systemctl list-timers")
PY
echo
echo "== Сейчас в crontab:"
crontab -l 2>/dev/null | grep -B1 run_daily
echo
echo "== Готово."
