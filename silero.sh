#!/bin/bash
# Пробный ролик с голосом Silero. Всё в /root/silero-test, боты и VPN не затрагиваются.
set -e
D=/root/silero-test; mkdir -p $D; cd $D
AV=$(df --output=avail -k / | tail -1)
echo "Свободно на диске: $((AV/1024)) МБ"
[ "$AV" -gt 2000000 ] || { echo "Мало места (нужно 2 ГБ), стоп"; exit 1; }
R=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/silero-test
for f in prep.py tts.py build.py; do curl -sfL -o $f $R/$f; done
echo "1/4 Ставлю Silero (torch, ~5 минут)..."
[ -d venv ] || python3 -m venv venv
venv/bin/pip -q install --upgrade pip
venv/bin/pip -q install numpy torch --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
echo "2/4 Скачиваю модель голоса..."
[ -s v4_ru.pt ] || curl -sfL -o v4_ru.pt https://models.silero.ai/models/tts/ru/v4_ru.pt
/root/clips-bot/.venv/bin/python prep.py
echo "3/4 Озвучиваю..."
venv/bin/python tts.py
echo "4/4 Собираю ролик..."
/root/clips-bot/.venv/bin/python build.py
cp out.mp4 /var/www/html/silero.mp4
echo "ГОТОВО: http://89.207.252.121:8080/silero.mp4"
