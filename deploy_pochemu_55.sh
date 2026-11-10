#!/bin/bash
# «Почему так?» (10.11.2026):
#   1) надписи больше не вылезают за края кадра: размер букв подбирается и по ширине (длинное слово
#      вроде «ДЕФОРМИРУЮТСЯ» раньше выходило за поле), текст держится в 120 px от краёв;
#   2) 20 новых тем под настоящего зрителя (55+, мужчины): здоровье, быт, машины, история. Идут через одну
#      со старыми темами; старые темы не тронуты; новые картинки «машина» и «таблетка».
#   Меняются только make_video.py, icons.py, topics_ru_v2.json. Расписание, настройки, голос — как были.
# Запуск на сервере (команда «Сервер» на iPhone):
#   RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot; curl -fsSL --max-time 40 $RAW/deploy_pochemu_55.sh | RAW=$RAW bash 2>&1
# Вернуть как было:  ... | RAW=$RAW bash -s -- --back 2>&1
# Безопасно: сначала всё скачивается и проверяется в стороне; прежние файлы хранятся как *.bak-pre55;
# при любой ошибке возвращает назад и пишет «НЕ ВСТАЛО». Повторный запуск ничего не ломает.
set -u
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}
ALB=${ALB:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/fdfc60aefb88df0c1daab9d9ed2aebabee118381}
FILES="make_video.py icons.py topics_ru_v2.json"
TAG=bak-pre55
NEED=54            # сценариев в новом банке

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
  lock_bot
  for f in $FILES; do [ -f "$f.$TAG" ] || fail "нет сохранённого файла $f.$TAG — возвращать нечего"; done
  for f in $FILES; do cp -p "$f.$TAG" "$f" || { echo "!! не вернулся $f"; echo "НЕ ВСТАЛО"; exit 1; }; done
  "$PY" -m py_compile make_video.py icons.py || { echo "!! прежний код не проверился"; echo "НЕ ВСТАЛО"; exit 1; }
  export_texts
  echo "== Готово: «Почему так?» возвращён как был до 10.11 (прежние надписи, без новых тем). Бот: $D"
  exit 0
fi

# ---------- скачать и проверить в стороне ----------
T=$(mktemp -d) || fail "нет временной папки"
trap 'rm -rf "$T"' EXIT
echo "== Скачиваю (бот: $D)"
for f in $FILES; do
  curl -fsSL --connect-timeout 10 --max-time 40 "$RAW/$f" -o "$T/$f" || fail "не скачался $f"
done
curl -fsSL --connect-timeout 10 --max-time 40 "$ALB/patch_bot.py" -o "$T/patch_bot.py" || fail "не скачался patch_bot.py"
grep -q "^def fit_text" "$T/make_video.py" && grep -q "^def text_fit_report" "$T/make_video.py" \
  && grep -q '("car",' "$T/icons.py" && grep -q '("pill",' "$T/icons.py" || fail "скачались не те файлы"
"$PY" -m py_compile "$T/make_video.py" "$T/icons.py" "$T/patch_bot.py" || fail "в скачанном коде ошибка"
"$PY" - "$T/topics_ru_v2.json" "$NEED" <<'PY' || fail "новый банк тем не прошёл проверку"
import json, sys
bank = json.load(open(sys.argv[1], encoding="utf-8"))
cfg = json.load(open("config.json", encoding="utf-8"))
old = json.load(open("topics_ru_v2.json", encoding="utf-8"))
fm = cfg.get("formats") or []
titles = [s["title"] for s in bank]
assert len(bank) == int(sys.argv[2]) and len(set(titles)) == len(bank), f"сценариев {len(bank)}"
for s in bank:
    assert s["format"] in fm, f"рубрики «{s['format']}» нет в config.json"
    assert len(s["lines"]) == 5 and all(l.strip() for l in s["lines"]) and len(s.get("caps") or []) == 5, s["title"]
lost = [s["title"] for s in old if s["title"] not in set(titles)]
assert not lost, f"пропали прежние темы: {lost}"
PY

# ---------- поставить ----------
lock_bot
ALB_ON=0          # 0 — голос «Альбина» к боту не подключён; 1 — подключён и работает; 2 — подключён, но не загружается
if grep -q "голос «Альбина»" make_video.py; then
  "$PY" -c "import make_video as M, sys; sys.exit(0 if getattr(M.speak, '_albina', False) else 1)" >/dev/null 2>&1 && ALB_ON=1 || ALB_ON=2
fi
for f in $FILES; do
  [ -f "$f.$TAG" ] || cp -p "$f" "$f.$TAG" || fail "не сохранилась копия $f"     # прежние файлы — один раз
  cp -p "$f" "$f.prev55" || fail "не сохранилась копия $f"
done
restore() {
  echo "!! $1 — возвращаю как было"
  for f in $FILES; do cp -p "$f.prev55" "$f"; rm -f "$f.prev55" "$f.new55"; done
  echo "НЕ ВСТАЛО — на сервере всё как было"; exit 1
}
for f in $FILES; do cp "$T/$f" "$f.new55" && mv "$f.new55" "$f" || restore "не записался $f"; done
if [ "$ALB_ON" != 0 ]; then
  "$PY" "$T/patch_bot.py" make_video.py >/dev/null || restore "голос «Альбина» не подключился к новому make_video.py"
  grep -q "голос «Альбина»" make_video.py || restore "голос «Альбина» не подключился к новому make_video.py"
