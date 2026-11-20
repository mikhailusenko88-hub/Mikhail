#!/bin/bash
# kz-bridge — мост из России к серверу в Казахстане.
# Этот сервер принимает подключения на своих портах и пересылает их на казахстанский сервер.
# VPN здесь не ставится и трафик не расшифровывается — только переброска портов (iptables DNAT).
#
# Сначала проверка (ничего не меняет):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/most/kz-bridge.sh | bash -s -- НОВЫЙ_IP --dry
# Поставить мост или сменить адрес Казахстана:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/most/kz-bridge.sh | bash -s -- НОВЫЙ_IP
# Потом на этом сервере:  kz-bridge status   |   kz-bridge remove
set -u
SELF_URL=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/most/kz-bridge.sh
BIN=/usr/local/bin/kz-bridge
CONF=/etc/kz-bridge.conf
UNIT=/etc/systemd/system/kz-bridge.service
# протокол  порт-здесь(желательный)  порт-в-Казахстане  что-это
# Порты Amnezia оставлены такими же, как в Казахстане: тогда Amnezia сама выдаёт рабочие ключи с адресом моста.
MAP_DEFAULT="tcp 2222 22 SSH_(команда_«Сервер»)
tcp 8443 8443 XRay_XHTTP_(Happ)
tcp 8444 443 XRay_Reality_(Happ)
tcp 445 445 Amnezia_XRay
udp 445 445 Amnezia_XRay_(udp)
udp 39894 39894 AmneziaWG
tcp 8080 8080 Страницы_мебели_и_Барсика"

DRY=0; FORCE=0; KZ_IP=""; MAP=""

