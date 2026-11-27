#!/bin/bash
# «Почему так?» — гипотеза H49 (27.11.2026, «да» Михаила): в слоте 15:00 МСК — живые кадры вместо значка.
#   Фон — настоящие видеоклипы Pexels по теме (бесплатная лицензия, указывать автора не нужно),
#   на кадре — подпись 2–4 слова, голос Альбины, музыка и звуки — как сейчас. 7 роликов подряд, потом само выключится.
#   Нет ключа Pexels, нет клипов или любая ошибка — ролик выходит в обычном виде (значок), бот не ломается.
#   Ставит live.py, одну вставку в make_video.py (build → live при live_hours) и две настройки в config.json.
# Запуск на сервере (команда «Сервер» на iPhone):
#   RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/<коммит>; curl -fsSL --max-time 40 $RAW/deploy_pochemu_live.sh | RAW=$RAW bash 2>&1
# Ключ Pexels (если команда скажет «КЛЮЧА НЕТ»):  ... | RAW=$RAW bash -s -- --key ВАШ_КЛЮЧ 2>&1
# Вернуть как было:  ... | RAW=$RAW bash -s -- --back 2>&1
# Безопасно: всё скачивается и проверяется в стороне; прежний make_video.py хранится как make_video.py.bak-live;
# при любой ошибке возвращает назад и пишет «НЕ ВСТАЛО». Повторный запуск ничего не ломает.
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
TAG=bak-live
NDAYS=7
MARK="# --- живые кадры (H49)"

fail() { echo "!! $1"; echo "НЕ ВСТАЛО — на сервере ничего не изменено"; exit 1; }

# ---------- папка бота «Почему так?» ----------
is_bot() {
  [ -f "$1/make_video.py" ] && [ -f "$1/run_daily.py" ] && [ -f "$1/config.json" ] && [ -f "$1/topics_ru_v2.json" ] || return 1
  python3 -c "
import json, sys
c = json.load(open(sys.argv[1], encoding='utf-8'))
sys.exit(0 if c.get('bank_file') == 'topics_ru_v2.json' and c.get('lang', 'ru') != 'kk' and c.get('mode') != 'race' else 1)" "$1/config.json" 2>/dev/null
}
C=()
if [ -n "${BOT:-}" ]; then
  is_bot "${BOT%/}" && C=("${BOT%/}")
