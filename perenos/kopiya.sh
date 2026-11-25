#!/bin/bash
# kopiya.sh — запасная копия казахстанского сервера (Hoster.kz, 89.126.192.214)
# на шведском (HostUp, 206.168.213.210). Запускать НА ШВЕДСКОМ сервере.
#
# НИЧЕГО НЕ ВКЛЮЧАЕТ: на шведском боты не ставятся в расписание, службы не запускаются,
# VPN шведского сервера не трогается. На казахстанском ничего не меняется
# (только поставится программа rsync, если её там нет).
#
#   kz-kopiya            — снять копию или обновить её (повторять можно сколько угодно)
#   kz-kopiya proverka   — каждым ботом собрать пробный ролик БЕЗ выкладки, проверить входы в YouTube и скачивание
#   kz-kopiya otchet     — коротко: что на казахстанском сервере и что уже скопировано
#   kz-kopiya stop       — убрать ночное обновление копии (сама копия остаётся)
#
# Первый запуск — Терминал Мака:
#   ssh -t root@206.168.213.210 'curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/perenos/perenos/kopiya.sh | bash'
#
# Где что лежит на шведском:
#   боты, их данные, токены, программы — на тех же местах, что в Казахстане (/root/kz-bot, /root/clips-bot,
#     /root/quotes-bot, /opt/…, /var/www/…, /usr/local/bin/…), если такого места на шведском ещё не было;
#   всё остальное как есть (/etc с расписаниями и службами, crontab, ключи .ssh, старый VPN /opt/amnezia,
#     папки, совпавшие по имени со шведскими) — в /root/kz-kopiya/fs/;
#   опись казахстанского сервера — /root/kz-kopiya/opis/; журнал — /root/kz-kopiya/run.log.
#
# Весь код — внутри функций, запуск — последней строкой: так «curl … | bash» безопасен.

KZ=${KZ:-89.126.192.214}
K=/root/kz-kopiya
FS=$K/fs
OP=$K/opis
PLACED=$K/placed.txt
CONFL=$K/sovpali.txt
SELF=/usr/local/sbin/kz-kopiya
SELF_URL=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/perenos/perenos/kopiya.sh
SO=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -o ServerAliveInterval=30
    -o ServerAliveCountMax=10 -o ControlMaster=auto -o "ControlPath=/root/.ssh/cm-kz-%C" -o ControlPersist=10m)
RSH="ssh ${SO[*]} -o BatchMode=yes"
EXCL=(--exclude=.cache/pip --exclude=__pycache__)
APTENV=(env DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l)

say() { echo; echo "== $*"; }
kz()  { ssh -n "${SO[@]}" -o BatchMode=yes root@"$KZ" "$@" 9>&-; }
rs()  { rsync -aHs --numeric-ids --partial -e "$RSH" "$@" </dev/null 9>&-; }
gb()  { awk -v n="${1:-0}" 'BEGIN{printf "%.1f", n/1048576}'; }
norm() { tr 'A-Z' 'a-z' | sed 's/[_.]/-/g'; }

