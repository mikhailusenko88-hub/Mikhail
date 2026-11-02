#!/bin/bash
# Голос рассказчика «Альбина» для «Мультиков» — установка на свой сервер (Ubuntu/Debian).
# Ставит отдельную службу multik-tts на порт 8095. VPN, сайты и nginx не трогает.
# Запуск (вывод — в /root/multik-tts.log):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel-3d/tools/multik/tts/setup.sh -o /root/multik-tts-setup.sh && nohup bash /root/multik-tts-setup.sh > /root/multik-tts.log 2>&1 &
set -e
D=/opt/multik-tts
B=${TTS_SRC:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel-3d/tools/multik/tts}
PORT=8095
echo "== 1/6 пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip ffmpeg curl >/dev/null

echo "== 2/6 память"
mem=$(free -m | awk '/Mem:/{print $2}'); sw=$(free -m | awk '/Swap:/{print $2}')
echo "память ${mem} МБ, подкачка ${sw} МБ"
if [ $((mem + sw)) -lt 2500 ] && [ ! -f /swapfile-tts ]; then
  fallocate -l 2G /swapfile-tts && chmod 600 /swapfile-tts && mkswap /swapfile-tts >/dev/null && swapon /swapfile-tts
  grep -q swapfile-tts /etc/fstab || echo '/swapfile-tts none swap sw 0 0' >> /etc/fstab
  echo "добавил подкачку 2 ГБ"
fi

echo "== 3/6 python (несколько минут)"
id multiktts >/dev/null 2>&1 || useradd --system --home-dir $D --shell /usr/sbin/nologin multiktts
mkdir -p $D/cache $D/hf
[ -x $D/venv/bin/python ] || python3 -m venv $D/venv
$D/venv/bin/pip install -q --upgrade pip
$D/venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
$D/venv/bin/pip install -q numpy ruaccent

echo "== 4/6 голос"
[ -s $D/v5_cis_base.pt ] || curl -fsSL -o $D/v5_cis_base.pt https://models.silero.ai/models/tts/ru/v5_cis_base.pt
curl -fsSL -o $D/server.py "$B/server.py"
chown -R multiktts: $D

echo "== 5/6 служба"
cat > /etc/systemd/system/multik-tts.service <<EOF
[Unit]
Description=Multik narrator voice (Silero ru_albina)
After=network-online.target

[Service]
User=multiktts
WorkingDirectory=$D
Environment=PORT=$PORT
Environment=HF_HOME=$D/hf
Environment=OMP_NUM_THREADS=2
ExecStart=$D/venv/bin/python $D/server.py
Restart=always
RestartSec=5
Nice=10
CPUQuota=150%

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable multik-tts >/dev/null 2>&1
systemctl restart multik-tts
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then ufw allow $PORT/tcp >/dev/null && echo "открыл порт $PORT"; fi

echo "== 6/6 проверка (первый запуск до 5 минут: скачиваются словари ударений)"
for i in $(seq 1 100); do
  if curl -fs localhost:$PORT/health | grep -q '"ready": true'; then break; fi
  sleep 5
done
if curl -fs -o /tmp/multik-tts-test.wav "localhost:$PORT/tts?text=%D0%96%D0%B8%D0%BB%D0%B8-%D0%B1%D1%8B%D0%BB%D0%B8%20%D0%BA%D0%BE%D1%82%20%D0%B8%20%D0%BC%D1%8B%D1%88%D0%BE%D0%BD%D0%BE%D0%BA." && [ "$(stat -c %s /tmp/multik-tts-test.wav)" -gt 20000 ]; then
  echo "ГОТОВО: голос рассказчика работает на порту $PORT"
else
  echo "ОШИБКА: голос не отвечает. Последние строки службы:"
  journalctl -u multik-tts -n 30 --no-pager || true
  exit 1
fi
