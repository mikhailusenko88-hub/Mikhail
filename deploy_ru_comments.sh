#!/bin/bash
# «Білесің бе?»: ру из комментариев сами попадают в гонку «Қай ру жеңеді?».
#   - перед каждой гонкой родов бот читает комментарии (как обычный зритель, без ключей);
#   - берёт ТОЛЬКО настоящие ру из справочника kz_ru.py (шежіре трёх жузов) — выдуманное не добавит;
#   - узнаёт любое написание (Уақ = Уак, Адаймын, Найманнан); подроды (Тобықты, Матай, Ботбай) засчитывает своему ру;
#   - за заезд добавляет не больше 3 новых ру, всего до 30; в описании ролика — «🆕 по вашей просьбе».
# Запуск на сервере (команда «Сервер» на iPhone):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_ru_comments.sh | bash
# Безопасно: делает копии (*.bak-ДАТА), при ошибке возвращает как было. Повторный запуск ничего не ломает.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
RAW=${RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot}

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

FILES="race_leagues.py race_bot.py kz_ru.py"
for f in $FILES; do [ -f "$f" ] && cp -p "$f" "$f.bak-$STAMP"; done
restore() {
  echo "!! Ошибка — возвращаю как было"
  for f in $FILES; do
    if [ -f "$f.bak-$STAMP" ]; then cp -p "$f.bak-$STAMP" "$f"; else rm -f "$f"; fi
  done
  exit 1
}

[ -f kz_places.py ] || { echo "!! нет kz_places.py — сначала нужен deploy_comments.sh"; exit 1; }
"$PY" -c "import youtube_comment_downloader" 2>/dev/null || "$PY" -m pip install -q youtube-comment-downloader \
  || pip3 install -q youtube-comment-downloader || { echo "!! не поставился youtube-comment-downloader"; exit 1; }

echo "== Скачиваю"
for f in $FILES; do
  curl -fsSL "$RAW/$f?$STAMP" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; restore; }
done
"$PY" -m py_compile $FILES || restore

echo "== Проверка"
"$PY" -c "
import race_leagues as RL, kz_ru as KR
assert KR.find('Уақпын') == [('Уақ', None)]
assert KR.find('Тобықты') == [('Арғын', 'Тобықты')]
assert KR.find('маймыл сила') == []
RL.set_extra_ru([{'kk': 'Тарақты', 'ru': 'Таракты', 'zhuz': 'орта'}])
assert len(RL.entries('ru')) == len(RL.RU) + 1
RL.set_extra_ru([])
print('   распознавание и список ру — ок')
" || restore
"$PY" race_video.py --check >/dev/null || restore

echo "== Обновляю srv (новые команды: srv ru, srv rus)"
curl -fsSL "$RAW/srv?$STAMP" -o /usr/local/bin/srv.new && chmod +x /usr/local/bin/srv.new && mv /usr/local/bin/srv.new /usr/local/bin/srv

echo
echo "== Что сейчас пишут про ру в комментариях (ничего не меняю)"
timeout 300 "$PY" kz_ru.py --dry 2>&1 | tail -20
echo
echo "== Готово. Перед каждой гонкой родов бот сам добавит новые ру из комментариев (до 3 за заезд)."
echo "   Посмотреть просьбы:  srv rus      Добавить вручную:  srv ru Тарақты"