# ---------- вход шведского сервера на казахстанский ----------
dostup() {
  command -v rsync >/dev/null || { "${APTENV[@]}" apt-get install -y -qq rsync >/dev/null 2>&1 ||
    { apt-get update -qq >/dev/null 2>&1; "${APTENV[@]}" apt-get install -y -qq rsync >/dev/null 2>&1; }; }
  [ -f /root/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -C "hostup-kz-kopiya" -f /root/.ssh/id_ed25519 -q
  kz true 2>/dev/null && return 0
  if ( : </dev/tty ) 2>/dev/null; then
    say "Первый раз: даю шведскому серверу вход на казахстанский ($KZ)"
    echo "Сейчас появится:  root@$KZ's password:"
    echo "Это пароль КАЗАХСТАНСКОГО сервера. Введите его (буквы не видны — так и должно быть) и Enter."
    ssh-copy-id -i /root/.ssh/id_ed25519.pub -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 \
      root@"$KZ" </dev/tty >/dev/null 2>&1 9>&- || true
    kz true 2>/dev/null && { echo "Вход есть."; return 0; }
  fi
  echo
  echo "НЕ ВЫШЛО: шведский сервер не может зайти на казахстанский ($KZ)."
  echo "Можно добавить ключ с iPhone: «Команды» → «Сервер» (казахстанский) — вставить строку:"
  echo
  echo "mkdir -p /root/.ssh && echo \"$(cat /root/.ssh/id_ed25519.pub)\" >> /root/.ssh/authorized_keys && echo КЛЮЧ ДОБАВЛЕН"
  echo
  echo "…и потом запустить копию ещё раз."
  return 2
}

sohranit_sebya() {
  local tmp; tmp=$(mktemp)
  if curl -fsSL "$SELF_URL" -o "$tmp" 2>/dev/null && head -1 "$tmp" | grep -q '^#!/bin/bash'; then
    install -m 755 "$tmp" "$SELF"; rm -f "$tmp"; return 0
  fi
  rm -f "$tmp"; [ -x "$SELF" ]
}

# запуск в фоне: если закрыть окно или оборвётся связь — работа не прервётся
v_fon() {
  local mode=${1:-kopiya} logf="$K/run.log"
  [ "$mode" = proverka ] && logf="$K/proverka.log"
  if ! sohranit_sebya; then
    echo "Не смог сохранить скрипт — работаю прямо в этом окне (не закрывайте его)."
    if [ "$mode" = proverka ]; then proverka; else rabota; fi; return
  fi
  if ! flock -n "$K/.lock" true; then
    echo "Уже идёт копия или проверка. Посмотреть ход:  tail -f $K/run.log  (или $K/proverka.log)"
    tail -n 15 "$logf" 2>/dev/null; return 0
  fi
  KZK_FON=1 setsid nohup "$SELF" "$mode" > "$logf" 2>&1 < /dev/null &
  local pid=$!
  echo
  echo "Идёт в фоне — окно можно закрыть, работа не прервётся."
  if [ "$mode" = proverka ]; then echo "Обычно 10–40 минут. Итог потом:  tail -n 40 $logf"
  else echo "Обычно 10–40 минут. Итог потом:  kz-kopiya otchet"; fi
  sleep 2; tail -n +1 -f --pid="$pid" "$logf"
}

# ---------- основная работа ----------
rabota() {
  exec 9>"$K/.lock"
  flock -n 9 || { echo "Копия уже идёт — второй раз не запускаю."; return 0; }
  local t0; t0=$(date +%s)
  echo "Начало: $(date '+%d.%m.%Y %H:%M') (время шведского сервера)"
  if ! kz true 2>/dev/null; then
    echo "НЕТ СВЯЗИ с казахстанским сервером $KZ — копия не обновлена (прежняя на месте)."
    date '+%d.%m.%Y %H:%M нет связи с Казахстаном' > "$K/poslednyaya-oshibka.txt"; return 3
  fi
  if ! kz 'command -v rsync >/dev/null'; then
    say "На казахстанском нет rsync — ставлю (программа копирования, больше там ничего не меняю)"
    kz '(DEBIAN_FRONTEND=noninteractive apt-get install -y -qq rsync || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq rsync)) >/dev/null 2>&1'
    kz 'command -v rsync >/dev/null' || { echo "НЕ ВЫШЛО: rsync на казахстанском не ставится."; return 3; }
  fi
  zashchita || return 4
  opis_snyat
  mesto || return 4
  kopirovat
  pakety
  python_chast
  nochnoe
  date '+%d.%m.%Y %H:%M' > "$K/poslednyaya-kopiya.txt"
  rm -f "$K/poslednyaya-oshibka.txt"
  echo
  echo "Копия готова за $(( ($(date +%s) - t0) / 60 )) мин."
  otchet
}

# не портить копию, если казахстанский сервер переустановили или почистили
zashchita() {
  local mid all miss
  mid=$(kz 'cat /etc/machine-id 2>/dev/null')
  if [ -s "$K/machine-id" ] && [ -n "$mid" ] && [ "$mid" != "$(cat "$K/machine-id")" ]; then
    echo "!! Казахстанский сервер не тот, что раньше (переустановлен?). Копию НЕ обновляю, чтобы не испортить её."
    return 1
  fi
  [ -n "$mid" ] && echo "$mid" > "$K/machine-id"
  if [ -s "$PLACED" ]; then
    kz 'for b in /root /opt /var/www /srv /usr/local/bin /usr/local/lib; do ls -A1 "$b" 2>/dev/null | sed "s#^#$b/#"; done' > "$K/est-na-kz.txt"
    all=$(wc -l < "$PLACED"); miss=$(grep -cvxF -f "$K/est-na-kz.txt" "$PLACED")
    if [ "$miss" -gt $((all / 2)) ]; then
      echo "!! На казахстанском пропало $miss из $all скопированных мест — копию НЕ обновляю (вдруг сервер почистили)."
      return 1
    fi
  fi
  return 0
}

opis_snyat() {
  say "Опись казахстанского сервера"
  kz 'cat /etc/os-release; echo; uname -a; echo; uptime; echo "ядер: $(nproc)"; free -m; echo; df -h -x tmpfs -x devtmpfs -x overlay' > "$OP/os.txt" 2>&1
  kz 'crontab -l 2>/dev/null' > "$OP/crontab-root.txt" 2>/dev/null
  kz 'echo "### crontab root"; crontab -l 2>/dev/null; for f in /etc/cron.d/*; do echo; echo "### $f"; cat "$f"; done' > "$OP/cron.txt" 2>&1
  kz 'echo "### работают"; systemctl list-units --type=service --state=running --no-pager --no-legend; echo; echo "### включены"; systemctl list-unit-files --state=enabled --no-pager --no-legend; echo; echo "### таймеры"; systemctl list-timers --all --no-pager --no-legend' > "$OP/sluzhby.txt" 2>&1
  kz 'ss -ltnup' > "$OP/porty.txt" 2>&1
  kz 'docker ps -a --format "{{.Names}}  {{.Image}}  {{.Status}}" 2>/dev/null || echo "docker нет"' > "$OP/docker.txt" 2>&1
  kz 'du -sh /root/* /root/.[!.]* /opt/* /var/www/* /srv/* /home/* /usr/local/bin /usr/local/lib 2>/dev/null | sort -h' > "$OP/razmery.txt" 2>&1
  kz 'apt-mark showmanual 2>/dev/null' > "$OP/apt.txt" 2>&1
  kz 'for b in python3 node npm deno yt-dlp ffmpeg nginx caddy docker; do printf "%s: " $b; command -v $b || echo нет; done; python3 -V; node -v 2>/dev/null' > "$OP/programmy.txt" 2>&1
  kz 'nginx -T 2>/dev/null || echo "nginx нет"' > "$OP/nginx.txt" 2>&1
  kz 'python3 -m pip list --format=freeze 2>/dev/null' > "$OP/pip-sistema.txt" 2>&1
  kz 'find /root /opt /home /srv /var/www -maxdepth 4 -name pyvenv.cfg -not -path "*/.cache/*" 2>/dev/null' | sed 's#/pyvenv.cfg$##' > "$OP/venv.txt"
  local v
  while read -r v; do
    [ -n "$v" ] && kz "$v/bin/python -m pip freeze 2>/dev/null" > "$OP/pip$(echo "$v" | tr / _).txt" 2>&1
  done < "$OP/venv.txt"
  KZPY=$(kz 'python3 -c "import sys;print(\"%d.%d\"%sys.version_info[:2])"' 2>/dev/null)
  SWPY=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
  echo "Python: в Казахстане $KZPY, в Швеции $SWPY" | tee "$OP/python.txt"
  if [ -n "$KZPY" ] && [ "$KZPY" != "$SWPY" ]; then
    # разный Python: виртуальные окружения не копируем, а собираем заново по спискам
    local v2
    while read -r v; do
      [ -n "$v" ] || continue
      v2="$(basename "$(dirname "$v")")/$(basename "$v")/"
      EXCL+=("--exclude=$v2")
    done < "$OP/venv.txt"
  fi
}

mesto() {
  local need free
  need=$(kz 'du -skx /root /opt /var/www /srv /home /usr/local /etc /var/spool/cron 2>/dev/null | awk "{s+=\$1} END {print s+0}"')
  free=$(df -Pk /root | awk 'NR==2{print $4}')
  echo "На казахстанском к копии: $(gb "$need") ГБ, на шведском свободно: $(gb "$free") ГБ"
  if [ ! -s "$PLACED" ] && [ "${free:-0}" -lt $(( ${need:-0} + 3 * 1048576 )) ]; then
    echo "НЕ ХВАТАЕТ МЕСТА на шведском — копию не снимаю. Пришлите этот экран Claude."; return 1
  fi
  [ "${free:-0}" -lt $((2 * 1048576)) ] && { echo "На шведском меньше 2 ГБ свободно — копию не обновляю."; return 1; }
  return 0
}

# одна папка-основа: что можно — на своё место, что совпало со шведским — только в fs/
razlozhit() {
  local base=$1 skip=$2 e path dest list n=0
  kz "test -d $base" || return 0
  mkdir -p "$base"
  list=$(kz "ls -A1 $base 2>/dev/null")
  [ -n "$list" ] || return 0
  echo "-- $base"
  while IFS= read -r e; do
    [ -n "$e" ] || continue
    if [ -n "$skip" ] && printf '%s\n' "$e" | grep -qE "$skip"; then continue; fi
    path="$base/$e"
    if grep -qxF "$path" "$PLACED"; then
      dest=$base
    elif [ "$base" = /root ] && printf '%s\n' "$e" | grep -qxE '\.(cache|local|config)'; then
      dest=$base; echo "$path" >> "$PLACED"          # общие папки — дополняем, шведское не удаляется
    elif [ -e "$path" ] || [ -L "$path" ]; then
      dest=$FS$base; mkdir -p "$dest"
      grep -qxF "$path" "$CONFL" 2>/dev/null || echo "$path" >> "$CONFL"
    else
      dest=$base; echo "$path" >> "$PLACED"
    fi
    case "$e" in crontab.bak-*|*.bak-*|*.log) ;; *) echo "   $path";; esac
    rs "${EXCL[@]}" "root@$KZ:$path" "$dest/" || echo "   !! $path — не до конца (докопируется при следующем запуске)"
    n=$((n + 1))
  done <<< "$list"
}

