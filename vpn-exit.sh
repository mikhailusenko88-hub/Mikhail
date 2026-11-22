#!/bin/bash
# vpn-exit — VPN-трафик (контейнеры Amnezia) выходит в интернет через ВТОРОЙ адрес сервера.
# Устройства по-прежнему подключаются к основному адресу (вход), а сайты и приложения видят только второй (выход).
# Сам сервер (SSH, DuckDNS, обновления) ходит в интернет по-старому, через основной адрес.
#
# Поставить:   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/dns/vpn-exit.sh | bash -s -- ВТОРОЙ_IP
# Потом на сервере:  vpn-exit status   |   vpn-exit remove
# После установки скрипт сам проверяет, с какого адреса VPN выходит в интернет; если не с второго — всё откатывает.
set -u
SELF_URL=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/dns/vpn-exit.sh
BIN=/usr/local/bin/vpn-exit
CONF=/etc/vpn-exit.conf
UNIT=/etc/systemd/system/vpn-exit.service
TIMER=/etc/systemd/system/vpn-exit.timer
T=177; MARK=0x177; P_FROM=1770; P_MARK=1771

say(){ echo "$*"; }
ip_of_if(){ ip -4 -o addr show dev "$1" scope global 2>/dev/null | awk '{split($4,a,"/"); print a[1]; exit}'; }
if_of_ip(){ ip -4 -o addr show 2>/dev/null | awk -v ip="$1" '{split($4,a,"/"); if (a[1]==ip) {print $2; exit}}'; }
pfx_of_ip(){ ip -4 -o addr show 2>/dev/null | awk -v ip="$1" '{split($4,a,"/"); if (a[1]==ip) {print a[2]; exit}}'; }
net_of(){ python3 -c "import ipaddress,sys; n=ipaddress.ip_interface(sys.argv[1]).network; print(n.with_prefixlen, n.network_address+1)" "$1"; }
phys_nics(){ for d in /sys/class/net/*; do [ -e "$d/device" ] && basename "$d"; done; }
trace_ip(){ curl -s --max-time 12 https://1.1.1.1/cdn-cgi/trace 2>/dev/null | awk -F= '/^ip=/{print $2}'; }
awg_ct(){ docker ps --format '{{.Names}}' 2>/dev/null | grep -E '^amnezia-(awg|wireguard|xray)' | head -1; }

detect(){ # -> XIF ENTRY_IF ENTRY_GW ENTRY_IP XPFX XNET XGW NEED_ADDR
  NEED_ADDR=0
  XIF=$(if_of_ip "$EXIT_IP")
  if [ -z "$XIF" ]; then # адрес ещё не настроен в системе — ищем сетевую карту без адреса
    local c=() n
    for n in $(phys_nics); do [ -z "$(ip_of_if "$n")" ] && c+=("$n"); done
    if [ ${#c[@]} -eq 1 ]; then XIF=${c[0]}; NEED_ADDR=1; fi
  fi
  read -r ENTRY_IF ENTRY_GW < <(ip -4 route show default table main | awk -v x="${XIF:-none}" '{d="";g=""; for(i=1;i<NF;i++){if($i=="dev")d=$(i+1); if($i=="via")g=$(i+1)} if(d!=x){print d, g; exit}}')
  ENTRY_IP=$(ip_of_if "${ENTRY_IF:-none}")
  XPFX=$(pfx_of_ip "$EXIT_IP"); [ -z "$XPFX" ] && XPFX=24
  read -r XNET XGW < <(net_of "$EXIT_IP/$XPFX")
  local g; g=$(ip -4 route show default table main dev "${XIF:-none}" 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="via"){print $(i+1); exit}}')
  [ -n "$g" ] && XGW=$g
}

jump(){ # таблица цепочка-откуда цепочка-куда
  iptables -t "$1" -C "$2" -j "$3" 2>/dev/null || iptables -t "$1" -I "$2" 1 -j "$3"
}

up(){
  . "$CONF"
  ip link set "$XIF" up
  ip_of_if "$XIF" | grep -q . || ip addr add "$EXIT_IP/$XPFX" dev "$XIF"
  # основной маршрут сервера — только через вход
  while ip route del default dev "$XIF" table main 2>/dev/null; do :; done
  ip -4 route show default table main | grep -q "dev $ENTRY_IF" || ip route add default via "$ENTRY_GW" dev "$ENTRY_IF"
  # отдельная таблица для выхода
  ip route flush table $T 2>/dev/null
  ip route add "$XNET" dev "$XIF" src "$EXIT_IP" table $T
  ip route add default via "$XGW" dev "$XIF" src "$EXIT_IP" table $T onlink
  ip rule del pref $P_FROM 2>/dev/null; ip rule add pref $P_FROM from "$EXIT_IP" lookup $T
  ip rule del pref $P_MARK 2>/dev/null; ip rule add pref $P_MARK fwmark $MARK lookup $T
  sysctl -q -w net.ipv4.ip_forward=1 net.ipv4.conf.all.rp_filter=2 net.ipv4.conf.default.rp_filter=2 "net.ipv4.conf.$XIF.rp_filter=2"
  # метка: новые соединения ИЗ контейнеров в интернет (не ответы клиентам, не локальные адреса)
  iptables -t mangle -N VPNX 2>/dev/null; iptables -t mangle -F VPNX
  iptables -t mangle -A VPNX -i lo -j RETURN
  iptables -t mangle -A VPNX -i "$ENTRY_IF" -j RETURN
  iptables -t mangle -A VPNX -i "$XIF" -j RETURN
  iptables -t mangle -A VPNX -m conntrack --ctstate DNAT -j RETURN
  # пакеты с портов самих VPN-служб (ответы устройствам) — всегда через вход, чтобы устройства не узнали второй адрес
  local c pr
  for c in $(docker ps --format '{{.Names}}' 2>/dev/null | grep '^amnezia-'); do
    for pr in $(docker port "$c" 2>/dev/null | awk '{print $1}' | sort -u); do
      iptables -t mangle -A VPNX -p "${pr#*/}" --sport "${pr%/*}" -j RETURN
    done
  done
  iptables -t mangle -A VPNX -m addrtype --dst-type LOCAL -j RETURN
  iptables -t mangle -A VPNX -d 0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.168.0.0/16,224.0.0.0/3 -j RETURN
  iptables -t mangle -A VPNX -j MARK --set-mark $MARK
  jump mangle PREROUTING VPNX
  # подмена адреса на выходе
  iptables -t nat -N VPNX 2>/dev/null; iptables -t nat -F VPNX
  iptables -t nat -A VPNX -o "$XIF" -m mark --mark $MARK -j SNAT --to-source "$EXIT_IP"
  jump nat POSTROUTING VPNX
  # снаружи на второй адрес — ничего не открыто (ни SSH, ни VPN): только ответы на наши соединения
  iptables -N VPNX_IN 2>/dev/null; iptables -F VPNX_IN
  iptables -A VPNX_IN -i "$XIF" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
  iptables -A VPNX_IN -i "$XIF" -p udp --sport 67 --dport 68 -j RETURN
  iptables -A VPNX_IN -i "$XIF" -j DROP
  jump filter INPUT VPNX_IN
  iptables -n -L DOCKER-USER >/dev/null 2>&1 && jump filter DOCKER-USER VPNX_IN
  return 0
}

down(){
  iptables -t mangle -D PREROUTING -j VPNX 2>/dev/null; iptables -t mangle -F VPNX 2>/dev/null; iptables -t mangle -X VPNX 2>/dev/null
  iptables -t nat -D POSTROUTING -j VPNX 2>/dev/null; iptables -t nat -F VPNX 2>/dev/null; iptables -t nat -X VPNX 2>/dev/null
  iptables -D INPUT -j VPNX_IN 2>/dev/null; iptables -D DOCKER-USER -j VPNX_IN 2>/dev/null
  iptables -F VPNX_IN 2>/dev/null; iptables -X VPNX_IN 2>/dev/null
  ip rule del pref $P_MARK 2>/dev/null; ip rule del pref $P_FROM 2>/dev/null
  ip route flush table $T 2>/dev/null
  return 0
}

check(){ # выход VPN через второй адрес?
  local ct pid got host
  ct=$(awg_ct)
  host=$(trace_ip)
  say "   сервер сам выходит в интернет с: ${host:-?}  (должен быть основной $ENTRY_IP)"
  if [ -z "$ct" ]; then say "!! не нашёл контейнер Amnezia (docker ps)"; return 1; fi
  pid=$(docker inspect -f '{{.State.Pid}}' "$ct" 2>/dev/null)
  got=$(nsenter -t "$pid" -n curl -s --max-time 12 https://1.1.1.1/cdn-cgi/trace 2>/dev/null | awk -F= '/^ip=/{print $2}')
  say "   VPN ($ct) выходит в интернет с: ${got:-нет ответа}  (должен быть второй $EXIT_IP)"
  [ "$got" = "$EXIT_IP" ]
}

status(){
  [ -f "$CONF" ] || { say "vpn-exit не установлен."; return 1; }
  . "$CONF"
  say "== Вход (к нему подключаются устройства): $ENTRY_IP на $ENTRY_IF"
  say "== Выход (его видят сайты):               $EXIT_IP на $XIF, шлюз $XGW"
  check && say "== Всё в порядке." || say "!! Выход работает не через второй адрес."
}

install(){
  [[ "$EXIT_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { say "!! Укажите второй адрес, например: bash -s -- 103.177.249.102"; exit 1; }
  [ "$(id -u)" = 0 ] || { say "!! Нужен root"; exit 1; }
  for c in iptables ip docker nsenter curl python3; do command -v $c >/dev/null || { say "!! На сервере нет $c"; exit 1; }; done
  detect
  say "== Нашёл на сервере"
  say "   вход:  ${ENTRY_IF:-?}  ${ENTRY_IP:-?}  шлюз ${ENTRY_GW:-?}"
  say "   выход: ${XIF:-?}  $EXIT_IP/$XPFX  шлюз $XGW$( [ $NEED_ADDR = 1 ] && echo '  (адрес на карту поставлю сам)')"
  if [ -z "$XIF" ] || [ -z "$ENTRY_IF" ] || [ -z "$ENTRY_GW" ] || [ -z "$ENTRY_IP" ] || [ "$XIF" = "$ENTRY_IF" ]; then
    say ""; say "!! Не смог однозначно определить сетевые карты — ничего не менял. Пришлите это:"
    ip -br addr; ip -4 route show table main; exit 1
  fi
  printf 'EXIT_IP=%s\nXIF=%s\nXPFX=%s\nXNET=%s\nXGW=%s\nENTRY_IF=%s\nENTRY_GW=%s\nENTRY_IP=%s\n' \
    "$EXIT_IP" "$XIF" "$XPFX" "$XNET" "$XGW" "$ENTRY_IF" "$ENTRY_GW" "$ENTRY_IP" > "$CONF"
  down; up
  say ""; say "== Проверка"
  sleep 2
  if ! check; then
    say ""; say "!! Выход через второй адрес не заработал — откатываю, всё как было."
    down; rm -f "$CONF"
    say "   Для разбора пришлите фото экрана. Маршруты сейчас:"; ip -4 route show table main | head -5
    exit 1
  fi
  if curl -fsSL --max-time 30 "$SELF_URL" -o "$BIN.new"; then mv "$BIN.new" "$BIN"; chmod 700 "$BIN"; fi
  if [ -x "$BIN" ]; then
    cat > "$UNIT" <<UNITEOF
[Unit]
Description=vpn-exit: VPN выходит в интернет через второй адрес
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=$BIN up
UNITEOF
    cat > "$TIMER" <<UNITEOF
[Unit]
Description=vpn-exit: подтверждать правила раз в 10 минут
[Timer]
OnBootSec=40s
OnUnitActiveSec=10min
[Install]
WantedBy=timers.target
UNITEOF
    systemctl daemon-reload; systemctl enable --now -q vpn-exit.timer
  else
    say "   (не скачал vpn-exit с GitHub — выход работает, но после перезагрузки сервера команду надо будет повторить)"
  fi
  say ""; say "== Готово: устройства подключаются к $ENTRY_IP, а в интернет VPN выходит с $EXIT_IP."
  say "   Проверить: vpn-exit status    Убрать: vpn-exit remove"
}

case "${1:-}" in
  up) up ;;
  down) down ;;
  status) status ;;
  remove) [ -f "$CONF" ] && . "$CONF"; down; systemctl disable --now -q vpn-exit.timer 2>/dev/null; rm -f "$UNIT" "$TIMER" "$CONF" "$BIN"; systemctl daemon-reload; say "vpn-exit убран: VPN снова выходит через основной адрес." ;;
  *) EXIT_IP="${1:-}"; install ;;
esac
