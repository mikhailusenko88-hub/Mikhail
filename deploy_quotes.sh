#!/bin/bash
# Установка бота «Живые строки» на сервер (повторный запуск безопасен — обновляет код, ничего не стирает).
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/quotes/deploy_quotes.sh | bash
set -u
RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/quotes
D=/root/quotes-bot
mkdir -p "$D/videos" && cd "$D" || exit 1

echo "== Скачиваю бота"
for f in quotes_bot.py yt_upload.py schedule_30d.json quotes; do
  curl -fsSL "$RAW/$f" -o "$f.new" && mv "$f.new" "$f" || { echo "!! не скачался $f"; exit 1; }
  echo "   $f"
done
if [ ! -f config.json ]; then
  cat > config.json <<'JSON'
{
  "enabled": true,
  "channel_name": "Living Lines",
  "youtube_category_id": "22",
  "youtube_privacy": "public",
  "yt_extra_tags": ["цитаты", "мудрость", "цитаты великих людей", "мудрые мысли", "классика", "литература", "акварель", "quotes", "wisdom"]
}
JSON
  echo "   config.json"
fi

echo "== Python с библиотеками YouTube"
PY=""
for c in /root/kz-bot/.venv/bin/python $(ls /root/*/.venv/bin/python 2>/dev/null) "$D/.venv/bin/python"; do
  [ -x "$c" ] && "$c" -c "import googleapiclient, google.oauth2, requests" 2>/dev/null && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  python3 -m venv "$D/.venv" && "$D/.venv/bin/pip" install -q google-api-python-client google-auth requests \
    && PY="$D/.venv/bin/python" || { echo "!! не получилось поставить библиотеки"; exit 1; }
fi
echo "   $PY"

echo "== Ключ приложения Google (тот же, что у «Білесің бе?»)"
if ls client_secret*.json >/dev/null 2>&1; then
  echo "   уже есть"
else
  SRC=""
  for t in /root/kz-bot/yt_token.json $(ls /root/*/yt_token.json 2>/dev/null); do [ -f "$t" ] && { SRC="$t"; break; }; done
  if [ -n "$SRC" ]; then
    "$PY" - "$SRC" <<'PYC'
import json, sys
d = json.load(open(sys.argv[1]))
out = {"installed": {"client_id": d["client_id"], "client_secret": d["client_secret"]}}
open("client_secret_quotes.json", "w").write(json.dumps(out))
PYC
    chmod 600 client_secret_quotes.json && echo "   взял из $SRC"
  else
    echo "!! ключа не нашёл — при входе спросит Client ID и Client secret"
  fi
fi

echo "== Команда quotes"
sed "s#__PY__#$PY#" quotes > /usr/local/bin/quotes && chmod +x /usr/local/bin/quotes && echo "   /usr/local/bin/quotes"

echo "== Расписание (каждые 10 минут бот сам смотрит, пора ли выкладывать)"
LINE="*/10 * * * * /usr/local/bin/quotes tick >> $D/cron.log 2>&1"
if crontab -l 2>/dev/null | grep -qF "quotes tick"; then
  echo "   уже стоит"
else
  crontab -l > "/root/crontab.bak-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
  (crontab -l 2>/dev/null; echo "$LINE") | crontab - && echo "   добавил" || echo "!! не получилось добавить в crontab"
fi

echo "== Место на диске: $(df -h / | awk 'NR==2{print "свободно "$4" из "$2}')"
echo
if [ -f yt_token.json ]; then
  "$PY" yt_upload.py --check 2>&1
  "$PY" quotes_bot.py status
else
  echo "Осталось войти в YouTube. Сейчас покажу код:"
  "$PY" yt_upload.py --login-start 2>&1
fi