kopirovat() {
  say "Копирую (молчит по несколько минут на больших папках — это нормально)"
  touch "$PLACED" "$CONFL"
  local p
  # как есть, только для справки и для переноса (здесь ничего не включается)
  for p in /etc /var/spool/cron /root/.ssh /opt/amnezia /home; do
    kz "test -e $p" || continue
    mkdir -p "$FS$p"
    rs "root@$KZ:$p/" "$FS$p/" && echo "   $p → $FS$p (как есть)" || echo "   !! $p — не до конца"
  done
  razlozhit /root '^(\.ssh|\.bash_history|\.bashrc|\.profile|\.lesshst|\.viminfo|\.wget-hsts|\.python_history|\.sudo_as_admin_successful|\.selected_editor|snap|kz-kopiya|\.docker|\.npm|\.ansible)$'
  razlozhit /opt '^(amnezia|containerd|docker.*)$'
  razlozhit /var/www ''
  razlozhit /srv ''
  razlozhit /usr/local/bin ''
  razlozhit /usr/local/lib ''
  chmod 700 "$K"
}

pakety() {
  say "Программы (apt): ставлю то, что есть в Казахстане и нет здесь — без запуска служб"
  local bad='^(linux-|grub|cloud|netplan|openssh|ssh$|systemd|ubuntu-|snapd|docker|containerd|amnezia|qemu|shim|efibootmgr|lxd|ufw|iptables|netfilter|nftables|firewalld|fail2ban|wireguard|openvpn|strongswan|resolvconf|ifupdown|network-manager|open-vm|xe-guest|hyperv|apparmor|initramfs|lvm2|mdadm|xfsprogs|btrfs|sudo$|cron$|rsyslog|landscape|walinuxagent|xray|x-ui|sing-box|shadowsocks)'
  grep -E '^[a-z0-9]' "$OP/apt.txt" | grep -vE "$bad" | sort -u > "$K/apt-nado.txt"
  dpkg-query -W -f='${Package}\n' 2>/dev/null | sort -u > "$K/apt-est.txt"
  comm -23 "$K/apt-nado.txt" "$K/apt-est.txt" > "$K/apt-net.txt"
  [ -s "$K/apt-net.txt" ] || { echo "   всё нужное уже стоит"; return 0; }
  apt-get update -qq >/dev/null 2>&1
  : > "$K/apt-stavit.txt"
  local p u own=0
  while read -r p; do
    apt-cache policy "$p" 2>/dev/null | grep -qE 'Candidate: [^ (]' && echo "$p" >> "$K/apt-stavit.txt"
  done < "$K/apt-net.txt"
  [ -s "$K/apt-stavit.txt" ] || { echo "   нового ставить нечего"; return 0; }
  echo "   ставлю: $(tr '\n' ' ' < "$K/apt-stavit.txt")"
  systemctl list-unit-files --state=enabled --no-legend 2>/dev/null | awk '{print $1}' | sort > "$K/en-do.txt"
  [ -e /usr/sbin/policy-rc.d ] && own=1
  [ $own = 0 ] && { printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d; chmod 755 /usr/sbin/policy-rc.d; }
  # shellcheck disable=SC2046
  if ! "${APTENV[@]}" apt-get install -y -q $(cat "$K/apt-stavit.txt") >> "$K/apt.log" 2>&1; then
    while read -r p; do
      "${APTENV[@]}" apt-get install -y -q "$p" >> "$K/apt.log" 2>&1 || echo "   !! не встало: $p"
    done < "$K/apt-stavit.txt"
  fi
  [ $own = 0 ] && rm -f /usr/sbin/policy-rc.d
  systemctl list-unit-files --state=enabled --no-legend 2>/dev/null | awk '{print $1}' | sort > "$K/en-posle.txt"
  for u in $(comm -13 "$K/en-do.txt" "$K/en-posle.txt"); do
    case "$u" in cron.service) continue ;; esac
    systemctl disable --now "$u" >/dev/null 2>&1 && echo "$u" >> "$K/otklyucheno.txt" &&
      echo "   новая служба $u — выключена (включим в день переноса)"
  done
}

