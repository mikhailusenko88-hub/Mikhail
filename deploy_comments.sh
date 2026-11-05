#!/bin/bash
# «Білесің бе?»: города из комментариев сами попадают в гонку «Қай қала жеңеді?».
#   - бот перед каждой гонкой городов читает комментарии (как обычный зритель, без ключей);
#   - узнаёт город в любом написании (Ускимен = Өскемен = Усть-Каменогорск), повторно не добавляет;
#   - за заезд добавляет не больше 2 новых городов, всего до 30; в описании ролика — «🆕 по вашей просьбе».
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_comments.sh | bash
# Безопасно: делает копии (.bak-ДАТА), при любой ошибке возвращает как было. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot

D=""
for c in /root/kz-bot; do [ -f "$c/race_leagues.py" ] && D="$c"; done
if [ -z "$D" ]; then
  f=$(find / -xdev -name race_leagues.py -not -path '/proc/*' -not -path '*/.git/*' 2>/dev/null | head -1)
  [ -n "$f" ] && D=$(dirname "$f")
fi
[ -n "$D" ] || { echo "!! Не нашёл папку бота «Білесің бе?»"; exit 1; }
echo "== Бот: $D"
cd "$D" || exit 1
PY=python3; [ -x "$D/.venv/bin/python" ] && PY="$D/.venv/bin/python"

for f in race_leagues.py race_bot.py; do cp -p "$f" "$f.bak-$STAMP"; done
[ -f kz_places.py ] && cp -p kz_places.py "kz_places.py.bak-$STAMP"
restore() {
  echo "!! Ошибка — возвращаю как было"
  for f in race_leagues.py race_bot.py; do cp -p "$f.bak-$STAMP" "$f"; done
  if [ -f "kz_places.py.bak-$STAMP" ]; then cp -p "kz_places.py.bak-$STAMP" kz_places.py; else rm -f kz_places.py; fi
  exit 1
}

echo "== Ставлю чтение комментариев (youtube-comment-downloader)"
"$PY" -m pip install -q youtube-comment-downloader 2>/dev/null || pip3 install -q youtube-comment-downloader \
  || { echo "!! не поставился youtube-comment-downloader"; restore; }

echo "== Скачиваю kz_places.py (справочник городов + чтение комментариев)"
curl -fsSL "$RAW/kz_places.py" -o kz_places.py.new && mv kz_places.py.new kz_places.py || restore

echo "== Подключаю к гонке"
"$PY" - <<'EOF' || restore
from pathlib import Path

# --- race_leagues.py: к 22 городам добавляются города по просьбам (из state.json) ---
p = Path("race_leagues.py")
s = p.read_text(encoding="utf-8")
if "EXTRA_CITIES" in s:
    print("   race_leagues.py — уже подключён")
else:
    old = '''    if league == "cities":
        return [_e(kk, kk, ru, str(i + 1), lat=la, lon=lo) for i, (kk, ru, la, lo) in enumerate(CITIES)]'''
    new = '''    if league == "cities":
        rows = list(CITIES) + [r for r in EXTRA_CITIES if r[0] not in {c[0] for c in CITIES}]
        return [_e(kk, kk, ru, str(i + 1), lat=la, lon=lo) for i, (kk, ru, la, lo) in enumerate(rows)]'''
    if old not in s:
        raise SystemExit("!! не нашёл entries() для городов в race_leagues.py")
    s = s.replace(old, new, 1)
    anchor = "def entries(league"
    add = ('# города, добавленные по просьбам из комментариев (ставит race_bot из state.json → race.extra)\n'
           'EXTRA_CITIES = []\n\n\n'
           'def set_extra_cities(rows):\n'
           '    EXTRA_CITIES[:] = [(r["kk"], r["ru"], r["lat"], r["lon"]) for r in rows or []]\n\n\n')
    i = s.index(anchor)
    s = s[:i] + add + s[i:]
    p.write_text(s, encoding="utf-8")
    print("   race_leagues.py — подключён")

# --- race_bot.py: перед гонкой городов прочитать просьбы, в описание — «🆕 по вашей просьбе» ---
p = Path("race_bot.py")
s = p.read_text(encoding="utf-8")
if "kz_places" in s:
    print("   race_bot.py — уже подключён")
else:
    old1 = '''    ls = league_state(state, league)
    new_season(ls, league, log)
'''
    new1 = '''    ls = league_state(state, league)
    new_season(ls, league, log)
    # города по просьбам из комментариев (kz_places.py)
    new_cities = []
    try:
        import kz_places as KP
        if league == "cities" and not test:
            new_cities, _ = KP.take_requests(state, ls, log, cfg)
    except Exception as e:
        log(f"Города из комментариев: ошибка {e}")
    RL.set_extra_cities(state.get("race", {}).get("extra", []))
'''
    old2 = '''    out.with_suffix(".txt").write_text(info["title"] + "\\n\\n" + info["description"], encoding="utf-8")'''
    new2 = '''    if league == "cities":
        try:
            import kz_places as KP
            info["description"] = KP.note(new_cities) + KP.fix_desc(info["description"], len(RL.entries("cities")))
        except Exception as e:
            log(f"Описание: {e}")
    out.with_suffix(".txt").write_text(info["title"] + "\\n\\n" + info["description"], encoding="utf-8")'''
    if old1 not in s or old2 not in s:
        raise SystemExit("!! не нашёл места в race_bot.py (run_league)")
    s = s.replace(old1, new1, 1).replace(old2, new2, 1)
    p.write_text(s, encoding="utf-8")
    print("   race_bot.py — подключён")
EOF

"$PY" -m py_compile race_leagues.py race_bot.py kz_places.py || restore
"$PY" -c "import race_leagues as RL; RL.set_extra_cities([{'kk':'Тест','ru':'Тест','lat':45,'lon':70}]); assert len(RL.entries('cities')) == len(RL.CITIES) + 1" || restore
"$PY" race_video.py --check >/dev/null || restore

echo "== Обновляю srv (новые команды: srv city, srv cities)"
curl -fsSL "$RAW/srv" -o /usr/local/bin/srv.new && chmod +x /usr/local/bin/srv.new && mv /usr/local/bin/srv.new /usr/local/bin/srv

echo
echo "== Проверка: что сейчас пишут в комментариях (ничего не меняю)"
"$PY" kz_places.py --dry 2>&1 | tail -20
echo
echo "== Готово. Перед каждой гонкой городов бот сам добавит новые города из комментариев (до 2 за заезд)."
echo "   Посмотреть просьбы:  srv cities      Добавить вручную:  srv city Степногорск"
