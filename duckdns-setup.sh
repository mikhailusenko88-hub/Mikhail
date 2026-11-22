#!/bin/bash
# duckdns-setup — сервер сам сообщает DuckDNS свой адрес раз в 5 минут.
# После «Change IPv4» в панели хостера имя через несколько минут само начинает указывать на новый адрес,
# и устройства с ключами по имени переподключаются без перевыпуска ключей.
#
# Поставить:   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/dns/duckdns-setup.sh | bash -s -- ИМЯ ТОКЕН
# Проверить:   duckdns-update        (печатает OK и адрес)
# Журнал:      tail /var/log/duckdns.log
# Убрать:      curl -fsSL .../duckdns-setup.sh | bash -s -- remove
set -u
if [ "${1:-}" = remove ]; then
  systemctl disable --now -q duckdns.timer 2>/dev/null
  rm -f /etc/systemd/system/duckdns.timer /etc/systemd/system/duckdns.service /usr/local/bin/duckdns-update /etc/duckdns.conf
  systemctl daemon-reload; echo "DuckDNS-обновление убрано."; exit 0
fi
NAME="${1:-}"; TOKEN="${2:-}"
NAME="${NAME%.duckdns.org}"
[ -n "$NAME" ] && [ -n "$TOKEN" ] || { echo "!! Нужно два значения: ИМЯ ТОКЕН"; exit 1; }
[[ "$NAME" =~ ^[a-z0-9-]+$ ]] || { echo "!! Имя — только латиница, цифры и дефис (без .duckdns.org)"; exit 1; }
[ "$(id -u)" = 0 ] || { echo "!! Нужен root"; exit 1; }

umask 077
printf 'NAME=%s\nTOKEN=%s\n' "$NAME" "$TOKEN" > /etc/duckdns.conf

cat > /usr/local/bin/duckdns-update <<'SCRIPT'
#!/bin/bash
# Сообщить DuckDNS основной адрес этого сервера (тот, через который сервер ходит в интернет по умолчанию).
. /etc/duckdns.conf
IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src"){print $(i+1); exit}}')
R=$(curl -fsS --max-time 25 "https://www.duckdns.org/update?domains=$NAME&token=$TOKEN&ip=$IP" 2>&1 | head -c 200)
LOG=/var/log/duckdns.log
echo "$(date '+%F %T') $NAME $IP $R" >> $LOG
tail -n 300 $LOG > $LOG.tmp 2>/dev/null && mv $LOG.tmp $LOG
echo "$R $IP"
SCRIPT
chmod 700 /usr/local/bin/duckdns-update

cat > /etc/systemd/system/duckdns.service <<'UNIT'
[Unit]
Description=DuckDNS: сообщить адрес сервера
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/duckdns-update
UNIT
cat > /etc/systemd/system/duckdns.timer <<'UNIT'
[Unit]
Description=DuckDNS каждые 5 минут
[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now -q duckdns.timer

echo "== Проверка"
R=$(/usr/local/bin/duckdns-update)
echo "   DuckDNS ответил: $R"
case "$R" in
  OK*) echo "   Готово: $NAME.duckdns.org будет обновляться сам каждые 5 минут." ;;
  *)   echo "!! DuckDNS ответил не OK — проверьте имя и токен (тогда запустите команду ещё раз с верными)." ;;
esac
sleep 3
echo "   Имя сейчас указывает на: $(getent ahostsv4 $NAME.duckdns.org | awk 'NR==1{print $1}')"
