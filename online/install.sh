#!/bin/bash
# Ставит онлайн-сервер игры «Шарики.io» отдельной службой ballio на порт 8091.
# Ничего другого не трогает: nginx, VPN, сайты и мебельные страницы остаются как есть.
# Удалить полностью:  systemctl disable --now ballio; rm -f /etc/systemd/system/ballio.service; rm -rf /opt/ballio; systemctl daemon-reload
set -u
PORT=8091
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SRC="$DIR/server.js"
say() { echo "== $*"; }
[ -f "$SRC" ] || { say "Не нашёл $SRC — ничего не меняю"; exit 1; }
NODE="$(command -v node 2>/dev/null || true)"
if [ -z "$NODE" ]; then for p in /usr/local/bin/node /usr/bin/node /root/.nvm/versions/node/*/bin/node; do [ -x "$p" ] && NODE="$p"; done; fi
[ -n "$NODE" ] || { say "На сервере нет Node.js — ничего не меняю"; exit 1; }
say "Node.js: $NODE $($NODE -v 2>/dev/null)"
RUNNODE="$NODE"
case "$NODE" in /root/*) mkdir -p /opt/ballio && cp -f "$NODE" /opt/ballio/node && chmod 755 /opt/ballio/node && RUNNODE=/opt/ballio/node ;; esac
if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  if systemctl is-active --quiet ballio; then say "Служба ballio уже работает — обновляю"; else say "Порт $PORT занят другой программой — ничего не меняю"; ss -ltnp 2>/dev/null | grep ":$PORT "; exit 1; fi
fi
mkdir -p /opt/ballio && cp -f "$SRC" /opt/ballio/server.js && chmod 644 /opt/ballio/server.js
cat > /etc/systemd/system/ballio.service <<UNIT
[Unit]
Description=Ballio online arena (game server)
After=network.target

[Service]
Environment=PORT=$PORT
Environment=WATCH=$SRC
ExecStartPre=+/bin/cp -f $SRC /opt/ballio/server.js
ExecStart=$RUNNODE /opt/ballio/server.js
User=nobody
Restart=always
RestartSec=2
NoNewPrivileges=true
MemoryMax=300M

[Install]
WantedBy=multi-user.target
UNIT
# открыть порт, только если на сервере включён фаервол
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then ufw allow $PORT/tcp >/dev/null && say "Открыл порт $PORT в ufw"; fi
if command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state 2>/dev/null | grep -q running; then firewall-cmd --permanent --add-port=$PORT/tcp >/dev/null && firewall-cmd --reload >/dev/null && say "Открыл порт $PORT в firewalld"; fi
if iptables -S INPUT 2>/dev/null | head -1 | grep -q "DROP" && ! iptables -C INPUT -p tcp --dport $PORT -j ACCEPT 2>/dev/null; then iptables -I INPUT -p tcp --dport $PORT -j ACCEPT && say "Открыл порт $PORT в iptables"; fi
systemctl daemon-reload
systemctl enable ballio >/dev/null 2>&1
systemctl restart ballio
sleep 3
if curl -s --max-time 4 "http://127.0.0.1:$PORT/health" | grep -q '"ok":1'; then
  say "ГОТОВО: сервер игры работает. Ссылка: http://$(curl -s --max-time 3 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}'):8080/mebel/ip52gz08/online/"
else
  say "Служба не ответила, последние строки журнала:"; journalctl -u ballio -n 15 --no-pager
fi
