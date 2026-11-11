#!/bin/bash
# «Почему так?» (11.11.2026): темы ещё на месяц.
#   1) +88 новых тем (рубрики поровну): здоровье, быт и дача, машины, история, природа, рекорды.
#      Идут после уже стоящих в очереди; прежние темы не тронуты.
#   2) Три темы, которые бот 7.11 пометил «не собрались» и пропускал («Самый жуткий факт о Солнце»,
#      «Жуткий факт о твоём теле», «Жуткий факт о космосе: ты видишь прошлое»), стоят в самом конце очереди.
#   3) Новые картинки: гриб, птица, насекомое.
#   Меняются только icons.py и topics_ru_v2.json (и список пропущенных тем в state.json).
#   make_video.py, расписание, настройки, голос — как были.
# Запуск на сервере (команда «Сервер» на iPhone):
#   RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/<коммит>; curl -fsSL --max-time 40 $RAW/deploy_pochemu_month.sh | RAW=$RAW bash 2>&1
# Вернуть как было:  ... | RAW=$RAW bash -s -- --back 2>&1
# Безопасно: сначала всё скачивается и проверяется в стороне; прежние файлы хранятся как *.bak-month;
# при любой ошибке возвращает назад и пишет «НЕ ВСТАЛО». Повторный запуск ничего не ломает.
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
FILES="icons.py topics_ru_v2.json"
TAG=bak-month
NEED=142           # сценариев в новом банке
THREE='["Самый жуткий факт о Солнце", "Жуткий факт о твоём теле", "Жуткий факт о космосе: ты видишь прошлое"]'

fail() { echo "!! $1"; echo "НЕ ВСТАЛО — на сервере ничего не изменено"; exit 1; }