nashe() {  # путь лежит внутри того, что мы положили на место
  local p
  while read -r p; do case "$1" in "$p"|"$p"/*) return 0 ;; esac; done < "$PLACED"
  return 1
}

python_chast() {
  say "Python: библиотеки ботов"
  "${APTENV[@]}" apt-get install -y -q python3-pip python3-venv >> "$K/apt.log" 2>&1 || true
  # системные библиотеки (поставленные в Казахстане через pip)
  local line name n spec v f h idx
  python3 -m pip list --format=freeze 2>/dev/null | cut -d= -f1 | norm | sort -u > "$K/pip-est.txt"
  grep '==' "$OP/pip-sistema.txt" 2>/dev/null | grep -E '^[A-Za-z0-9]' > "$K/pip-kz.txt"
  local sysbad='^(dbus-python|pygobject|python-apt|distro-info|ubuntu-pro-client|ubuntu-advantage-tools|cloud-init|ufw|command-not-found|systemd-python|netifaces|unattended-upgrades|ssh-import-id|launchpadlib|lazr|wadllib|sos|pycairo|ptyprocess|dbus)'
  while IFS= read -r line; do
    name=${line%%==*}; n=$(echo "$name" | norm)
    grep -qxF "$n" "$K/pip-est.txt" && continue
    echo "$n" | grep -qE "$sysbad" && continue
    spec=$name; [ "$KZPY" = "$SWPY" ] && spec=$line
    python3 -m pip install -q --break-system-packages "$spec" >> "$K/pip.log" 2>&1 ||
      python3 -m pip install -q --break-system-packages "$name" >> "$K/pip.log" 2>&1 ||
      echo "   !! pip не встало: $name"
  done < "$K/pip-kz.txt"
  # виртуальные окружения ботов
  while read -r v; do
    [ -n "$v" ] || continue
    nashe "$v" || { echo "   $v — папка совпала со шведской, пропускаю"; continue; }
    f="$OP/pip$(echo "$v" | tr / _).txt"
    h=$(md5sum < "$f" 2>/dev/null | cut -c1-12)
    idx=(); grep -q '+cpu' "$f" 2>/dev/null && idx=(--extra-index-url https://download.pytorch.org/whl/cpu)
    if [ -x "$v/bin/python" ] && "$v/bin/python" -c 'import sys' 2>/dev/null; then
      if [ "$KZPY" != "$SWPY" ] && [ ! -f "$v/.kz-kopiya-$h" ]; then
        "$v/bin/pip" install -q "${idx[@]}" -r "$f" >> "$K/pip.log" 2>&1 && touch "$v/.kz-kopiya-$h"
      fi
      echo "   $v — работает"; continue
    fi
    echo "   $v — собираю заново (может занять до 10–15 минут)"
    mkdir -p "$(dirname "$v")"
    python3 -m venv --clear "$v" >> "$K/pip.log" 2>&1 || { echo "   !! не получилось создать $v"; continue; }
    "$v/bin/pip" install -q -U pip >> "$K/pip.log" 2>&1
    if ! "$v/bin/pip" install -q "${idx[@]}" -r "$f" >> "$K/pip.log" 2>&1; then
      sed 's/[=<>~!@ ].*//' "$f" | grep -E '^[A-Za-z0-9]' | while read -r n; do
        "$v/bin/pip" install -q "${idx[@]}" "$n" >> "$K/pip.log" 2>&1 || echo "   !! в $v не встало: $n"
      done
    fi
    touch "$v/.kz-kopiya-$h"
  done < "$OP/venv.txt"
}

