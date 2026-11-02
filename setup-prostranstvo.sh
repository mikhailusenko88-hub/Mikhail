#!/usr/bin/env bash
# =============================================================================
#  setup-prostranstvo.sh — установка сервера магазина «Пространство»
#  (Selectel, Ubuntu 24.04 LTS). Запускать от root одной командой:
#
#    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-prostranstvo.sh | bash -s -- ДОМЕН EMAIL
#
#  Пример:  ... | bash -s -- prostranstvo-dekor.ru name@example.ru
#
#  Что делает: ставит nginx, забирает сайт из GitHub (ветка mebel, папка 0f7s1eez)
#  и обновляет его каждую минуту, кладёт three.js r128 в /mebel/_lib/, включает
#  HTTPS (Let's Encrypt), firewall ufw, fail2ban и автообновления безопасности.
#
#  Повторный запуск безопасен (скрипт идемпотентный). Без параметров повторный
#  запуск берёт домен и email из /etc/prostranstvo/prostranstvo.conf.
#  Секретов в скрипте нет и быть не должно — репозиторий открытый.
# =============================================================================
set -Eeuo pipefail
export LC_ALL=C.UTF-8

# --- Постоянные настройки ----------------------------------------------------
# (без readonly: те же имена читаются из /etc/prostranstvo/prostranstvo.conf в подоболочках)
REPO_URL="https://github.com/mikhailusenko88-hub/Mikhail.git"
REPO_BRANCH="mebel"
SITE_SUBDIR="0f7s1eez"          # папка сайта в ветке mebel
OLD_PATH="/mebel/0f7s1eez"      # старый адрес сайта (ссылки в фиде Авито)
LIB_URL_PATH="/mebel/_lib"      # отсюда сайт грузит three.js
SITE_USER="prostranstvo"        # отдельный пользователь для сайта
SRC_DIR="/opt/prostranstvo-src" # копия репозитория (git)
WWW_DIR="/var/www/prostranstvo" # то, что отдаёт nginx
LIB_DIR="/var/www/prostranstvo-lib"
STATE_DIR="/var/lib/prostranstvo"
CONF_DIR="/etc/prostranstvo"
CONF_FILE="$CONF_DIR/prostranstvo.conf"
LIB_SH="/usr/local/lib/prostranstvo/common.sh"
SYNC_LOG="/var/log/prostranstvo-sync.log"
CERT_LOG="/var/log/prostranstvo-cert.log"
SETUP_LOG="/var/log/prostranstvo-setup.log"
DETAIL_LOG="/var/log/prostranstvo-setup-details.log"
THREE_VERSION="0.128.0"
# Эталонные SHA-256 файлов three.js r128 (тег r128 в github.com/mrdoob/three.js)
THREE_MIN_SHA256="9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2"
ORBIT_SHA256="02bb4ade710f3e607329e37a21f098bc3ac70eb6e33daf8a65e79f4db785e7b2"
TOTAL_STEPS=10

STEP=0
CURRENT_STEP="подготовка"
WARNINGS=()
FORCE=no
ARG_DOMAIN=""
ARG_EMAIL=""
DOMAIN=""
EMAIL=""
TEE_PID=""
OS_VERSION=""
SSH_PORTS=()
LIBS_OK=no
SITE_OK=no
HTTPS_OK=no

# --- Вывод ---------------------------------------------------------------------
step() { STEP=$((STEP + 1)); CURRENT_STEP="$*"; printf '\n[%d/%d] %s\n' "$STEP" "$TOTAL_STEPS" "$*"; }
ok()   { printf '   + %s\n' "$*"; }
info() { printf '     %s\n' "$*"; }
warn() { printf '   ! ВНИМАНИЕ: %s\n' "$*"; WARNINGS+=("$*"); }
die() {
  trap - ERR
  printf '\nОШИБКА: %s\n' "$*"
  printf 'Исправьте причину и запустите ту же команду ещё раз — повторный запуск безопасен.\n'
  if [[ -f $DETAIL_LOG ]]; then printf 'Подробный журнал: %s\n' "$DETAIL_LOG"; fi
  exit 1
}

# Выполнить команду «тихо»: её вывод уходит в подробный журнал, на экран — только при ошибке.
run() {
  local rc=0
  printf '\n### %s  $ %s\n' "$(date '+%F %T')" "$*" >>"$DETAIL_LOG"
  "$@" >>"$DETAIL_LOG" 2>&1 || rc=$?
  if ((rc != 0)); then
    printf '   Команда не выполнилась (код %s): %s\n' "$rc" "$*"
    tail -n 12 "$DETAIL_LOG" | sed 's/^/   | /'
  fi
  return "$rc"
}

on_err() {
  local rc=$1 line=$2
  trap - ERR
  printf '\nОШИБКА на шаге «%s» (строка %s, код %s).\n' "$CURRENT_STEP" "$line" "$rc"
  printf 'Исправьте причину (часто достаточно подождать минуту) и запустите ту же команду ещё раз — повторный запуск безопасен.\n'
  printf 'Подробный журнал: %s\n' "$DETAIL_LOG"
  exit "$rc"
}

on_exit() {
  local rc=$?
  if [[ -n $TEE_PID ]]; then
    exec 1>&- 2>&-
    wait "$TEE_PID" 2>/dev/null || true
  fi
  exit "$rc"
}