fi
"$PY" -m py_compile make_video.py icons.py || restore "ошибка в коде"

# ---------- проверка на этом сервере (его шрифт, его Python) ----------
"$PY" - "$TAG" "$ALB_ON" <<'PY' || restore "проверка на сервере не прошла"
import json, os, sys, tempfile
import make_video as M
import icons

tag, alb_on = sys.argv[1], sys.argv[2]
cfg = json.load(open("config.json", encoding="utf-8"))
bank = json.load(open("topics_ru_v2.json", encoding="utf-8"))
old = {s["title"] for s in json.load(open("topics_ru_v2.json." + tag, encoding="utf-8"))}
new = [s for s in bank if s["title"] not in old]

# 1) надписи: каждая строка каждого кадра влезает в поле
n, widest, bad = M.text_fit_report(bank, cfg.get("max_lines", 5))
assert not bad, "надписи не влезают: " + "; ".join(bad[:3])
# 2) кадры и картинки рисуются
tmp = tempfile.mkdtemp()
s0 = new[0] if new else bank[0]
for i, kind in ((0, "hook"), (2, "body"), (5, "cta")):
    M.text_v2((255, 196, 64), kind, s0["title"], s0["lines"][i] if i < 5 else M.CTA_TEXT, i, 6,
              cfg.get("channel_handle", ""), os.path.join(tmp, "t.png"), cap=s0["caps"][i] if kind == "body" else None)
for name in ("car", "pill"):
    assert icons.draw(name, 620, (255, 196, 64)).getbbox(), name
assert icons.pick("машина мотор бензин") == "car" and icons.pick("таблетки лекарство") == "pill"
if alb_on == "1":
    assert getattr(M.build, "_albina", False) and getattr(M.speak, "_albina", False), "Альбина не подключена"
elif alb_on == "2":
    print("   ! голос «Альбина» не загружался и до этой команды — это отдельная неполадка, пришли вывод Клоду")
fnt = M.font(40).getname()[0]
print(f"   надписи: проверено {n} кадров, самая широкая строка {widest:.0f} из {M.SAFE_W} px — за края не выходит (шрифт {fnt})")
PY
for f in $FILES; do rm -f "$f.prev55"; done
unlock_bot
echo "== Встало. Со следующего ролика: надписи в поле кадра и новые темы через одну со старыми."
export_texts

# ---------- справка: что выйдет дальше и готова ли озвучка (на установку уже не влияет) ----------
"$PY" - "$TAG" <<'PY' || echo "   (справку о ближайших роликах собрать не удалось — на установку это не влияет)"
import json, os, sys

tag = sys.argv[1]
cfg = json.load(open("config.json", encoding="utf-8"))
bank = json.load(open("topics_ru_v2.json", encoding="utf-8"))
old = {s["title"] for s in json.load(open("topics_ru_v2.json." + tag, encoding="utf-8"))}
new = [s for s in bank if s["title"] not in old]
st = json.load(open("state.json", encoding="utf-8")) if os.path.exists("state.json") else {}
used, failed = st.get("used_titles", []), st.get("failed_titles", [])
skip = set(used) | set(failed)
future = [s for s in bank if s["title"] not in skip]
voice, marks = None, {}
try:
    import albina
    voice = next((v for v in (cfg.get("voices") or []) if albina.is_albina(v)), None)
    if voice:
        marks = albina.gh_marks()
except Exception:
    pass
ready = lambda s: all(albina.cache_key(l, voice) in marks for l in s["lines"][:cfg.get("max_lines", 5)])

print(f"   тем в банке: {len(bank)}, новых: {len(new)}; ещё не выходило: {len(future)} (из них новых {sum(s in new for s in future)})")
if not voice:
    print("   голос: в config.json не Альбина — озвучку не проверяю")
elif not marks:
    print("   озвучка: GitHub сейчас не ответил, проверить не смог (ролик сам возьмёт готовую озвучку при сборке)")
else:
    miss = [s["title"] for s in future if not ready(s)]
    print(f"   озвучено Альбиной: {len(future) - len(miss)} из {len(future)} будущих тем" + ("" if not miss else " — НЕТ озвучки: " + "; ".join(miss[:4])))
fm = cfg.get("formats") or []
n0, sk = st.get("n_done", 0), set(skip)
print("   ближайшие ролики:")
for k in range(6):
    want = fm[(n0 + k) % len(fm)] if fm else None
    s = next((x for x in bank if x["title"] not in sk and (not want or x["format"] == want)), None)
    if not s:
        break
    sk.add(s["title"])
    print(f"     {k + 1}. {s['title']}" + (" — НОВАЯ" if s in new else ""))
if failed:
    print(f"   к сведению: эти темы бот раньше не смог собрать и пропускает ({len(failed)}): " + "; ".join(failed[:5]))
PY
echo "   Вернуть как было: та же команда, после bash добавить  -s -- --back"
