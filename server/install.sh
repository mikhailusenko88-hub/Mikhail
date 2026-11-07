#!/bin/bash
# Установка нарезки Shorts «Кот Барсик» на сервер. Запуск: curl -sL <raw-url>/install.sh | bash
set -e
RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/mikhail/shorts/server
echo "== пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update >/dev/null 2>&1 || true
apt-get -qq install -y ffmpeg fonts-dejavu-core python3 python3-pip curl >/dev/null 2>&1 || apt-get -qq install -y ffmpeg fonts-dejavu python3 python3-pip curl >/dev/null 2>&1 || true
apt-get -qq install -y unzip >/dev/null 2>&1 || true
pip3 install -q -U "yt-dlp[default]" yt-dlp-ejs 2>/dev/null || pip3 install -q -U --break-system-packages "yt-dlp[default]" yt-dlp-ejs
# deno — движок JS, нужен yt-dlp для YouTube
if ! command -v deno >/dev/null 2>&1; then
  curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y >/dev/null 2>&1 || true
  [ -x /usr/local/bin/deno ] || { curl -fsSL -o /tmp/deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip && unzip -qo /tmp/deno.zip -d /usr/local/bin && chmod +x /usr/local/bin/deno; }
fi
echo "deno: $(deno --version 2>/dev/null | head -1 || echo НЕТ)  ejs: $(pip3 show yt-dlp-ejs 2>/dev/null | grep -i ^version | cut -d" " -f2)"
echo "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f3)  yt-dlp: $(yt-dlp --version 2>/dev/null)"

echo "== папки"
mkdir -p /var/www/shorts/tmp /var/www/mebel/s9kbars-v
touch /var/www/mebel/s9kbars-v/.keep
# старая синхронизация с GitHub больше не нужна
(crontab -l 2>/dev/null | grep -v shorts-sync | grep -v shorts-cut) | crontab - || true
rm -f /usr/local/bin/shorts-sync
# очистить старые тестовые ролики
[ -f /var/www/shorts/.installed ] || { find /var/www/mebel/s9kbars-v -maxdepth 1 -type f \( -name '*.mp4' -o -name '*.jpg' -o -name '*.part' \) -delete; rm -f /var/www/mebel/s9kbars-v/feed.json /var/www/shorts/state.json; }
touch /var/www/shorts/.installed

echo "== скрипт"
cat > /usr/local/bin/shorts-cut <<'EOF'
#!/bin/bash
# каждый запуск подтягивает свежий скрипт с GitHub (если GitHub недоступен — работает старый)
curl -sL --max-time 30 https://raw.githubusercontent.com/mikhailusenko88-hub/mikhail/shorts/server/shorts-cut.py -o /usr/local/bin/shorts-cut.py.new \
  && python3 -c "import ast,sys;ast.parse(open('/usr/local/bin/shorts-cut.py.new').read())" 2>/dev/null \
  && mv /usr/local/bin/shorts-cut.py.new /usr/local/bin/shorts-cut.py || rm -f /usr/local/bin/shorts-cut.py.new
exec python3 /usr/local/bin/shorts-cut.py "$@"
EOF
chmod +x /usr/local/bin/shorts-cut
curl -sL $RAW/shorts-cut.py -o /usr/local/bin/shorts-cut.py
(crontab -l 2>/dev/null; echo "0 7 * * * /usr/local/bin/shorts-cut >/dev/null 2>&1") | crontab -
echo "cron: $(crontab -l | grep shorts-cut)"

echo "== проверка YouTube с сервера"
cd /var/www/shorts/tmp && rm -f yt-test.mp4
yt-dlp --js-runtimes deno -f "b[height<=360]" -o yt-test.mp4 --no-playlist "https://www.youtube.com/watch?v=fa7knKC0dNs" 2>&1 | grep -E "ERROR|WARNING|Destination|100%" | tail -4 || true
if [ -s yt-test.mp4 ]; then echo "YouTube: РАБОТАЕТ ($(du -h yt-test.mp4 | cut -f1))"; rm -f yt-test.mp4; else echo "YouTube: НЕ КАЧАЕТ (будет Rutube)"; fi

if ls /var/www/mebel/s9kbars-v/*.mp4 >/dev/null 2>&1; then echo "== ролики уже есть, нарезку не повторяю"; else echo "== первая нарезка (2–5 минут)"; /usr/local/bin/shorts-cut 2>&1 | grep -vE "WARNING|ERROR" | tail -6; fi
echo "== файлы:"; ls -la /var/www/mebel/s9kbars-v/ | grep -E 'mp4|feed' || echo "(пусто)"
echo "== готово: http://89.126.192.214:8080/mebel/s9kbars/"