usage() {
  cat <<'EOF'
Установка сервера «Пространство».
  curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-prostranstvo.sh | bash -s -- ДОМЕН EMAIL

  ДОМЕН  — например prostranstvo-dekor.ru (без www и https://). «-» — пока без домена (сайт по IP).
  EMAIL  — почта для Let's Encrypt (необязательно).
  --force — запустить, даже если сервер не выглядит новым (осторожно!).
Повторный запуск без параметров берёт домен и email из /etc/prostranstvo/prostranstvo.conf.
EOF
}

# --- Разбор параметров ----------------------------------------------------------
parse_args() {
  local a pos=()
  for a in "$@"; do
    case $a in
      -h | --help) usage; exit 0 ;;
      --force) FORCE=yes ;;
      --*) die "неизвестный параметр: $a (см. --help)" ;;
      *) pos+=("$a") ;;
    esac
  done
  ((${#pos[@]} <= 2)) || die "лишние параметры: ${pos[*]:2}. Нужно: ДОМЕН EMAIL"
  ARG_DOMAIN=${pos[0]:-}
  ARG_EMAIL=${pos[1]:-}
}

normalize_domain() {
  local d=${1,,}
  d=${d#http://}; d=${d#https://}; d=${d%%/*}; d=${d%%:*}; d=${d%.}; d=${d#www.}
  if [[ $d =~ [^a-z0-9.-] ]]; then
    # кириллический домен (.рф) → punycode
    d=$(python3 -c 'import sys; print(sys.argv[1].encode("idna").decode("ascii"))' "$d" 2>/dev/null) || return 1
  fi
  [[ $d =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,63}|xn--[a-z0-9-]{1,59})$ ]] || return 1
  printf '%s\n' "$d"
}

resolve_settings() {
  local saved_domain="" saved_email=""
  if [[ -r $CONF_FILE ]]; then
    # shellcheck source=/dev/null
    saved_domain=$(. "$CONF_FILE" && printf '%s' "${DOMAIN:-}") || saved_domain=""
    # shellcheck source=/dev/null
    saved_email=$(. "$CONF_FILE" && printf '%s' "${EMAIL:-}") || saved_email=""
  fi
  if [[ $ARG_DOMAIN == "-" ]]; then
    DOMAIN=""
  elif [[ -n $ARG_DOMAIN ]]; then
    DOMAIN=$(normalize_domain "$ARG_DOMAIN") || die "непонятный домен «$ARG_DOMAIN». Пример: prostranstvo-dekor.ru"
  else
    DOMAIN=$saved_domain
  fi
  if [[ -n $ARG_EMAIL ]]; then
    [[ $ARG_EMAIL =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || die "непонятный email «$ARG_EMAIL»"
    EMAIL=$ARG_EMAIL
  else
    EMAIL=$saved_email
  fi
}

# --- Проверки ------------------------------------------------------------------
check_root_and_os() {
  [[ $(id -u) -eq 0 ]] || { echo "ОШИБКА: запустите от root (пользователь root на сервере)." >&2; exit 1; }
  [[ -r /etc/os-release ]] || { echo "ОШИБКА: не найден /etc/os-release — это не Ubuntu." >&2; exit 1; }
  local id ver
  id=$(. /etc/os-release && printf '%s' "${ID:-}")
  ver=$(. /etc/os-release && printf '%s' "${VERSION_ID:-}")
  [[ $id == ubuntu ]] || { echo "ОШИБКА: нужна Ubuntu, а здесь «$id»." >&2; exit 1; }
  OS_VERSION=$ver
}

# Защита от запуска «не на том» сервере (например, на старом сервере в Казахстане с VPN):
# там firewall закрыл бы порты работающих служб.
check_server_is_new() {
  [[ $FORCE == yes ]] && return 0
  [[ -f $CONF_FILE ]] && return 0   # повторный запуск на уже нашем сервере
  local found=() addr port ssh_port
  ssh_port=${SSH_CONNECTION:-}; ssh_port=${ssh_port##* }
  if command -v docker >/dev/null 2>&1; then found+=("установлен Docker"); fi
  if [[ -d /opt/amnezia ]]; then found+=("есть папка Amnezia VPN"); fi
  while read -r addr; do
    [[ -n $addr ]] || continue
    port=${addr##*:}; addr=${addr%:*}
    case $addr in 127.* | '[::1]' | *%lo) continue ;; esac
    case $port in 22 | 80 | 443 | "$ssh_port") continue ;; esac
    found+=("занят порт $port")
  done < <(ss -Htln 2>/dev/null | awk '{print $4}' | sort -u)
  if ((${#found[@]})); then
    printf '\nПохоже, это НЕ новый сервер: %s.\n' "$(IFS=,; printf '%s' "${found[*]}")"
    printf 'Возможно, команда запущена на старом сервере (например, в Казахстане с VPN) —\n'
    printf 'там установка закрыла бы firewall-ом порты работающих служб.\n'
    printf 'НИЧЕГО НЕ ИЗМЕНЕНО. Запускайте команду на новом сервере Selectel.\n'
    printf 'Если вы точно уверены, что это нужный сервер, добавьте в конец команды: --force\n'
    exit 1
  fi
}

# --- Установка файлов ----------------------------------------------------------
# put_file ПУТЬ РЕЖИМ [ВЛАДЕЛЕЦ] — записать stdin в файл (только если содержимое изменилось)
put_file() {
  local dst=$1 mode=$2 owner=${3:-root:root} tmp
  tmp=$(mktemp)
  cat >"$tmp"
  if [[ -f $dst ]] && cmp -s "$tmp" "$dst"; then
    rm -f "$tmp"
  else
    install -D -m "$mode" -o "${owner%%:*}" -g "${owner##*:}" "$tmp" "$dst"
    rm -f "$tmp"
  fi
  chmod "$mode" "$dst"
  chown "$owner" "$dst"
}

# =============================================================================
#  Шаги установки
# =============================================================================

step_packages() {
  step "Установка программ (nginx, git, certbot, защита) — 1–3 минуты"
  export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
  local apt=(apt-get -y -q -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)
  local pkgs=(nginx git rsync curl ca-certificates openssl ufw fail2ban python3-systemd nftables
    unattended-upgrades certbot python3-certbot-nginx bind9-dnsutils cron logrotate iproute2 tzdata python3)
  local n

  # если прошлая установка оборвалась посреди dpkg — доделать
  if [[ -n $(dpkg --audit 2>/dev/null) ]]; then
    for n in 1 2 3 4 5 6 7 8 9 10; do
      if run dpkg --configure -a; then break; fi
      info "dpkg занят (идут автообновления?) — жду 20 секунд…"; sleep 20
    done
  fi
  for n in 1 2 3 4 5; do
    if run "${apt[@]}" update; then break; fi
    ((n < 5)) || die "не удалось обновить список пакетов (apt-get update). Проверьте интернет на сервере."
    info "повторяю через 20 секунд…"; sleep 20
  done
  for n in 1 2 3; do
    if run "${apt[@]}" install --no-install-recommends "${pkgs[@]}"; then break; fi
    ((n < 3)) || die "не удалось установить программы (apt-get install)."
    info "повторяю через 30 секунд…"; sleep 30
  done
  ok "установлено: nginx $(nginx -v 2>&1 | sed -n 's#.*nginx/##p'), git, certbot, ufw, fail2ban"
}

step_time_updates() {
  step "Часовой пояс (Москва) и автоматические обновления безопасности"
  if ! timedatectl set-timezone Europe/Moscow >>"$DETAIL_LOG" 2>&1; then
    ln -sf /usr/share/zoneinfo/Europe/Moscow /etc/localtime
    printf 'Europe/Moscow\n' >/etc/timezone
  fi
  ok "время сервера: $(date '+%d.%m.%Y %H:%M') (Москва)"

  put_file /etc/apt/apt.conf.d/20auto-upgrades 644 <<'EOF'
// Создано setup-prostranstvo.sh: ежедневно обновлять список пакетов и ставить обновления безопасности.
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
  put_file /etc/apt/apt.conf.d/52prostranstvo-unattended 644 <<'EOF'
// Создано setup-prostranstvo.sh. Если обновлению (например, ядра) нужна перезагрузка —
// сервер перезагрузится сам ночью в 04:30 по Москве (сайт недоступен ~1 минуту).
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
  if run systemctl enable --now unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer; then
    ok "автообновления безопасности включены (перезагрузка при необходимости — в 04:30)"
  else
    warn "не удалось включить автообновления (unattended-upgrades) — см. $DETAIL_LOG"
  fi
}

detect_ssh_ports() {
  local p ports=() cur=${SSH_CONNECTION:-}
  cur=${cur##* }
  [[ $cur =~ ^[0-9]+$ ]] && ports+=("$cur")
  while read -r p; do
    [[ $p =~ ^[0-9]+$ ]] && ports+=("$p")
  done < <(sshd -T 2>/dev/null | awk '$1 == "port" {print $2}')
  ports+=(22)
  mapfile -t SSH_PORTS < <(printf '%s\n' "${ports[@]}" | sort -un)
}

step_firewall() {
  step "Firewall (ufw): открыты только SSH, 80 (http) и 443 (https)"
  detect_ssh_ports
  local p
  for p in "${SSH_PORTS[@]}"; do run ufw allow "$p/tcp" comment 'SSH'; done
  run ufw allow 80/tcp comment 'HTTP'
  run ufw allow 443/tcp comment 'HTTPS'
  run ufw default deny incoming
  run ufw default allow outgoing
  run ufw --force enable
  ok "ufw включён, открыты порты: ${SSH_PORTS[*]} (SSH), 80, 443"
}

step_fail2ban() {
  step "fail2ban: блокировка подбора пароля к SSH"
  local ports
  ports=$(IFS=,; printf '%s' "${SSH_PORTS[*]}")
  put_file /etc/fail2ban/jail.d/prostranstvo-sshd.local 644 <<EOF
# Создано setup-prostranstvo.sh: защита SSH от подбора пароля.
# 6 неудачных входов за 10 минут — адрес блокируется на 1 час.
[sshd]
enabled  = true
backend  = systemd
port     = $ports
maxretry = 6
findtime = 10m
bantime  = 1h
EOF
  if run systemctl enable fail2ban && run systemctl restart fail2ban; then
    sleep 3
    if fail2ban-client status sshd >>"$DETAIL_LOG" 2>&1; then
      ok "fail2ban следит за SSH (6 ошибок за 10 мин → блок на 1 час)"
    else
      warn "fail2ban запущен, но защита SSH не отвечает — см. journalctl -u fail2ban"
    fi
  else
    warn "fail2ban не запустился — см. journalctl -u fail2ban (сайт это не затрагивает)"
  fi
}

step_user_dirs() {
  step "Пользователь сайта, папки и служебные команды"
  if ! id -u "$SITE_USER" >/dev/null 2>&1; then
    run useradd --system --user-group --home-dir "$STATE_DIR" --no-create-home --shell /usr/sbin/nologin "$SITE_USER"
  fi
  install -d -o "$SITE_USER" -g "$SITE_USER" -m 755 "$SRC_DIR" "$WWW_DIR" "$STATE_DIR"
  install -d -o root -g root -m 755 "$LIB_DIR" "$CONF_DIR" "$(dirname "$LIB_SH")"
  touch "$SYNC_LOG" "$CERT_LOG"
  chown "$SITE_USER:$SITE_USER" "$SYNC_LOG"; chmod 644 "$SYNC_LOG"
  chown root:adm "$CERT_LOG"; chmod 640 "$CERT_LOG"

  put_file "$CONF_FILE" 644 <<EOF
# Настройки сервера «Пространство» (создано setup-prostranstvo.sh).
# Чтобы сменить домен — запустите установку заново с новым доменом.
DOMAIN=$(printf '%q' "$DOMAIN")
EMAIL=$(printf '%q' "$EMAIL")
REPO_URL=$(printf '%q' "$REPO_URL")
REPO_BRANCH=$(printf '%q' "$REPO_BRANCH")
SITE_SUBDIR=$(printf '%q' "$SITE_SUBDIR")
OLD_PATH=$(printf '%q' "$OLD_PATH")
LIB_URL_PATH=$(printf '%q' "$LIB_URL_PATH")
SITE_USER=$(printf '%q' "$SITE_USER")
SRC_DIR=$(printf '%q' "$SRC_DIR")
WWW_DIR=$(printf '%q' "$WWW_DIR")
LIB_DIR=$(printf '%q' "$LIB_DIR")
STATE_DIR=$(printf '%q' "$STATE_DIR")
SYNC_LOG=$(printf '%q' "$SYNC_LOG")
CERT_LOG=$(printf '%q' "$CERT_LOG")
EOF
  write_helpers
  ok "пользователь $SITE_USER, сайт в $WWW_DIR, настройки в $CONF_FILE"
  ok "команды: prostranstvo-status, prostranstvo-cert, prostranstvo-sync"
}

# --- three.js r128 из npm -------------------------------------------------------
fetch_three_npm() { # fetch_three_npm РЕЕСТР ПАПКА
  local reg=$1 dir=$2 integrity actual
  curl -fsSL --retry 2 --connect-timeout 10 --max-time 60 "$reg/three/$THREE_VERSION" -o "$dir/meta.json" || return 1
  integrity=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["dist"]["integrity"])' "$dir/meta.json" 2>/dev/null) || return 1
  [[ $integrity == sha512-* ]] || return 1
  curl -fsSL --retry 2 --connect-timeout 10 --max-time 300 "$reg/three/-/three-$THREE_VERSION.tgz" -o "$dir/three.tgz" || return 1
  actual="sha512-$(openssl dgst -sha512 -binary "$dir/three.tgz" | base64 -w0)"
  if [[ $actual != "$integrity" ]]; then
    printf 'three.tgz с %s: контрольная сумма не совпала\n' "$reg" >>"$DETAIL_LOG"
    return 1
  fi
  tar -xzf "$dir/three.tgz" -C "$dir" package/build/three.min.js package/examples/js/controls/OrbitControls.js || return 1
  mv "$dir/package/build/three.min.js" "$dir/three.min.js" &&
    mv "$dir/package/examples/js/controls/OrbitControls.js" "$dir/OrbitControls.js"
}

fetch_three_github() { # запасной путь: те же файлы с тега r128, проверка по эталонной SHA-256
  local dir=$1 base="https://raw.githubusercontent.com/mrdoob/three.js/r128"
  curl -fsSL --retry 2 --max-time 120 "$base/build/three.min.js" -o "$dir/three.min.js" || return 1
  curl -fsSL --retry 2 --max-time 60 "$base/examples/js/controls/OrbitControls.js" -o "$dir/OrbitControls.js" || return 1
  [[ $(sha256sum <"$dir/three.min.js" | cut -d' ' -f1) == "$THREE_MIN_SHA256" ]] || return 1
  [[ $(sha256sum <"$dir/OrbitControls.js" | cut -d' ' -f1) == "$ORBIT_SHA256" ]] || return 1
}

step_three() {
  step "Библиотеки 3D: three.js r128 → $LIB_URL_PATH/"
  if [[ -s $LIB_DIR/three.min.js && -s $LIB_DIR/OrbitControls.js && $(cat "$LIB_DIR/VERSION" 2>/dev/null || true) == "$THREE_VERSION" ]]; then
    LIBS_OK=yes
    ok "уже установлены (three@$THREE_VERSION)"
    return 0
  fi
  local tmp src="" reg
  tmp=$(mktemp -d)
  for reg in https://registry.npmjs.org https://registry.npmmirror.com; do
    rm -rf "${tmp:?}"/*
    if fetch_three_npm "$reg" "$tmp" >>"$DETAIL_LOG" 2>&1; then src="npm ($reg)"; break; fi
  done
  if [[ -z $src ]]; then
    rm -rf "${tmp:?}"/*
    if fetch_three_github "$tmp" >>"$DETAIL_LOG" 2>&1; then src="GitHub (тег r128)"; fi
  fi
  if [[ -n $src ]]; then
    install -m 644 "$tmp/three.min.js" "$LIB_DIR/three.min.js"
    install -m 644 "$tmp/OrbitControls.js" "$LIB_DIR/OrbitControls.js"
    printf '%s\n' "$THREE_VERSION" >"$LIB_DIR/VERSION"
    LIBS_OK=yes
    ok "three.min.js и OrbitControls.js (three@$THREE_VERSION) скачаны из $src"
    if [[ $(sha256sum <"$LIB_DIR/three.min.js" | cut -d' ' -f1) == "$THREE_MIN_SHA256" ]]; then
      info "контрольная сумма совпадает с эталоном r128"
    fi
  else
    warn "не удалось скачать three.js — 3D-просмотр на сайте не заработает. Запустите установку ещё раз позже."
  fi
  rm -rf "$tmp"
}

step_site_sync() {
  step "Сайт из GitHub (ветка $REPO_BRANCH, папка $SITE_SUBDIR) + автообновление раз в минуту"
  local rc=0
  runuser -u "$SITE_USER" -- /usr/local/sbin/prostranstvo-sync --verbose 2>&1 | sed 's/^/     /' || rc=$?
  if ((rc == 0)) && [[ -s $WWW_DIR/index.html ]]; then
    SITE_OK=yes
    ok "сайт загружен в $WWW_DIR"
  else
    warn "сайт пока не загрузился из GitHub. Сервер пробует каждую минуту сам; ошибки — в $SYNC_LOG"
  fi
  put_file /etc/cron.d/prostranstvo 644 <<'EOF'
# «Пространство» (создано setup-prostranstvo.sh, не править руками):
#  - каждую минуту: обновить сайт из GitHub (ошибки: /var/log/prostranstvo-sync.log и journalctl -t prostranstvo-sync);
#  - каждые 15 минут: если HTTPS-сертификата ещё нет, а DNS уже указывает на сервер — получить его.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
* * * * *     prostranstvo  /usr/local/sbin/prostranstvo-sync 2>&1 | logger -t prostranstvo-sync
*/15 * * * *  root          /usr/local/sbin/prostranstvo-cert --auto 2>&1 | logger -t prostranstvo-cert
EOF
  if run systemctl enable --now cron; then
    ok "автообновление включено: каждую минуту git fetch + копирование в $WWW_DIR"
  else
    warn "служба cron не запустилась — автообновление сайта не будет работать (systemctl status cron)"
  fi
}

step_nginx() {
  step "Веб-сервер nginx"
  if ! /usr/local/sbin/prostranstvo-nginx 2>&1 | sed 's/^/     /'; then
    die "nginx не настроился (текст ошибки выше). Сайт не изменён."
  fi
}

step_cert() {
  step "HTTPS-сертификат Let's Encrypt"
  if [[ -z $DOMAIN ]]; then
    warn "домен не указан — сайт работает только по http://IP/. Когда будет домен: запустите установку с доменом."
    return 0
  fi
  local rc=0
  /usr/local/sbin/prostranstvo-cert 2>&1 | sed 's/^/     /' || rc=$?
  # shellcheck source=/dev/null
  if (. "$LIB_SH" && cert_ok); then
    HTTPS_OK=yes
  elif ((rc == 2)); then
    warn "HTTPS пока нет: домен ещё не указывает на сервер. Сервер сам пробует каждые 15 минут; вручную: prostranstvo-cert"
  else
    warn "HTTPS не включился (код $rc). Повторить: prostranstvo-cert ; журнал: $CERT_LOG"
  fi
}

# --- Самопроверка и итог ----------------------------------------------------------
http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@" 2>/dev/null || true; }

check_line() { # check_line ОПИСАНИЕ ПОЛУЧЕНО ОЖИДАЕТСЯ
  if [[ $2 == "$3" ]]; then printf '   [да]  %s\n' "$1"; else printf '   [НЕТ] %s (ответ %s, ждали %s)\n' "$1" "$2" "$3"; fi
}

step_selftest_and_summary() {
  step "Самопроверка"
  local base=() url ip
  if [[ $HTTPS_OK == yes ]]; then
    base=(-k --resolve "$DOMAIN:443:127.0.0.1"); url="https://$DOMAIN"
  else
    base=(-H "Host: ${DOMAIN:-localhost}"); url="http://127.0.0.1"
  fi
  check_line "главная страница /" "$(http_code "${base[@]}" "$url/")" 200
  check_line "старый адрес $OLD_PATH/ → главная" "$(http_code "${base[@]}" "$url$OLD_PATH/")" 301
  if [[ $SITE_OK == yes && -f $WWW_DIR/img/hero.jpg ]]; then
    check_line "фото по старому адресу ($OLD_PATH/img/…)" "$(http_code "${base[@]}" "$url$OLD_PATH/img/hero.jpg")" 200
  fi
  if [[ $SITE_OK == yes && -f $WWW_DIR/avito.xml ]]; then
    check_line "фид Авито /avito.xml" "$(http_code "${base[@]}" "$url/avito.xml")" 200
  fi
  check_line "3D-библиотека $LIB_URL_PATH/three.min.js" "$(http_code "${base[@]}" "$url$LIB_URL_PATH/three.min.js")" 200
  check_line "скрытые файлы не отдаются (/.git)" "$(http_code "${base[@]}" "$url/.git/config")" 404
  if [[ $HTTPS_OK == yes ]]; then
    check_line "http → https" "$(http_code -H "Host: $DOMAIN" "http://127.0.0.1/")" 301
  fi

  # shellcheck source=/dev/null
  ip=$(. "$LIB_SH" && server_ip) || ip=""
  local site_url
  if [[ $HTTPS_OK == yes ]]; then site_url="https://$DOMAIN"
  elif [[ -n $DOMAIN ]]; then site_url="http://$DOMAIN"
  else site_url="http://${ip:-IP-сервера}"; fi

  local yn_sync yn_https yn_ufw yn_f2b yn_upd
  yn_sync=$([[ $SITE_OK == yes ]] && echo "да " || echo "НЕТ")
  yn_https=$([[ $HTTPS_OK == yes ]] && echo "да " || echo "НЕТ")
  local ufw_state
  ufw_state=$(ufw status 2>/dev/null) || ufw_state=""
  yn_ufw=$([[ $ufw_state == "Status: active"* ]] && echo "да " || echo "НЕТ")
  yn_f2b=$(systemctl is-active --quiet fail2ban && echo "да " || echo "НЕТ")
  yn_upd=$(systemctl is-enabled --quiet unattended-upgrades 2>/dev/null && echo "да " || echo "НЕТ")

  printf '\n==================================================\n'
  if ((${#WARNINGS[@]})); then
    printf ' ГОТОВО, но есть замечания (см. ниже)\n'
  else
    printf ' ГОТОВО: сервер «Пространство» настроен\n'
  fi
  printf '==================================================\n'
  printf ' Сайт:         %s/\n' "$site_url"
  if [[ -n $ip ]]; then printf ' IP сервера:   %s   (сайт по IP: http://%s/)\n' "$ip" "$ip"; fi
  printf ' Старый адрес: %s%s/ → на главную\n' "$site_url" "$OLD_PATH"
  printf ' Фото Авито:   %s%s/img/…\n' "$site_url" "$OLD_PATH"
  printf ' Фид Авито:    %s/avito.xml\n' "$site_url"
  printf '\n Работает:\n'
  printf '  [%s] сайт обновляется из GitHub каждую минуту%s\n' "$yn_sync" \
    "$( [[ -f $STATE_DIR/deployed-commit ]] && printf ' (версия %s)' "$(cut -c1-7 "$STATE_DIR/deployed-commit")" )"
  printf '  [%s] HTTPS (Let'\''s Encrypt, продление автоматическое)\n' "$yn_https"
  printf '  [%s] 3D-библиотеки three.js r128\n' "$([[ $LIBS_OK == yes ]] && echo "да " || echo "НЕТ")"
  printf '  [%s] firewall ufw (открыты: %s, 80, 443)\n' "$yn_ufw" "${SSH_PORTS[*]}"
  printf '  [%s] fail2ban — защита SSH от подбора пароля\n' "$yn_f2b"
  printf '  [%s] автообновления безопасности (перезагрузка при нужде в 04:30)\n' "$yn_upd"

  if ((${#WARNINGS[@]})); then
    printf '\n Замечания:\n'
    local w
    for w in "${WARNINGS[@]}"; do printf '  - %s\n' "$w"; done
  fi

  printf '\n Что сделать дальше:\n'
  local n=1
  if [[ -n $DOMAIN && $HTTPS_OK != yes ]]; then
    printf '  %d) reg.ru → домен %s → «DNS-серверы и управление зоной»:\n' "$n" "$DOMAIN"
    printf '     A-запись «@» → %s и A-запись «www» → %s (AAAA-записи удалить).\n' "${ip:-IP сервера}" "${ip:-IP сервера}"
    printf '     Сертификат сервер получит сам (проверка каждые 15 мин) или сразу командой:\n'
    printf '       prostranstvo-cert\n'
    n=$((n + 1))
  elif [[ -z $DOMAIN ]]; then
    printf '  %d) Когда купите домен — запустите эту же команду, указав домен и email.\n' "$n"
    n=$((n + 1))
  fi
  local feed_base=$site_url
  if [[ -n $DOMAIN ]]; then feed_base="https://$DOMAIN"; fi
  printf '  %d) Фид Авито: в config.json генератора поставить\n' "$n"
  printf '     "photo_base": "%s%s/img/", пересобрать avito.xml и залить в ветку mebel' "$feed_base" "$OLD_PATH"
  if [[ -n $DOMAIN && $HTTPS_OK != yes ]]; then printf ' (когда заработает HTTPS)'; fi
  printf '.\n'
  n=$((n + 1))
  print_ssh_advice "$n"
  printf '\n Проверить сервер в любой момент:  prostranstvo-status\n'
  printf ' Журнал установки: %s\n' "$SETUP_LOG"
  printf '==================================================\n'
}

print_ssh_advice() {
  local n=$1 pass keys=no
  pass=$(sshd -T 2>/dev/null | awk '$1 == "passwordauthentication" {print $2}') || pass=""
  if [[ -s /root/.ssh/authorized_keys ]]; then keys=yes; fi
  printf '  %d) Безопасность SSH (сделать вручную — скрипт специально это НЕ меняет,\n' "$n"
  printf '     чтобы вы не потеряли доступ):\n'
  if [[ $keys == no ]]; then
    printf '     - в «Командах» iPhone в действии SSH выбрать «Ключ SSH», нажать\n'
    printf '       «Поделиться открытым ключом» и добавить его в /root/.ssh/authorized_keys;\n'
  fi
  if [[ $pass != no ]]; then
    printf '     - когда вход по ключу проверен — отключить вход по паролю\n'
    printf '       (PasswordAuthentication no в /etc/ssh/sshd_config), держа открытой\n'
    printf '       вторую сессию; запасной вход — консоль в панели Selectel;\n'
  fi
  printf '     - порт SSH менять не обязательно: fail2ban уже блокирует подбор пароля.\n'
}

# =============================================================================
#  ЭТАП 2 (ПОКА НЕ ВКЛЮЧЁН): база данных и CRM — будет отдельным шагом.
#  Заготовка плана, чтобы потом добавить сюда функцию step_database_crm():
#   - PostgreSQL из репозитория Ubuntu (apt-get install postgresql), слушает
#     только 127.0.0.1; порт 5432 в ufw НЕ открывать;
#   - отдельный системный пользователь crm; приложение CRM — systemd-служба на
#     127.0.0.1:8081;
#   - nginx: в snippets/prostranstvo-site.conf добавить
#       location /crm/ { proxy_pass http://127.0.0.1:8081/; }  + вход по паролю;
#   - пароли и ключи — только в /etc/prostranstvo/secrets.env (chmod 600) на
#     сервере, НИКОГДА не в GitHub (репозиторий открытый);
#   - ежедневная копия базы: pg_dump в /var/backups/prostranstvo + копия в
#     объектное хранилище Selectel.
# step_database_crm() { :; }
# =============================================================================

# =============================================================================
#  Служебные команды на сервере (пишутся в /usr/local/sbin и /usr/local/lib)
# =============================================================================
write_helpers() {
  # ---------------------------------------------------------------- common.sh
  put_file "$LIB_SH" 644 <<'PRS_COMMON'
# shellcheck shell=bash
# Общие функции служебных команд «Пространства». Создано setup-prostranstvo.sh —
# руками не править (повторная установка перезапишет файл).
PROSTRANSTVO_CONF=/etc/prostranstvo/prostranstvo.conf
if [[ ! -r $PROSTRANSTVO_CONF ]]; then
  echo "Нет файла настроек $PROSTRANSTVO_CONF — запустите установку заново." >&2
  exit 1
fi
# shellcheck source=/dev/null
. "$PROSTRANSTVO_CONF"
export LC_ALL=C.UTF-8

ts() { date '+%Y-%m-%d %H:%M:%S'; }

# log_to ФАЙЛ УРОВЕНЬ СООБЩЕНИЕ
log_to() {
  local file=$1 level=$2
  shift 2
  printf '%s [%s] %s\n' "$(ts)" "$level" "$*" >>"$file" 2>/dev/null || true
}

# is_public_ipv4 IP — true для «белого» адреса (не 127.*, 10.*, 192.168.* и т.п.)
is_public_ipv4() {
  [[ $1 =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || return 1
  case $1 in
    0.* | 10.* | 127.* | 169.254.* | 192.168.* | 172.1[6-9].* | 172.2[0-9].* | 172.3[01].* | 100.6[4-9].* | 100.[7-9][0-9].* | 100.1[01][0-9].* | 100.12[0-7].*) return 1 ;;
  esac
  return 0
}

# Внешний IPv4 сервера (как его видит интернет)
server_ip() {
  local url ip
  for url in https://api.ipify.org https://ipv4-internet.yandex.net/api/v0/ip https://ipv4.icanhazip.com https://ifconfig.me/ip; do
    ip=$(curl -4 -fsS --max-time 5 "$url" 2>/dev/null | tr -d '"[:space:]') || ip=""
    if is_public_ipv4 "$ip"; then
      printf '%s\n' "$ip"
      return 0
    fi
  done
  # интернет-сервисы не ответили — берём адрес с сетевой карты (сначала «белый»)
  for ip in $(ip -4 -o addr show scope global 2>/dev/null | awk '{sub(/\/.*/, "", $4); print $4}'); do
    if is_public_ipv4 "$ip"; then
      printf '%s\n' "$ip"
      return 0
    fi
  done
  ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}') || ip=""
  if [[ -n $ip ]]; then printf '%s\n' "$ip"; fi
  return 0
}

server_ip6_list() {
  ip -6 addr show scope global 2>/dev/null | awk '$1 == "inet6" {sub(/\/.*/, "", $2); print $2}'
  return 0
}

# dns_lookup A|AAAA ИМЯ — адреса из DNS: сначала у DNS-серверов домена (reg.ru),
# потом у публичных; так видно изменения раньше, чем через кеши.
dns_lookup() {
  local type=$1 name=$2 ns out servers=""
  if command -v dig >/dev/null 2>&1; then
    if [[ -n ${DOMAIN:-} ]]; then
      servers=$(dig +short +time=3 +tries=1 NS "$DOMAIN" @77.88.8.8 2>/dev/null | awk 'NR <= 2 {sub(/\.$/, ""); print}') || servers=""
    fi
    for ns in $servers 77.88.8.8 1.1.1.1 8.8.8.8; do
      out=$(dig +time=3 +tries=1 +noall +comments +answer "$type" "$name" "@$ns" 2>/dev/null) || continue
      [[ $out =~ status:\ (NOERROR|NXDOMAIN) ]] || continue
      awk -v t="$type" '$4 == t {print $5}' <<<"$out"
      return 0
    done
  fi
  if [[ $type == A ]]; then
    getent ahostsv4 "$name" 2>/dev/null | awk '{print $1}' | sort -u
  else
    getent ahostsv6 "$name" 2>/dev/null | awk '$1 ~ /:/ && $1 !~ /^::ffff:/ {print $1}' | sort -u
  fi
  return 0
}

# dns_points_here ИМЯ IP — true, если A-записи имени = ровно этот IP
dns_points_here() {
  local recs
  recs=$(dns_lookup A "$1" | sort -u | paste -sd' ')
  [[ -n $2 && $recs == "$2" ]]
}

cert_path() { printf '/etc/letsencrypt/live/%s/fullchain.pem' "${DOMAIN:-none}"; }

# действующий сертификат для DOMAIN есть
cert_ok() {
  [[ -n ${DOMAIN:-} ]] || return 1
  [[ -s $(cert_path) && -s /etc/letsencrypt/live/$DOMAIN/privkey.pem ]] || return 1
  openssl x509 -checkend 0 -noout -in "$(cert_path)" >/dev/null 2>&1
}

# cert_has ИМЯ — сертификат включает это имя
cert_has() {
  local san
  san=$(openssl x509 -noout -ext subjectAltName -in "$(cert_path)" 2>/dev/null) || return 1
  grep -qwF "DNS:$1" <<<"$san"
}

cert_until() {
  local d
  d=$(openssl x509 -enddate -noout -in "$(cert_path)" 2>/dev/null) || return 0
  d=${d#notAfter=}
  date -d "$d" '+%d.%m.%Y' 2>/dev/null || printf '%s' "$d"
}
PRS_COMMON

  # ------------------------------------------------------- prostranstvo-sync
  put_file /usr/local/sbin/prostranstvo-sync 755 <<'PRS_SYNC'
#!/bin/bash
# prostranstvo-sync — обновить сайт «Пространство» из GitHub.
# Запускается cron'ом КАЖДУЮ МИНУТУ от пользователя prostranstvo (/etc/cron.d/prostranstvo).
# Никаких «тихих» условий: любая ошибка пишется в /var/log/prostranstvo-sync.log
# и в системный журнал (journalctl -t prostranstvo-sync).
# Вручную (от root тоже можно):  prostranstvo-sync --verbose
set -uo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh

if [[ $(id -u) -eq 0 ]]; then
  exec runuser -u "$SITE_USER" -- "$0" "$@"
fi

VERBOSE=no
if [[ ${1:-} == -v || ${1:-} == --verbose ]]; then VERBOSE=yes; fi
export HOME="$STATE_DIR" GIT_TERMINAL_PROMPT=0

say() { if [[ $VERBOSE == yes ]]; then printf '%s\n' "$*"; fi; }
info() { log_to "$SYNC_LOG" инфо "$*"; say "$*"; }
fail() {
  trap - ERR
  log_to "$SYNC_LOG" ОШИБКА "$*"
  logger -t prostranstvo-sync -p user.err -- "ОШИБКА: $*" 2>/dev/null || true
  if [[ $VERBOSE == yes || -t 2 ]]; then printf 'ОШИБКА: %s\n' "$*" >&2; fi
  exit 1
}
trap 'fail "неожиданная ошибка (строка $LINENO): $BASH_COMMAND"' ERR

exec 8>>"$STATE_DIR/sync.lock"
if ! flock -n 8; then
  info "предыдущее обновление ещё не закончилось — пропускаю этот запуск"
  exit 0
fi

if [[ ! -d $SRC_DIR/.git ]]; then
  out=$(git -c init.defaultBranch=site init -q "$SRC_DIR" 2>&1) || fail "не удалось создать репозиторий в $SRC_DIR: $out"
fi
if git -C "$SRC_DIR" remote get-url origin >/dev/null 2>&1; then
  out=$(git -C "$SRC_DIR" remote set-url origin "$REPO_URL" 2>&1) || fail "git remote set-url: $out"
else
  out=$(git -C "$SRC_DIR" remote add origin "$REPO_URL" 2>&1) || fail "git remote add: $out"
fi

out=$(timeout 120 git -C "$SRC_DIR" fetch --quiet --depth 1 --no-tags origin \
  "+refs/heads/$REPO_BRANCH:refs/remotes/origin/$REPO_BRANCH" 2>&1) ||
  fail "не удалось скачать обновления с GitHub (ветка $REPO_BRANCH): ${out:-нет ответа 120 секунд}"
out=$(git -C "$SRC_DIR" reset --quiet --hard "refs/remotes/origin/$REPO_BRANCH" 2>&1) || fail "git reset: $out"
out=$(git -C "$SRC_DIR" clean -ffdxq 2>&1) || fail "git clean: $out"
commit=$(git -C "$SRC_DIR" rev-parse HEAD 2>&1) || fail "git rev-parse: $commit"

src="$SRC_DIR/$SITE_SUBDIR"
[[ -s $src/index.html ]] ||
  fail "в ветке $REPO_BRANCH нет файла $SITE_SUBDIR/index.html — сайт НЕ обновлён, оставлена прежняя версия"

out=$(rsync -a --delete --delay-updates --exclude='.git*' --exclude='.keep' \
  --chmod=D755,F644 "$src/" "$WWW_DIR/" 2>&1) || fail "не удалось скопировать сайт в $WWW_DIR (rsync): $out"

prev=$(cat "$STATE_DIR/deployed-commit" 2>/dev/null) || prev=""
if [[ $commit != "$prev" ]]; then
  when=$(git -C "$SRC_DIR" log -1 --format=%cd --date=format-local:'%d.%m.%Y %H:%M' 2>/dev/null) || when="?"
  subject=$(git -C "$SRC_DIR" log -1 --format=%s 2>/dev/null) || subject=""
  printf '%s\n' "$commit" >"$STATE_DIR/deployed-commit" || fail "не удалось записать $STATE_DIR/deployed-commit"
  printf '%s\n' "$when" >"$STATE_DIR/deployed-date" || true
  printf '%s\n' "$subject" >"$STATE_DIR/deployed-subject" || true
  info "сайт обновлён до версии ${commit:0:7} от $when: $subject"
else
  say "изменений нет (версия ${commit:0:7})"
fi
date +%s >"$STATE_DIR/last-ok" || fail "не удалось записать $STATE_DIR/last-ok"
exit 0
PRS_SYNC

  # ------------------------------------------------------ prostranstvo-nginx
  put_file /usr/local/sbin/prostranstvo-nginx 755 <<'PRS_NGINX'
#!/bin/bash
# prostranstvo-nginx — собрать конфигурацию nginx для сайта «Пространство» и перезагрузить nginx.
# Если сертификат Let's Encrypt уже есть — включает HTTPS и перенаправление http → https.
# Если nginx не принимает новую конфигурацию — возвращает прежние файлы (сайт не ломается).
set -Eeuo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh
trap 'echo "ОШИБКА в prostranstvo-nginx (строка $LINENO): $BASH_COMMAND" >&2' ERR
if [[ $(id -u) -ne 0 ]]; then echo "Запустите от root." >&2; exit 1; fi

SITE_FILE=/etc/nginx/sites-available/prostranstvo.conf
SITE_LINK=/etc/nginx/sites-enabled/prostranstvo.conf
HTTP_FILE=/etc/nginx/conf.d/prostranstvo-http.conf
SNIP_SITE=/etc/nginx/snippets/prostranstvo-site.conf
SNIP_TLS=/etc/nginx/snippets/prostranstvo-tls.conf
DEFAULT_LINK=/etc/nginx/sites-enabled/default

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

listen6=no
if [[ -e /proc/net/if_inet6 ]]; then listen6=yes; fi
nginx_ver=$(nginx -v 2>&1 | sed -n 's#^.*nginx/\([0-9][0-9.]*\).*$#\1#p') || nginx_ver=""
if dpkg --compare-versions "${nginx_ver:-0}" ge 1.25.1; then
  h2_listen=""; h2_line="    http2 on;"
else
  h2_listen=" http2"; h2_line=""
fi
https=no; www_cert=no
if cert_ok; then
  https=yes
  if cert_has "www.$DOMAIN"; then www_cert=yes; fi
fi
if [[ -n ${DOMAIN:-} ]]; then names="$DOMAIN www.$DOMAIN _"; else names="_"; fi

listen() { # listen ПОРТ [ПАРАМЕТРЫ]
  local port=$1 params=""
  shift
  if (($#)); then params=" $*"; fi
  printf '    listen %s%s;\n' "$port" "$params"
  if [[ $listen6 == yes ]]; then printf '    listen [::]:%s%s;\n' "$port" "$params"; fi
}

# ---------- conf.d: общие настройки уровня http
{
  echo "# Создано prostranstvo-nginx — не править руками (перезапишется)."
  if ! grep -Eqs --exclude=prostranstvo-http.conf '^[[:space:]]*server_tokens[[:space:]]' /etc/nginx/nginx.conf /etc/nginx/conf.d/*.conf; then
    echo "server_tokens off;  # не показывать версию nginx"
  fi
  cat <<'EOF'
# Кеш в браузере: страницы и фид — каждый раз проверять свежесть (сайт обновляется
# каждую минуту), картинки/стили/скрипты — 7 дней.
map $sent_http_content_type $prostranstvo_expires {
    default                          off;
    ~^text/html                      epoch;
    ~^(text|application)/xml         epoch;
    ~^image/                         7d;
    ~^text/css                       7d;
    ~^(application|text)/javascript  7d;
    ~^font/                          30d;
}
EOF
} >"$work/http.conf"

# ---------- настройки HTTPS
cat >"$work/tls.conf" <<'EOF'
# Настройки HTTPS (Mozilla «intermediate»). Создано prostranstvo-nginx.
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:prostranstvo_tls:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;
add_header Strict-Transport-Security "max-age=15552000" always;
EOF

# ---------- сам сайт (общий для http и https)
cat >"$work/site.conf" <<EOF
# Сайт «Пространство». Создано prostranstvo-nginx — не править руками.
root $WWW_DIR;
index index.html;
charset utf-8;
client_max_body_size 1m;

gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 5;
gzip_min_length 1024;
gzip_types text/plain text/css text/xml application/xml application/javascript application/json image/svg+xml;

add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

expires \$prostranstvo_expires;

location / {
    try_files \$uri \$uri/ =404;
}

# Скрытые файлы (.git, .keep, .env …) не отдавать; .well-known нужна для сертификата.
location ~ /\.(?!well-known/) {
    return 404;
}

# Библиотеки 3D (three.js r128): сайт подключает $LIB_URL_PATH/three.min.js и OrbitControls.js
location ^~ $LIB_URL_PATH/ {
    alias $LIB_DIR/;
    expires 30d;
}

# Старый адрес сайта ($OLD_PATH/): страница — переадресация на главную,
# файлы (фото для Авито, avito.xml) отдаются по старым ссылкам как есть.
location = $OLD_PATH {
    return 301 /\$is_args\$args;
}
location = $OLD_PATH/ {
    return 301 /\$is_args\$args;
}
location = $OLD_PATH/index.html {
    return 301 /\$is_args\$args;
}
location ^~ $OLD_PATH/ {
    alias $WWW_DIR/;
    location ~ /\. {
        return 404;
    }
}
EOF

# ---------- server-блоки
{
  echo "# Сайт «Пространство». Создано prostranstvo-nginx $(ts) — не править руками:"
  echo "# файл пересоздаётся при установке и при получении сертификата."
  if [[ $https == yes ]]; then
    echo "server {"
    listen 80 default_server
    echo "    server_name $names;"
    echo "    # всё с http — на https (проверку для продления сертификата certbot добавляет сам)"
    echo "    location / {"
    echo "        return 301 https://$DOMAIN\$request_uri;"
    echo "    }"
    echo "}"
    echo
    echo "server {"
    listen 443 "ssl$h2_listen" default_server
    if [[ -n $h2_line ]]; then echo "$h2_line"; fi
    echo "    server_name $DOMAIN;"
    echo "    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;"
    echo "    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;"
    echo "    include snippets/prostranstvo-tls.conf;"
    echo "    include snippets/prostranstvo-site.conf;"
    echo "}"
    if [[ $www_cert == yes ]]; then
      echo
      echo "server {"
      listen 443 "ssl$h2_listen"
      if [[ -n $h2_line ]]; then echo "$h2_line"; fi
      echo "    server_name www.$DOMAIN;"
      echo "    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;"
      echo "    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;"
      echo "    include snippets/prostranstvo-tls.conf;"
      echo "    return 301 https://$DOMAIN\$request_uri;"
      echo "}"
    fi
  else
    echo "server {"
    listen 80 default_server
    echo "    server_name $names;"
    echo "    include snippets/prostranstvo-site.conf;"
    echo "}"
  fi
} >"$work/server.conf"

# ---------- установка с возможностью отката
pairs=("$HTTP_FILE|$work/http.conf" "$SNIP_TLS|$work/tls.conf" "$SNIP_SITE|$work/site.conf" "$SITE_FILE|$work/server.conf")
mkdir -p "$work/bak"
for p in "${pairs[@]}"; do
  dst=${p%%|*}
  if [[ -e $dst ]]; then cp -a "$dst" "$work/bak/$(basename "$dst")"; fi
done
link_existed=no
if [[ -L $SITE_LINK || -e $SITE_LINK ]]; then link_existed=yes; fi
default_moved=no

for p in "${pairs[@]}"; do
  install -D -m 644 "${p#*|}" "${p%%|*}"
done
ln -sfn "$SITE_FILE" "$SITE_LINK"
if [[ -L $DEFAULT_LINK || -e $DEFAULT_LINK ]]; then
  mv "$DEFAULT_LINK" "$work/bak/default-link"
  default_moved=yes
fi

if ! test_out=$(nginx -t 2>&1); then
  echo "ОШИБКА: nginx не принял новую конфигурацию, возвращаю прежнюю:"
  printf '%s\n' "$test_out" | sed 's/^/   | /'
  for p in "${pairs[@]}"; do
    dst=${p%%|*}
    if [[ -e $work/bak/$(basename "$dst") ]]; then cp -a "$work/bak/$(basename "$dst")" "$dst"; else rm -f "$dst"; fi
  done
  if [[ $link_existed == no ]]; then rm -f "$SITE_LINK"; fi
  if [[ $default_moved == yes ]]; then mv "$work/bak/default-link" "$DEFAULT_LINK"; fi
  exit 1
fi

systemctl enable nginx >/dev/null 2>&1 || true
if systemctl is-active --quiet nginx; then
  systemctl reload nginx
elif ! systemctl restart nginx; then
  echo "ОШИБКА: nginx не запустился. Последние сообщения:"
  journalctl -u nginx -n 8 --no-pager 2>/dev/null | sed 's/^/   | /' || true
  exit 1
fi
if [[ $https == yes ]]; then
  echo "+ nginx работает: https://$DOMAIN/ (http перенаправляется на https)"
else
  echo "+ nginx работает: http://${DOMAIN:-IP-сервера}/ (HTTPS включится, когда будет сертификат)"
fi
PRS_NGINX

  # ------------------------------------------------------- prostranstvo-cert
  put_file /usr/local/sbin/prostranstvo-cert 755 <<'PRS_CERT'
#!/bin/bash
# prostranstvo-cert — получить HTTPS-сертификат Let's Encrypt для домена сайта.
#   prostranstvo-cert         — попробовать сейчас и понятно объяснить результат;
#   prostranstvo-cert --auto  — тихо, для cron (каждые 15 минут): пробует, только когда DNS
#                               уже указывает на этот сервер (и не чаще раза в час после неудачи).
# Продление готового сертификата делает сам certbot (certbot.timer) — эта команда для него не нужна.
set -Eeuo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh
trap 'echo "ОШИБКА в prostranstvo-cert (строка $LINENO): $BASH_COMMAND" >&2' ERR
if [[ $(id -u) -ne 0 ]]; then echo "Запустите от root." >&2; exit 1; fi

AUTO=no
if [[ ${1:-} == --auto ]]; then AUTO=yes; fi
say() { if [[ $AUTO == no ]]; then printf '%s\n' "$*"; fi; }

if [[ -z ${DOMAIN:-} ]]; then
  say "Домен не задан. Запустите установку с доменом: … | bash -s -- ДОМЕН EMAIL"
  if [[ $AUTO == yes ]]; then exit 0; fi
  exit 1
fi

if [[ $AUTO == yes ]]; then
  # уже всё есть — ничего не делать
  if cert_ok && cert_has "www.$DOMAIN"; then exit 0; fi
  last_fail=$(cat "$STATE_DIR/cert-last-fail" 2>/dev/null) || last_fail=0
  [[ $last_fail =~ ^[0-9]+$ ]] || last_fail=0
  if (($(date +%s) - last_fail < 3600)); then exit 0; fi
fi

ip=$(server_ip)
apex_recs=$(dns_lookup A "$DOMAIN" | sort -u | paste -sd' ')
need=("$DOMAIN")
apex_here=no; www_here=no
if [[ -n $ip && $apex_recs == "$ip" ]]; then apex_here=yes; fi
if [[ -n $ip ]] && dns_points_here "www.$DOMAIN" "$ip"; then www_here=yes; need+=("www.$DOMAIN"); fi

if cert_ok; then
  if [[ $www_here == no ]] || cert_has "www.$DOMAIN"; then
    if [[ $AUTO == yes ]]; then exit 0; fi
    say "Сертификат уже есть: https://$DOMAIN/ (действует до $(cert_until), продлевается автоматически)."
    # убедиться, что HTTPS включён в nginx (на экран — только при ошибке)
    if ! nginx_out=$(/usr/local/sbin/prostranstvo-nginx 2>&1); then printf '%s\n' "$nginx_out"; exit 1; fi
    exit 0
  fi
  say "Добавляю в сертификат www.$DOMAIN …"
fi

if [[ $AUTO == yes && $apex_here == no ]]; then exit 0; fi

say "Домен $DOMAIN сейчас указывает на: ${apex_recs:-никуда (записи нет)}"
say "IP этого сервера: ${ip:-не удалось определить}"
if [[ $apex_here == no ]]; then
  say "DNS ещё не указывает на этот сервер — Let's Encrypt, скорее всего, откажет. Всё равно пробую…"
fi
aaaa=$(dns_lookup AAAA "$DOMAIN" | paste -sd' ')
if [[ -n $aaaa ]]; then
  my6=" $(server_ip6_list | paste -sd' ') "
  for a in $aaaa; do
    if [[ $my6 != *" $a "* ]]; then
      say "ВНИМАНИЕ: у домена есть IPv6-запись (AAAA) $a, она ведёт не на этот сервер — удалите её в reg.ru."
      break
    fi
  done
fi

args=(certonly --nginx --non-interactive --agree-tos --cert-name "$DOMAIN")
for n in "${need[@]}"; do args+=(-d "$n"); done
if [[ -n ${EMAIL:-} ]]; then args+=(--email "$EMAIL" --no-eff-email); else args+=(--register-unsafely-without-email); fi
if [[ ${CERTBOT_STAGING:-0} == 1 ]]; then args+=(--test-cert); fi   # только для проверок скрипта

say "Запрашиваю сертификат Let's Encrypt для: ${need[*]} …"
log_to "$CERT_LOG" инфо "certbot ${args[*]}"
rc=0
out=$(certbot "${args[@]}" 2>&1) || rc=$?
printf '%s\n' "$out" >>"$CERT_LOG"

if ((rc == 0)) && cert_ok; then
  rm -f "$STATE_DIR/cert-last-fail"
  log_to "$CERT_LOG" инфо "сертификат получен для ${need[*]}"
  logger -t prostranstvo-cert "сертификат получен для ${need[*]}" 2>/dev/null || true
  if [[ $AUTO == yes ]]; then
    /usr/local/sbin/prostranstvo-nginx >>"$CERT_LOG" 2>&1
  else
    /usr/local/sbin/prostranstvo-nginx
  fi
  say "ГОТОВО: HTTPS включён — https://$DOMAIN/ (сертификат до $(cert_until), продление автоматическое)."
  exit 0
fi

date +%s >"$STATE_DIR/cert-last-fail"
reason=$(grep -E '^[[:space:]]*(Detail|Domain|Type):' <<<"$out" | tail -n 3) || reason=""
if [[ -z $reason ]]; then reason=$(grep -v '^[[:space:]]*$' <<<"$out" | tail -n 4) || reason=""; fi
log_to "$CERT_LOG" ОШИБКА "сертификат не получен: $(tr '\n' ' ' <<<"$reason")"
logger -t prostranstvo-cert -p user.err -- "сертификат не получен: $(tr '\n' ' ' <<<"$reason")" 2>/dev/null || true

say ""
say "Сертификат пока НЕ получен. Сайт работает по http://$DOMAIN/${ip:+ и http://$ip/}."
say "Ответ Let's Encrypt:"
if [[ $AUTO == no ]]; then printf '%s\n' "$reason" | sed 's/^/   | /'; fi
say "Что сделать: в reg.ru → домен $DOMAIN → «DNS-серверы и управление зоной»:"
say "  A-запись «@» → ${ip:-IP сервера}, A-запись «www» → ${ip:-IP сервера}; AAAA-записи удалить."
say "  Изменения DNS расходятся обычно за 15–60 минут (иногда до суток)."
say "Сервер сам пробует каждые 15 минут, как только DNS заработает."
say "Или повторите вручную одной командой:  prostranstvo-cert"
exit 2
PRS_CERT

  # ----------------------------------------------------- prostranstvo-status
  put_file /usr/local/sbin/prostranstvo-status 755 <<'PRS_STATUS'
#!/bin/bash
# prostranstvo-status — коротко: работает ли сайт, обновляется ли он из GitHub, HTTPS, защита.
set -uo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh

now=$(date +%s)
ip=$(server_ip)
echo "=== Сервер «Пространство», $(date '+%d.%m.%Y %H:%M') ==="
if cert_ok; then
  echo "Сайт:   https://$DOMAIN/  (сертификат до $(cert_until), продление авто)"
else
  echo "Сайт:   http://${DOMAIN:-$ip}/  (HTTPS пока нет — команда: prostranstvo-cert)"
fi
echo "IP:     ${ip:-?}"
echo "nginx:  $(systemctl is-active nginx 2>/dev/null || true)"

last_ok=$(cat "$STATE_DIR/last-ok" 2>/dev/null) || last_ok=""
sync_bad=no
if [[ $last_ok =~ ^[0-9]+$ ]]; then
  age=$(((now - last_ok) / 60))
  if ((age <= 3)); then
    echo "Обновление из GitHub: работает (последняя проверка $age мин назад)"
  else
    echo "Обновление из GitHub: НЕ РАБОТАЕТ уже $age мин"; sync_bad=yes
  fi
else
  echo "Обновление из GitHub: ещё ни разу не прошло успешно"; sync_bad=yes
fi
if [[ -s $STATE_DIR/deployed-commit ]]; then
  echo "Версия сайта: $(cut -c1-7 "$STATE_DIR/deployed-commit") от $(cat "$STATE_DIR/deployed-date" 2>/dev/null) — $(cat "$STATE_DIR/deployed-subject" 2>/dev/null)"
fi
if [[ $sync_bad == yes ]]; then
  echo "Последние ошибки (полностью: $SYNC_LOG):"
  { grep 'ОШИБКА' "$SYNC_LOG" 2>/dev/null || true; } | tail -n 3 | sed 's/^/  /'
fi
echo "Firewall ufw:  $(ufw status 2>/dev/null | awk 'NR == 1 {print $2}')"
banned=$(fail2ban-client status sshd 2>/dev/null | awk -F: '/Currently banned/ {gsub(/[[:space:]]/, "", $2); print $2}') || banned=""
echo "fail2ban SSH:  $(systemctl is-active fail2ban 2>/dev/null || true), сейчас заблокировано адресов: ${banned:-?}"
echo "Автообновления: $(systemctl is-enabled unattended-upgrades 2>/dev/null || true)"
if [[ -f /var/run/reboot-required ]]; then echo "Нужна перезагрузка: сделается сама в 04:30 (или сейчас: reboot)"; fi
echo "Диск:   $(df -h / | awk 'NR == 2 {print $4 " свободно из " $2}')"
PRS_STATUS

  # ------------------------------------------- продление сертификата → reload
  put_file /etc/letsencrypt/renewal-hooks/deploy/prostranstvo-reload-nginx 755 <<'EOF'
#!/bin/sh
# Создано setup-prostranstvo.sh: после продления сертификата перечитать его в nginx.
systemctl reload nginx
EOF

  # ------------------------------------------------------------ logrotate
  put_file /etc/logrotate.d/prostranstvo 644 <<'EOF'
# Создано setup-prostranstvo.sh
/var/log/prostranstvo-sync.log {
    su root adm
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0644 prostranstvo prostranstvo
}
/var/log/prostranstvo-cert.log /var/log/prostranstvo-setup.log /var/log/prostranstvo-setup-details.log {
    su root adm
    monthly
    rotate 6
    compress
    missingok
    notifempty
    create 0640 root adm
}
EOF
}

# =============================================================================
main() {
  trap '' HUP          # не прерываться, если связь с телефоном оборвётся
  exec </dev/null      # ничего не спрашивать
  parse_args "$@"
  check_root_and_os

  install -d -m 755 /var/log
  touch "$SETUP_LOG" "$DETAIL_LOG"
  chmod 640 "$SETUP_LOG" "$DETAIL_LOG"
  # Весь вывод — и на экран, и в журнал. tee не падает, если экран (SSH) отвалился.
  exec > >(tee --output-error=warn -a "$SETUP_LOG") 2>&1
  TEE_PID=$!
  trap on_exit EXIT
  trap 'on_err $? $LINENO' ERR

  printf '\n=== Установка сервера «Пространство» — %s ===\n' "$(date '+%d.%m.%Y %H:%M')"
  printf '\n=== %s: запуск установки ===\n' "$(date '+%F %T')" >>"$DETAIL_LOG"
  if [[ $OS_VERSION != 24.04 ]]; then
    warn "скрипт рассчитан на Ubuntu 24.04, здесь $OS_VERSION — продолжаю"
  fi
  exec 9>/run/prostranstvo-setup.lock
  flock -n 9 || die "установка уже идёт в другом окне. Дождитесь её окончания."

  resolve_settings
  check_server_is_new
  if [[ -n $DOMAIN ]]; then
    info "домен: $DOMAIN${EMAIL:+, email: $EMAIL}"
  else
    info "домен не указан — сайт будет доступен по IP (домен можно добавить позже)"
  fi

  step_packages
  step_time_updates
  step_firewall
  step_fail2ban
  step_user_dirs
  step_three
  step_site_sync
  step_nginx
  step_cert
  step_selftest_and_summary
}

main "$@"