# ---------- папка бота «Почему так?» ----------
is_bot() {      # бот «Почему так?»: свой банк topics_ru_v2.json, не казахский канал и не гонки
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
  if [ "${#C[@]}" -gt 1 ]; then          # несколько копий — берём ту, что стоит в расписании
    CR=$(crontab -l 2>/dev/null | grep -v '^ *#' | grep run_daily)
    K=(); for d in "${C[@]}"; do echo "$CR" | grep -q "$d\(/\| \|$\)" && K+=("$d"); done
    [ "${#K[@]}" -eq 1 ] && C=("${K[@]}")
  fi
fi
[ "${#C[@]}" -eq 1 ] || fail "Не нашёл одну папку бота «Почему так?» (нашёл: ${C[*]:-ничего}). Пришли этот вывод Клоду."
D=${C[0]}
cd "$D" || fail "не открылась папка $D"
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

export_texts() {    # тексты будущих роликов -> для озвучки Альбиной в GitHub
  [ -f albina.py ] || return 0
  "$PY" -c "import json, albina; albina.export_bank(json.load(open('config.json', encoding='utf-8')))" 2>/dev/null \
    || echo "   ! тексты для озвучки не выложились (не страшно — выложатся при следующем ролике)"
}

# ---------- бот не должен в этот момент делать ролик ----------
# Замок тот же, что у самого бота (.lock): пока идёт сборка ролика — файлы не трогаем; пока меняем файлы
# (несколько секунд) — бот не начнёт сборку. Скачивание идёт до замка, чтобы не держать его долго.
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

# ---------- вернуть как было ----------
if [ "${1:-}" = "--back" ]; then
  for f in $FILES state.json; do [ -f "$f.$TAG" ] || fail "нет сохранённого файла $f.$TAG — возвращать нечего"; done
  lock_bot
  "$PY" - "$TAG" <<'PY' || { echo "!! не вернулось"; echo "НЕ ВСТАЛО"; exit 1; }
import json, sys
tag = sys.argv[1]
st = json.load(open("state.json", encoding="utf-8"))
was = json.load(open("state.json." + tag, encoding="utf-8"))
st["failed_titles"] = was.get("failed_titles", [])     # вышедшие с тех пор ролики остаются отмеченными
open("state.json.tmp", "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))
json.load(open("state.json.tmp", encoding="utf-8"))
PY
  for f in $FILES; do cp -p "$f.$TAG" "$f" || { echo "!! не вернулся $f"; echo "НЕ ВСТАЛО"; exit 1; }; done
  mv state.json.tmp state.json || { echo "!! не вернулся state.json"; echo "НЕ ВСТАЛО"; exit 1; }
  "$PY" -m py_compile icons.py || { echo "!! прежний icons.py не проверился"; echo "НЕ ВСТАЛО"; exit 1; }
  unlock_bot
  export_texts
  echo "== Готово: темы как были до 11.11 (без 88 новых), три пропущенные темы снова пропускаются. Бот: $D"
  exit 0
fi

# ---------- скачать и проверить в стороне ----------
grep -q "^def fit_text" make_video.py && grep -q "^def text_fit_report" make_video.py \
  || fail "на сервере ещё нет вчерашнего обновления «Почему так?» (надписи по ширине) — сначала нужна прошлая команда"
T=$(mktemp -d) || fail "нет временной папки"
trap 'rm -rf "$T"' EXIT
echo "== Скачиваю (бот: $D)"
for f in $FILES; do
  curl -fsSL --connect-timeout 10 --max-time 40 "$RAW/$f" -o "$T/$f" || fail "не скачался $f"
done
grep -q '("mushroom",' "$T/icons.py" && grep -q '("bird",' "$T/icons.py" && grep -q '("bug",' "$T/icons.py" || fail "скачался не тот icons.py"
"$PY" -m py_compile "$T/icons.py" || fail "в скачанном icons.py ошибка"
"$PY" - "$T/topics_ru_v2.json" "$NEED" "$THREE" <<'PY' || fail "новый банк тем не прошёл проверку"
import json, sys
bank = json.load(open(sys.argv[1], encoding="utf-8"))
three = json.loads(sys.argv[3])
cfg = json.load(open("config.json", encoding="utf-8"))
old = json.load(open("topics_ru_v2.json", encoding="utf-8"))
fm = cfg.get("formats") or []
titles = [s["title"] for s in bank]
assert len(bank) == int(sys.argv[2]) and len(set(titles)) == len(bank), f"сценариев {len(bank)}"
for s in bank:
    assert s["format"] in fm, f"рубрики «{s['format']}» нет в config.json"
    assert len(s["lines"]) == 5 and all(l.strip() for l in s["lines"]) and len(s.get("caps") or []) == 5, s["title"]
key = lambda s: json.dumps(s, ensure_ascii=False, sort_keys=True)
have = set(map(key, bank))
lost = [s["title"] for s in old if key(s) not in have]
assert not lost, f"пропали или изменились прежние темы: {lost[:3]}"
jt = [s["title"] for s in bank if s["format"] == "Жуткий факт"]
assert jt[-3:] == three, "три пропущенные темы должны стоять в конце"
PY

# ---------- поставить ----------
lock_bot
for f in $FILES state.json; do
  [ -f "$f.$TAG" ] || cp -p "$f" "$f.$TAG" || fail "не сохранилась копия $f"     # прежние файлы — один раз
  cp -p "$f" "$f.prevm" || fail "не сохранилась копия $f"
done
restore() {
  echo "!! $1 — возвращаю как было"
  for f in $FILES state.json; do cp -p "$f.prevm" "$f"; rm -f "$f.prevm" "$f.newm"; done
  rm -f state.json.tmp
  echo "НЕ ВСТАЛО — на сервере всё как было"; exit 1
}
for f in $FILES; do cp "$T/$f" "$f.newm" && mv "$f.newm" "$f" || restore "не записался $f"; done
"$PY" - "$THREE" <<'PY' || restore "не получилось поправить список пропущенных тем"
import json, sys
three = set(json.loads(sys.argv[1]))
st = json.load(open("state.json", encoding="utf-8"))
was = st.get("failed_titles", [])
st["failed_titles"] = [t for t in was if t not in three]
open("state.json.tmp", "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))
json.load(open("state.json.tmp", encoding="utf-8"))
PY
mv state.json.tmp state.json || restore "не записался state.json"
"$PY" -m py_compile icons.py || restore "ошибка в icons.py"

# ---------- проверка на этом сервере (его шрифт, его Python) ----------
"$PY" - "$TAG" <<'PY' || restore "проверка на сервере не прошла"
import json, os, sys, tempfile
import make_video as M
import icons

tag = sys.argv[1]
cfg = json.load(open("config.json", encoding="utf-8"))
bank = json.load(open("topics_ru_v2.json", encoding="utf-8"))
st = json.load(open("state.json", encoding="utf-8"))
old = {s["title"] for s in json.load(open("topics_ru_v2.json." + tag, encoding="utf-8"))}
new = [s for s in bank if s["title"] not in old]
# 1) надписи: каждая строка каждого кадра влезает в поле
n, widest, bad = M.text_fit_report(bank, cfg.get("max_lines", 5))
assert not bad, "надписи не влезают: " + "; ".join(bad[:3])
# 2) картинки рисуются, кадр собирается
for name in ("mushroom", "bird", "bug", "car", "pill"):
    assert icons.draw(name, 620, (255, 196, 64)).getbbox(), name
assert icons.pick("бледная поганка гриб") == "mushroom" and icons.pick("кукушка птица гнездо") == "bird"
tmp = tempfile.mkdtemp()
s0 = new[0]
M.text_v2((255, 196, 64), "hook", s0["title"], s0["lines"][0], 0, 6, cfg.get("channel_handle", ""), os.path.join(tmp, "t.png"))
# 3) бот выбирает следующую тему
skip = st.get("used_titles", []) + st.get("failed_titles", [])
nx = M.bank_script(skip, st.get("n_done", 0), cfg)
assert nx and nx.get("lines"), "бот не смог выбрать тему"
print(f"   надписи: проверено {n} кадров, самая широкая строка {widest:.0f} из {M.SAFE_W} px — за края не выходит")
PY
for f in $FILES state.json; do rm -f "$f.prevm"; done
unlock_bot
echo "== Встало. Тем в банке теперь: $NEED."
export_texts

# ---------- справка: очередь и озвучка (на установку уже не влияет) ----------
"$PY" - "$TAG" "$THREE" <<'PY' || echo "   (справку собрать не удалось — на установку это не влияет)"
import json, sys
import make_video as M
tag, three = sys.argv[1], json.loads(sys.argv[2])
cfg = json.load(open("config.json", encoding="utf-8"))
bank = json.load(open("topics_ru_v2.json", encoding="utf-8"))
st = json.load(open("state.json", encoding="utf-8"))
old = {s["title"] for s in json.load(open("topics_ru_v2.json." + tag, encoding="utf-8"))}
sk = set(st.get("used_titles", [])) | set(st.get("failed_titles", []))
order = []
for k in range(400):                         # ровно так, как бот выбирает тему
    s = M.bank_script(list(sk), st.get("n_done", 0) + k, cfg)
    if s["title"] in sk:
        break
    sk.add(s["title"]); order.append(s)
import datetime
MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
per_day = max(1, len(cfg.get("schedule") or cfg.get("times") or []) or 3)
end = datetime.date.today() + datetime.timedelta(days=len(order) // per_day)
print(f"   в очереди невышедших тем: {len(order)}. При {per_day} роликах в день их хватит примерно до {end.day} {MON[end.month - 1]}")
pos = [i + 1 for i, s in enumerate(order) if s["title"] in three]
if pos:
    print("   три пропущенные темы выйдут в самом конце (ролики №" + ", ".join(map(str, pos)) + ")")
try:
    import albina
    voice = next((v for v in (cfg.get("voices") or []) if albina.is_albina(v)), None)
    marks = albina.gh_marks() if voice else {}
    if voice and marks:
        miss = [s["title"] for s in order if not all(albina.cache_key(l, voice) in marks for l in s["lines"][:cfg.get("max_lines", 5)])]
        print(f"   озвучено Альбиной: {len(order) - len(miss)} из {len(order)} тем в очереди" + ("" if not miss else " — нет озвучки: " + "; ".join(miss[:3])))
    elif voice:
        print("   озвучка: GitHub сейчас не ответил, проверить не смог (ролик сам возьмёт готовую озвучку при сборке)")
except Exception:
    pass
print("   ближайшие ролики:")
for i, s in enumerate(order[:6]):
    print(f"     {i + 1}. {s['title']}" + (" — НОВАЯ" if s["title"] not in old else ""))
PY
echo "   Вернуть как было: та же команда, после bash добавить  -s -- --back"