nochnoe() {
  [ -f /etc/cron.d/kz-kopiya ] && return 0
  [ -f "$K/nochnoe-ubrano" ] && return 0
  [ -x "$SELF" ] || return 0
  cat > /etc/cron.d/kz-kopiya <<'EOF'
# Ночное обновление запасной копии казахстанского сервера. Ничего не включает.
# Убрать: kz-kopiya stop
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
20 1 * * * root /usr/local/sbin/kz-kopiya tiho >> /root/kz-kopiya/noch.log 2>&1
EOF
  chmod 644 /etc/cron.d/kz-kopiya
  say "Каждую ночь в 01:20 (время сервера) копия будет обновляться сама"
}

# ---------- отчёт ----------
otchet() {
  echo
  echo "================ ОТЧЁТ ================"
  if [ -f "$K/poslednyaya-kopiya.txt" ]; then echo "Копия снята: $(cat "$K/poslednyaya-kopiya.txt") (время шведского сервера)"
  else echo "Полной копии ещё нет."; fi
  [ -f "$K/poslednyaya-oshibka.txt" ] && echo "Последняя попытка: $(cat "$K/poslednyaya-oshibka.txt")"
  [ -s "$OP/os.txt" ] || return 0
  echo "Казахстанский сервер: $(grep -m1 PRETTY_NAME "$OP/os.txt" | cut -d'"' -f2), $(awk '/^Mem/{print "память "$2" МБ"; exit}' "$OP/os.txt"); $(cat "$OP/python.txt" 2>/dev/null)"
  echo
  echo "Боты — на своих местах на шведском:"
  local d f
  for d in /root/*/; do
    d=${d%/}
    { [ -f "$d/run_daily.py" ] || [ -f "$d/config.json" ]; } || continue
    nashe "$d" || continue
    echo "   $d — $(du -sh "$d" 2>/dev/null | cut -f1)$( [ -f "$d/yt_token.json" ] && echo ', вход в YouTube скопирован')"
  done
  echo "Остальное на своих местах:"
  grep -E '^/(opt|var/www|srv|usr/local/bin)/' "$PLACED" 2>/dev/null | sed 's/^/   /' | head -40
  echo
  echo "Расписание в Казахстане (на шведском НЕ включено):"
  grep -vE '^[[:space:]]*(#|$)|^(SHELL|PATH|MAILTO)=' "$OP/crontab-root.txt" 2>/dev/null | cut -c1-150 | sed 's/^/   /'
  for f in "$FS"/etc/cron.d/*; do
    [ -f "$f" ] || continue
    case "$(basename "$f")" in e2scrub_all|popularity-contest|sysstat|php|.placeholder|anacron|certbot) continue ;; esac
    grep -vE '^[[:space:]]*(#|$)|^(SHELL|PATH|MAILTO)=' "$f" | cut -c1-150 | sed "s#^#   [cron.d/$(basename "$f")] #"
  done
  echo
  echo "Свои службы в Казахстане (на шведском НЕ запущены):"
  awk '/^### работают/{f=1;next} /^###/{f=0} f && NF{print $1}' "$OP/sluzhby.txt" |
    grep -vE '^(systemd-|dbus|cron|ssh|rsyslog|polkit|snapd|unattended|getty|serial-getty|user@|multipathd|ModemManager|udisks|qemu-guest|chrony|ntp|irqbalance|packagekit|containerd|docker|cloud|fwupd|atd|accounts-daemon|upower|thermald|lvm|apport|open-vm|hv-|haveged|uuidd|networkd|resolved|udev|journal|logind|timesyncd|qemu|vnstat|fail2ban|ufw|netplan|plymouth|finalrd|blk|setvtrgb|keyboard|console|kmod|apparmor|e2scrub|rc-local|wpa|NetworkManager|avahi|snap\.)' |
    sed 's/^/   /'
  echo "Открытые порты в Казахстане:"
  awk '$1=="tcp" && $2=="LISTEN" {n=split($5,a,":"); port=a[n]; p=""; if (match($0,/\(\("[^"]+"/)) p=substr($0,RSTART+3,RLENGTH-4); print port" "p}' "$OP/porty.txt" |
    sort -un | grep -vE '^(22|53) ' | sed 's/^/   порт /'
  if [ -s "$CONFL" ]; then
    echo; echo "Совпали по имени со шведскими — лежат только в $FS:"; sed 's/^/   /' "$CONFL"
  fi
  [ -s "$K/otklyucheno.txt" ] && { echo; echo "Поставлены, но выключены до переноса:"; sed 's/^/   /' "$K/otklyucheno.txt"; }
  echo
  if [ -f /etc/cron.d/kz-kopiya ]; then echo "Копия обновляется сама каждую ночь."; fi
  echo "На шведском ничего не включено: боты не по расписанию, службы не запущены, VPN не тронут."
  echo "======================================="
}

# ---------- пробные ролики, без выкладки ----------
proverka() {
  exec 9>"$K/.lock"
  flock -n 9 || { echo "Сейчас идёт копия — проверку запустите после неё."; return 0; }
  say "Пробные ролики: каждый бот собирает ролик и НИЧЕГО не выкладывает"
  local d PY rc vid log t
  for d in /root/*/; do
    d=${d%/}
    { [ -f "$d/run_daily.py" ] && [ -f "$d/config.json" ]; } || continue
    nashe "$d" || continue
    PY=python3; [ -x "$d/.venv/bin/python" ] && PY=$d/.venv/bin/python
    log="$K/proverka-$(basename "$d").log"
    echo; echo "-- $(basename "$d"): собираю (до 20 минут)…"
    touch "$K/.t0"; sleep 1
    ( cd "$d" && env TG_BOT_TOKEN= TG_CHAT_ID= timeout 1500 "$PY" run_daily.py --test ) > "$log" 2>&1 9>&-
    rc=$?
    vid=$(find "$d" -name '*.mp4' -newer "$K/.t0" -not -path '*/.venv/*' 2>/dev/null | head -1)
    if [ $rc = 0 ] && [ -n "$vid" ]; then
      echo "   OK: $vid ($(du -h "$vid" | cut -f1))"
      grep -qiE 'альбин' "$log" && grep -m1 -iE 'альбин' "$log" | cut -c1-160 | sed 's/^/   голос: /'
    else
      echo "   НЕ СОБРАЛОСЬ (код $rc). Конец журнала:"; tail -6 "$log" | cut -c1-200 | sed 's/^/     /'
    fi
  done
  say "Входы в YouTube — только проверка, что вход живой (ничего не выкладываю)"
  for t in $(find /root /opt -maxdepth 3 -name 'yt_token*.json' -not -path '/root/kz-kopiya/*' 2>/dev/null); do
    nashe "$t" || continue
    PY=python3; [ -x "$(dirname "$t")/.venv/bin/python" ] && PY="$(dirname "$t")/.venv/bin/python"
    r=$("$PY" - "$t" <<'PYEOF' 2>&1 | tail -1 | cut -c1-140
import json, sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
c = Credentials.from_authorized_user_info(json.load(open(sys.argv[1])))
c.refresh(Request())
print("OK — вход живой")
PYEOF
)
    echo "   $t: $r"
  done
  if command -v yt-dlp >/dev/null; then
    say "Скачивание с YouTube со шведского адреса (нужно нарезке «Кот Барсик»)"
    rm -f /tmp/kzk-yt.mp4
    if timeout 240 yt-dlp --js-runtimes deno -q -f "b[height<=360]" --no-playlist -o /tmp/kzk-yt.mp4 \
         "https://www.youtube.com/watch?v=fa7knKC0dNs" > "$K/proverka-yt.log" 2>&1 && [ -s /tmp/kzk-yt.mp4 ]; then
      echo "   OK — YouTube отдаёт видео на шведский сервер"
    else
      echo "   НЕ КАЧАЕТ: $(grep -m1 -E 'ERROR|error' "$K/proverka-yt.log" | cut -c1-180)"
    fi
    rm -f /tmp/kzk-yt.mp4
  fi
  command -v ffmpeg >/dev/null && echo "   ffmpeg есть" || echo "   !! ffmpeg нет"
  echo
  echo "Проверка закончена. Пришлите этот экран Claude."
}

main() {
  umask 022
  mkdir -p "$K" "$FS" "$OP" /root/.ssh
  chmod 700 "$K" /root/.ssh
  touch "$PLACED" "$CONFL"
  case "${1:-kopiya}" in
    otchet)   otchet ;;
    stop)     rm -f /etc/cron.d/kz-kopiya; touch "$K/nochnoe-ubrano"
              echo "Ночное обновление копии убрано. Сама копия осталась (в $K и на своих местах)." ;;
    proverka) if [ -n "${KZK_FON:-}" ]; then proverka; else v_fon proverka; fi ;;
    tiho)     rabota ;;
    kopiya)   if [ -n "${KZK_FON:-}" ]; then rabota; else dostup || return $?; v_fon kopiya; fi ;;
    *)        echo "Не знаю «$1». Есть: kz-kopiya | kz-kopiya proverka | kz-kopiya otchet | kz-kopiya stop"; return 1 ;;
  esac
}

main "$@"