else
  for d in /root/*/ /opt/*/ /home/*/*/ /srv/*/; do d=${d%/}; is_bot "$d" && C+=("$d"); done
  if [ "${#C[@]}" -eq 0 ]; then
    while read -r f; do d=$(dirname "$f"); is_bot "$d" && C+=("$d"); done \
      < <(timeout 25 find / -xdev -maxdepth 6 -name topics_ru_v2.json -not -path '*/.git/*' -not -path '/tmp/*' \
            -not -path '/var/tmp/*' -not -path '/proc/*' -not -path '*.bak*' 2>/dev/null)
  fi
  if [ "${#C[@]}" -gt 1 ]; then
    CR=$(crontab -l 2>/dev/null | grep -v '^ *#' | grep run_daily)
    K=(); for d in "${C[@]}"; do echo "$CR" | grep -q "$d\(/\| \|$\)" && K+=("$d"); done
    [ "${#K[@]}" -eq 1 ] && C=("${K[@]}")
  fi
fi
[ "${#C[@]}" -eq 1 ] || fail "Не нашёл одну папку бота «Почему так?» (нашёл: ${C[*]:-ничего}). Пришли этот вывод Клоду."
D=${C[0]}
cd "$D" || fail "не открылась папка $D"
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

lock_bot() {
  [ "$(date +%M)" = "59" ] && { echo "Через минуту бот начнёт делать ролик — запусти эту команду ещё раз через 5 минут (ничего не изменено)"; exit 0; }
  exec 9>>"$D/.lock"
  if command -v flock >/dev/null; then
    flock -n 9 || { echo "Бот прямо сейчас делает ролик — запусти эту команду ещё раз через 5 минут (ничего не изменено)"; exit 0; }
  elif pgrep -f "run_daily.py" >/dev/null; then
    echo "Бот прямо сейчас делает ролик — запусти эту команду ещё раз через 5 минут (ничего не изменено)"; exit 0
  fi
}
unlock_bot() { command -v flock >/dev/null && flock -u 9; exec 9>&-; }

# ---------- ключ Pexels ----------
if [ "${1:-}" = "--key" ]; then
  KEY="${2:-}"
  [ ${#KEY} -ge 20 ] || fail "ключ короткий — скопируй его целиком со страницы pexels.com/api"
  touch .env && chmod 600 .env
  grep -v '^PEXELS_API_KEY=' .env > .env.tmp; echo "PEXELS_API_KEY=$KEY" >> .env.tmp; mv .env.tmp .env; chmod 600 .env
  echo "== Ключ записан в $D/.env"
  if [ -f live.py ]; then "$PY" live.py --check 2>&1 | sed 's/^/   /'; else echo "   (live.py ещё нет — запусти основную команду без --key)"; fi
  exit 0
fi

# ---------- вернуть как было ----------
if [ "${1:-}" = "--back" ]; then
  [ -f "make_video.py.$TAG" ] || fail "нет make_video.py.$TAG — возвращать нечего"
  lock_bot
  cp -p "make_video.py.$TAG" make_video.py || { echo "!! не вернулся make_video.py"; echo "НЕ ВСТАЛО"; exit 1; }
  "$PY" - <<'PY' || { echo "!! config.json не поправился"; echo "НЕ ВСТАЛО"; exit 1; }
import json
c = json.load(open("config.json", encoding="utf-8"))
for k in ("live_hours", "live_until"):
    c.pop(k, None)
open("config.json.tmp", "w", encoding="utf-8").write(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
json.load(open("config.json.tmp", encoding="utf-8"))
PY
  mv config.json.tmp config.json
  "$PY" -m py_compile make_video.py || { echo "!! прежний make_video.py не проверился"; echo "НЕ ВСТАЛО"; exit 1; }
  unlock_bot
  echo "== Готово: «Почему так?» снова везде со значком, живые кадры выключены. Бот: $D"
  exit 0
fi

# ---------- скачать и проверить в стороне ----------
grep -q "^def build_v2" make_video.py && grep -q "^def build(" make_video.py || fail "make_video.py на сервере не того вида (нет build_v2) — пришли вывод Клоду"
T=$(mktemp -d) || fail "нет временной папки"
trap 'rm -rf "$T"' EXIT
echo "== Скачиваю (бот: $D)"
curl -fsSL --connect-timeout 10 --max-time 40 "$RAW/live.py" -o "$T/live.py" || fail "не скачался live.py"
grep -q "^def build_live" "$T/live.py" || fail "скачался не тот live.py"
"$PY" -m py_compile "$T/live.py" || fail "в скачанном live.py ошибка"

# ---------- поставить ----------
lock_bot
[ -f "make_video.py.$TAG" ] || cp -p make_video.py "make_video.py.$TAG" || fail "не сохранилась копия make_video.py"
cp -p make_video.py make_video.py.prevl && cp -p config.json config.json.prevl || fail "не сохранились копии"
restore() {
  echo "!! $1 — возвращаю как было"
  cp -p make_video.py.prevl make_video.py; cp -p config.json.prevl config.json
  rm -f make_video.py.prevl config.json.prevl config.json.tmp
  echo "НЕ ВСТАЛО — на сервере всё как было"; exit 1
}
cp "$T/live.py" live.py.newl && mv live.py.newl live.py || restore "не записался live.py"
"$PY" - "$MARK" <<'PY' || restore "не получилось вставить живые кадры в make_video.py"
import re, sys
mark = sys.argv[1]
s = open("make_video.py", encoding="utf-8").read()
if mark in s:
    print("   код: вставка уже есть")
    sys.exit(0)
m = list(re.finditer(r"^def build\(script, cfg, out_path, work_dir, tts=speak, log=print\):\n", s, re.M))
assert len(m) == 1, "не нашёл def build(...)"
ins = (f"    {mark}: в часы live_hours — фон из настоящих клипов; не вышло — обычный вид ---\n"
       "    if cfg.get(\"live_hours\"):\n"
       "        try:\n"
       "            import live as _live\n"
       "            if _live.want(cfg):\n"
       "                return _live.build_live(script, cfg, out_path, work_dir, tts, log)\n"
       "        except Exception as _e:  # noqa: BLE001\n"
       "            log(f\"живые кадры не вышли ({_e}) — делаю обычный вид\")\n")
s = s[:m[0].end()] + ins + s[m[0].end():]
open("make_video.py", "w", encoding="utf-8").write(s)
print("   код: вставка сделана")
PY
"$PY" -m py_compile make_video.py live.py || restore "ошибка в коде после вставки"
"$PY" - "$NDAYS" <<'PY' || restore "не получилось поправить config.json"
import datetime as dt, json, sys
msk = dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
start = msk.date() if (msk.hour, msk.minute) < (14, 40) else msk.date() + dt.timedelta(days=1)
until = start + dt.timedelta(days=int(sys.argv[1]) - 1)
c = json.load(open("config.json", encoding="utf-8"))
if c.get("live_until"):                      # повторный запуск — срок опыта не сдвигаем
    until = dt.date.fromisoformat(c["live_until"])
    start = until - dt.timedelta(days=int(sys.argv[1]) - 1)
c["live_hours"] = [15]
c["live_until"] = until.isoformat()
open("config.json.tmp", "w", encoding="utf-8").write(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
json.load(open("config.json.tmp", encoding="utf-8"))
print(f"   живые кадры: слот 15:00 МСК, с {start:%d.%m} по {until:%d.%m} включительно ({sys.argv[1]} роликов)")
PY
mv config.json.tmp config.json || restore "не записался config.json"
"$PY" - <<'PY' || restore "проверка на сервере не прошла"
import datetime as dt, json
import make_video as M
import live
cfg = json.load(open("config.json", encoding="utf-8"))
msk = dt.timezone(dt.timedelta(hours=3))
d = dt.date.fromisoformat(cfg["live_until"])
assert live.want(cfg, dt.datetime(d.year, d.month, d.day, 15, 1, tzinfo=msk))
assert not live.want(cfg, dt.datetime(d.year, d.month, d.day, 11, 1, tzinfo=msk))
assert not live.want(cfg, dt.datetime(d.year, d.month, d.day, 19, 1, tzinfo=msk))
assert "живые кадры (H49)" in open("make_video.py", encoding="utf-8").read()
live.overlay("body", "Минимум 7 см", cfg.get("channel_handle", ""), "/tmp/pochemu_live_t.png")
print("   проверка: часы 11 и 19 — обычный вид, 15 — живые кадры; подпись рисуется шрифтом сервера")
PY
rm -f make_video.py.prevl config.json.prevl
unlock_bot
echo "== Встало. Бот: $D"

# ---------- ключ и клипы ----------
"$PY" live.py --check 2>&1 | sed 's/^/   /'
if ! "$PY" live.py --check >/dev/null 2>&1; then
  echo "   ⚠ Без ключа ролик в 15:00 выйдет в обычном виде (значок). Ключ бесплатный:"
  echo "     pexels.com/api → войти или зарегистрироваться → «Your API Key» → скопировать,"
  echo "     потом та же команда с --key ВАШ_КЛЮЧ в конце."
fi

# ---------- справка: какие темы выйдут в 15:00 и что искать (на установку не влияет) ----------
"$PY" - <<'PY' || echo "   (справку собрать не удалось — на установку это не влияет)"
import datetime as dt, json
import make_video as M
import live
cfg = json.load(open("config.json", encoding="utf-8"))
st = json.load(open("state.json", encoding="utf-8"))
msk = dt.timezone(dt.timedelta(hours=3))
now = dt.datetime.now(msk)
slots, day = [], now.date()
while len(slots) < 30:
    for h in (11, 15, 19):
        t = dt.datetime(day.year, day.month, day.day, h, 0, tzinfo=msk)
        if t > now:
            slots.append(t)
    day += dt.timedelta(days=1)
sk = set(st.get("used_titles", [])) | set(st.get("failed_titles", []))
print("   ближайшие ролики 15:00 (тема → запросы клипов):")
for k, t in enumerate(slots):
    s = M.bank_script(list(sk), st.get("n_done", 0) + k, cfg)
    sk.add(s["title"])
    if live.want(cfg, t.replace(minute=1)):
        print(f"     {t:%d.%m} {s['title']} → {', '.join(live.queries(s)) or 'нет слов — будет значок'}")
PY