say() { echo "$*"; }
ipt() { if [ "$DRY" = 1 ]; then echo "   iptables $*"; else iptables "$@"; fi; }
jump() { # таблица цепочка-откуда цепочка-куда
  if [ "$DRY" = 1 ]; then echo "   iptables -t $1 -I $2 1 -j $3"; return; fi
  iptables -t "$1" -C "$2" -j "$3" 2>/dev/null || iptables -t "$1" -I "$2" 1 -j "$3"
}
busy() { # протокол порт -> 0, если порт на этом сервере уже кем-то занят
  command -v ss >/dev/null || return 1
  if [ "$1" = tcp ]; then ss -Hltn "sport = :$2" 2>/dev/null | grep -q .; else ss -Hlun "sport = :$2" 2>/dev/null | grep -q .; fi
}
reach() { timeout 6 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; }
my_ip() { ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src"){print $(i+1); exit}}'; }

pick_ports() { # из MAP_DEFAULT (или прежнего MAP) -> MAP с портами, свободными на этом сервере
  local old="" out="" pr lp rp name n used=" "
  [ -f "$CONF" ] && old=$(. "$CONF"; echo "$MAP")
  while read -r pr lp rp name; do
    [ -z "$pr" ] && continue
    # если мост уже стоял — берём прежний порт, чтобы в приложениях ничего не менять
    n=$(echo "$old" | awk -v p="$pr" -v r="$rp" '$1==p && $3==r {print $2; exit}')
    if [ -z "$n" ]; then
      n=$lp
      while busy "$pr" "$n" || [[ "$used" == *" $pr/$n "* ]]; do n=$((n+1)); done
      [ "$n" != "$lp" ] && say "   порт $pr $lp уже занят — для «${name//_/ }» беру $n" >&2
    fi
    used="$used$pr/$n "
    out="$out$pr $n $rp $name"$'\n'
  done <<< "$MAP_DEFAULT"
  printf '%s' "$out"
}

up() {
  [ -f "$CONF" ] && . "$CONF"
  [ -n "$KZ_IP" ] || { say "!! Нет адреса Казахстана в $CONF"; return 1; }
  if [ "$DRY" = 1 ]; then echo "   sysctl -w net.ipv4.ip_forward=1"; else
    sysctl -q -w net.ipv4.ip_forward=1; echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-kz-bridge.conf; fi
  if [ "$DRY" = 0 ]; then
    iptables -t nat -N KZB_PRE 2>/dev/null; iptables -t nat -F KZB_PRE
    iptables -t nat -N KZB_POST 2>/dev/null; iptables -t nat -F KZB_POST
    iptables -N KZB_FWD 2>/dev/null; iptables -F KZB_FWD
  fi
  jump nat PREROUTING KZB_PRE; jump nat POSTROUTING KZB_POST; jump filter FORWARD KZB_FWD
  if [ "$DRY" = 0 ] && iptables -n -L DOCKER-USER >/dev/null 2>&1; then jump filter DOCKER-USER KZB_FWD; fi
  local pr lp rp name
  while read -r pr lp rp name; do
    [ -z "$pr" ] && continue
    ipt -t nat -A KZB_PRE -p "$pr" --dport "$lp" -m addrtype --dst-type LOCAL -j DNAT --to-destination "$KZ_IP:$rp"
    ipt -t nat -A KZB_POST -p "$pr" -d "$KZ_IP" --dport "$rp" -j MASQUERADE
  done <<< "$MAP"
  ipt -A KZB_FWD -d "$KZ_IP" -j ACCEPT
  ipt -A KZB_FWD -s "$KZ_IP" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
}

down() {
  iptables -t nat -D PREROUTING -j KZB_PRE 2>/dev/null
  iptables -t nat -D POSTROUTING -j KZB_POST 2>/dev/null
  iptables -D FORWARD -j KZB_FWD 2>/dev/null
  iptables -D DOCKER-USER -j KZB_FWD 2>/dev/null
  for c in KZB_PRE KZB_POST; do iptables -t nat -F $c 2>/dev/null; iptables -t nat -X $c 2>/dev/null; done
  iptables -F KZB_FWD 2>/dev/null; iptables -X KZB_FWD 2>/dev/null
}

table() { # печать таблицы для приложений
  local me pr lp rp name; me=$(my_ip)
  say ""
  say "== Мост: $me  →  Казахстан $KZ_IP"
  say "   В приложениях адрес сервера: $me, порты:"
  while read -r pr lp rp name; do
    [ -z "$pr" ] && continue
    printf '   %-30s %s %-5s → %s\n' "${name//_/ }" "$pr" "$lp" "$rp"
  done <<< "$MAP"
}

check_kz() { # видит ли этот сервер Казахстан (только tcp-порты)
  local ok=0 bad=0 pr lp rp name
  say ""; say "== Проверка: этот сервер → Казахстан $KZ_IP"
  while read -r pr lp rp name; do
    [ "$pr" = tcp ] || continue
    if reach "$KZ_IP" "$rp"; then say "   $rp ОТКРЫТ"; ok=$((ok+1)); else say "   $rp ЗАКРЫТ"; bad=$((bad+1)); fi
  done <<< "$(echo "$MAP" | sort -u -k3,3)"
  [ $ok -gt 0 ]
}

status() {
  [ -f "$CONF" ] || { say "Мост не установлен."; return 1; }
  . "$CONF"; table; check_kz
  say ""; say "== Сколько подключений прошло через мост (пакеты)"
  iptables -t nat -n -v -L KZB_PRE 2>/dev/null | awk 'NR>2 {print "   " $1 " пак.  " $NF " " $(NF-1)}'
}

install() {
  [[ "$KZ_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { say "!! Укажите адрес Казахстана, например: bash -s -- 89.1.2.3"; exit 1; }
  [ "$DRY" = 1 ] || [ "$(id -u)" = 0 ] || { say "!! Нужен root"; exit 1; }
  command -v iptables >/dev/null || { say "!! На сервере нет iptables"; exit 1; }
  MAP=$(pick_ports)
  table
  if ! check_kz && [ "$FORCE" = 0 ]; then
    say ""; say "!! С этого сервера Казахстан $KZ_IP не открывается — мост работать не будет. Ничего не менял."
    exit 1
  fi
  if [ "$DRY" = 1 ]; then
    say ""; say "== Будет сделано (режим проверки, ничего не меняю):"; up
    say ""; say "Проверка окончена. Чтобы поставить мост — та же команда без --dry."
    exit 0
  fi
  printf 'KZ_IP=%s\nMAP="%s"\n' "$KZ_IP" "$MAP" > "$CONF"
  if curl -fsSL --max-time 30 "$SELF_URL" -o "$BIN.new"; then mv "$BIN.new" "$BIN"; chmod +x "$BIN"
  else say "   (не скачал kz-bridge с GitHub — мост работает, но после перезагрузки сервера его надо будет поставить заново)"; fi
  if [ -x "$BIN" ]; then
    cat > "$UNIT" <<UNITEOF
[Unit]
Description=kz-bridge: переброска портов в Казахстан
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$BIN up
ExecStop=$BIN down
[Install]
WantedBy=multi-user.target
UNITEOF
    systemctl daemon-reload; systemctl enable -q kz-bridge.service
  fi
  down; up && { say ""; say "== Мост работает. Проверить: kz-bridge status   Убрать: kz-bridge remove"; }
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  status) status ;;
  remove) down; systemctl disable -q kz-bridge.service 2>/dev/null; rm -f "$UNIT" "$CONF" "$BIN" /etc/sysctl.d/99-kz-bridge.conf; systemctl daemon-reload 2>/dev/null; say "Мост убран." ;;
  *) for a in "$@"; do case "$a" in --dry) DRY=1;; --force) FORCE=1;; *) KZ_IP=$a;; esac; done; install ;;
esac
