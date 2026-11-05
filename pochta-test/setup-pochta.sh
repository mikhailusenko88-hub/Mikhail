#!/usr/bin/env bash
# =============================================================================
#  setup-pochta.sh — почта на своём домене для сервера магазина «Наш декор»
#  (Ubuntu 24.04). Запускать от root ПОСЛЕ setup-prostranstvo.sh с доменом:
#
#    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-pochta.sh | bash
#
#  По умолчанию создаёт ящики info@, zakaz@, yulia@, mikhail@ (домен — из настроек
#  сервера /etc/prostranstvo/prostranstvo.conf). Свои имена:
#    ... | bash -s -- info zakaz yulia mikhail
#
#  Что ставит: Postfix (приём и отправка писем), Dovecot (IMAP — почта на телефонах
#  и компьютерах), Rspamd + Redis (подпись DKIM, фильтр спама), Roundcube (веб-почта
#  https://mail.ДОМЕН). Сертификат для mail.ДОМЕН сервер получает сам, как только
#  домен заработает (проверка каждые 15 минут).
#
#  Пароли ящиков — только на сервере: /etc/prostranstvo/pochta-paroli.txt (root, 600).
#  Показать: prostranstvo-pochta passwords. Секретов в скрипте нет — репозиторий открытый.
#  Повторный запуск безопасен: ящики, пароли и письма не трогаются, новые имена добавляются.
# =============================================================================
set -Eeuo pipefail
export LC_ALL=C.UTF-8

CONF_FILE="/etc/prostranstvo/prostranstvo.conf"
LIB_SH="/usr/local/lib/prostranstvo/common.sh"
HELPER="/usr/local/sbin/prostranstvo-pochta"
POCHTA_STATE="/var/lib/prostranstvo-pochta"
TLS_DIR="/etc/prostranstvo/pochta-tls"
PASS_FILE="/etc/prostranstvo/pochta-paroli.txt"
USERS_FILE="/etc/dovecot/pochta-users"
VMAIL_DIR="/var/mail/vhosts"
DKIM_DIR="/var/lib/rspamd/dkim"
DKIM_SELECTOR="mail"
SETUP_LOG="/var/log/prostranstvo-pochta-setup.log"
DETAIL_LOG="/var/log/prostranstvo-pochta-setup-details.log"
DEFAULT_BOXES=(info zakaz yulia mikhail)
TOTAL_STEPS=9

STEP=0
SELFTEST_FAIL=0
CURRENT_STEP="подготовка"
WARNINGS=()
BOXES=()
DOMAIN=""
EMAIL=""
MAIL_HOST=""
TEE_PID=""
WEBMAIL=no
RC_ROOT=""
PHP_SOCK=""
PHP_VER=""

# --- Вывод -----------------------------------------------------------------------
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
  printf 'Исправьте причину и запустите ту же команду ещё раз — повторный запуск безопасен.\n'
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

usage() {
  cat <<'EOF'
Почта на своём домене для сервера «Наш декор».
  curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-pochta.sh | bash -s -- [ЯЩИК ...]

  ЯЩИК — имя до @ (например zakaz). Без параметров: info zakaz yulia mikhail.
  Домен берётся из настроек сервера (сначала запустите setup-prostranstvo.sh с доменом).
После установки:  prostranstvo-pochta  — проверка;  prostranstvo-pochta help — все команды.
EOF
}

parse_args() {
  local a n
  for a in "$@"; do
    case $a in
      -h | --help) usage; exit 0 ;;
      --*) die "неизвестный параметр: $a (см. --help)" ;;
      *)
        n=${a,,}; n=${n%%@*}
        [[ $n =~ ^[a-z0-9]([a-z0-9._-]{0,30}[a-z0-9])?$ ]] || die "непонятное имя ящика «$a» (латиница, цифры, точка, дефис)"
        BOXES+=("$n")
        ;;
    esac
  done
  if ((${#BOXES[@]} == 0)); then BOXES=("${DEFAULT_BOXES[@]}"); fi
}

# =============================================================================
#  Шаги
# =============================================================================
check_all() {
  [[ $(id -u) -eq 0 ]] || { echo "ОШИБКА: запустите от root." >&2; exit 1; }
  local id ver
  id=$(. /etc/os-release 2>/dev/null && printf '%s' "${ID:-}")
  ver=$(. /etc/os-release 2>/dev/null && printf '%s' "${VERSION_ID:-}")
  [[ $id == ubuntu ]] || die "нужна Ubuntu, а здесь «$id»."
  if [[ $ver != 24.04 ]]; then warn "скрипт рассчитан на Ubuntu 24.04, здесь $ver — продолжаю"; fi
  [[ -r $CONF_FILE && -r $LIB_SH ]] || die "сервер ещё не настроен. Сначала: setup-prostranstvo.sh ДОМЕН EMAIL"
  DOMAIN=$(. "$CONF_FILE" && printf '%s' "${DOMAIN:-}")
  EMAIL=$(. "$CONF_FILE" && printf '%s' "${EMAIL:-}")
  [[ -n $DOMAIN ]] || die "у сервера не задан домен. Сначала: setup-prostranstvo.sh ДОМЕН EMAIL"
  MAIL_HOST="mail.$DOMAIN"
  if command -v apache2 >/dev/null 2>&1 && systemctl is-active --quiet apache2 2>/dev/null; then
    die "на сервере работает Apache — он мешает nginx. Это не наш сервер? Ничего не изменено."
  fi
}

step_packages() {
  step "Установка программ (Postfix, Dovecot, Rspamd, Roundcube) — 2–5 минут"
  export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
  local apt=(apt-get -y -q -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)
  local base=(postfix dovecot-core dovecot-imapd dovecot-lmtpd dovecot-sieve rspamd redis-server
    ssl-cert swaks bind9-dnsutils openssl ca-certificates cron)
  local web=(php-fpm roundcube-core roundcube-sqlite3 roundcube-plugins sqlite3)
  local n

  # ответы установщикам заранее, чтобы ничего не спрашивали
  run debconf-set-selections <<EOF
postfix postfix/main_mailer_type select Internet Site
postfix postfix/mailname string $MAIL_HOST
roundcube-core roundcube/dbconfig-install boolean true
roundcube-core roundcube/database-type select sqlite3
roundcube-core roundcube/reconfigure-webserver multiselect
roundcube-core roundcube/restart-webserver boolean false
EOF
  if [[ -n $(dpkg --audit 2>/dev/null) ]]; then
    for n in 1 2 3 4 5 6 7 8 9 10; do
      if run dpkg --configure -a; then break; fi
      info "dpkg занят (идут автообновления?) — жду 20 секунд…"; sleep 20
    done
  fi
  for n in 1 2 3 4 5; do
    if run "${apt[@]}" update; then break; fi
    ((n < 5)) || die "не удалось обновить список пакетов (apt-get update)."
    info "повторяю через 20 секунд…"; sleep 20
  done
  for n in 1 2 3; do
    if run "${apt[@]}" install --no-install-recommends "${base[@]}"; then break; fi
    ((n < 3)) || die "не удалось установить почтовые программы (apt-get install)."
    info "повторяю через 30 секунд…"; sleep 30
  done
  ok "установлено: Postfix $(postconf -h mail_version 2>/dev/null), Dovecot $(dovecot --version 2>/dev/null | cut -d' ' -f1), Rspamd, Redis"

  # Веб-почта. Apache не нужен (сайт на nginx) — если пакеты тянут его, веб-почту пропускаем.
  local sim
  sim=$("${apt[@]}" install --no-install-recommends -s "${web[@]}" 2>&1) || sim=""
  if [[ -z $sim ]]; then
    warn "веб-почта Roundcube: apt не смог посчитать установку — пропускаю (почта на телефонах работает и без неё)"
  elif grep -Eq '^Inst (apache2|libapache2-mod-php)' <<<"$sim"; then
    warn "веб-почта Roundcube требует Apache — пропускаю (почта на телефонах работает и без неё)"
  else
    for n in 1 2 3; do
      if run "${apt[@]}" install --no-install-recommends "${web[@]}"; then WEBMAIL=yes; break; fi
      ((n < 3)) || { warn "веб-почта Roundcube не установилась — см. $DETAIL_LOG"; break; }
      sleep 20
    done
  fi
  if [[ $WEBMAIL == yes ]]; then
    PHP_SOCK=$(ls -1 /run/php/php*-fpm.sock 2>/dev/null | sort -V | tail -n1) || PHP_SOCK=""
    PHP_VER=$(ls -1d /etc/php/*/fpm 2>/dev/null | sort -V | tail -n1 | cut -d/ -f4) || PHP_VER=""
    if [[ -z $PHP_SOCK && -n $PHP_VER ]]; then
      run systemctl enable --now "php$PHP_VER-fpm" || true
      PHP_SOCK="/run/php/php$PHP_VER-fpm.sock"
    fi
    for RC_ROOT in /var/lib/roundcube/public_html /usr/share/roundcube/public_html /var/lib/roundcube /usr/share/roundcube; do
      [[ -f $RC_ROOT/index.php ]] && break
    done
    if [[ -z $PHP_VER || ! -f $RC_ROOT/index.php ]]; then
      warn "веб-почта: не нашёл PHP или файлы Roundcube — пропускаю"
      WEBMAIL=no
    else
      ok "веб-почта Roundcube $(dpkg-query -W -f='${Version}' roundcube-core 2>/dev/null | cut -d+ -f1), PHP $PHP_VER"
    fi
  fi
  # Apache мог прийти зависимостью раньше — он не должен занимать порт 80
  if systemctl list-unit-files apache2.service >/dev/null 2>&1 && systemctl is-enabled --quiet apache2 2>/dev/null; then
    run systemctl disable --now apache2 || true
  fi
}

# Сначала пишется служебная команда — дальше установка пользуется ей же.
write_helper() {
  put_file "$HELPER" 755 <<'PRS_POCHTA'
#!/bin/bash
# prostranstvo-pochta — почта сервера «Наш декор». Создано setup-pochta.sh — руками не править
# (повторная установка перезапишет файл).
set -Eeuo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh
trap 'echo "ОШИБКА в prostranstvo-pochta (строка $LINENO): $BASH_COMMAND" >&2' ERR
if [[ $(id -u) -ne 0 ]]; then echo "Запустите от root." >&2; exit 1; fi
[[ -n ${DOMAIN:-} ]] || { echo "У сервера не задан домен." >&2; exit 1; }

MAIL_HOST="mail.$DOMAIN"
STATE=/var/lib/prostranstvo-pochta
TLS_DIR=/etc/prostranstvo/pochta-tls
PASS_FILE=/etc/prostranstvo/pochta-paroli.txt
USERS_FILE=/etc/dovecot/pochta-users
EXTRA_ALIASES=/etc/prostranstvo/pochta-aliases.txt
PF_BOXES=/etc/postfix/pochta-mailboxes
PF_ALIASES=/etc/postfix/pochta-aliases
PF_SENDERS=/etc/postfix/pochta-senders
PF_OWN=/etc/postfix/pochta-own-domain
VMAIL_DIR=/var/mail/vhosts
DKIM_SELECTOR=mail
DKIM_KEY=/var/lib/rspamd/dkim/$DOMAIN.$DKIM_SELECTOR.key
CERT_LOG=/var/log/prostranstvo-pochta-cert.log
# адреса, которые все ящики могут ставить в «От кого» (общие)
SHARED_SENDERS="info zakaz noreply"
# служебные адреса — пересылаются в ящик ниже (если такого ящика нет — в первый по списку)
SERVICE_ALIASES="postmaster abuse hostmaster webmaster noreply root dmarc"
SERVICE_TARGET=info

exec 8>/run/prostranstvo-pochta.lock
flock 8

norm_box() { # norm_box ИМЯ|АДРЕС → имя до @
  local n=${1,,}
  n=${n%%@*}
  [[ $n =~ ^[a-z0-9]([a-z0-9._-]{0,30}[a-z0-9])?$ ]] || { echo "Непонятное имя ящика: «$1»" >&2; return 1; }
  printf '%s\n' "$n"
}
gen_pw() { LC_ALL=C tr -dc 'A-HJ-NP-Za-km-z2-9' </dev/urandom | head -c 14; echo; }
hash_pw() { printf '%s' "$1" | openssl passwd -6 -stdin; }
boxes() { [[ -f $USERS_FILE ]] && cut -d: -f1 "$USERS_FILE" | sed -n "s/@$DOMAIN\$//p" || true; }
has_box() { boxes | grep -qxF "$1"; }

# set_pw ИМЯ ПАРОЛЬ — записать пароль (хеш — для Dovecot, сам пароль — в файл root:600)
set_pw() {
  local name=$1 pw=$2 addr="$1@$DOMAIN" h tmp
  h=$(hash_pw "$pw")
  install -d -m 755 /etc/dovecot
  touch "$USERS_FILE" "$PASS_FILE"
  tmp=$(mktemp)
  awk -F: -v a="$addr" '$1 != a' "$USERS_FILE" >"$tmp"
  printf '%s:{SHA512-CRYPT}%s::::::\n' "$addr" "$h" >>"$tmp"
  install -m 640 -o root -g dovecot "$tmp" "$USERS_FILE"
  awk -v a="$addr" '$1 != a' "$PASS_FILE" >"$tmp"
  printf '%s %s\n' "$addr" "$pw" >>"$tmp"
  install -m 600 -o root -g root "$tmp" "$PASS_FILE"
  rm -f "$tmp"
}

# rebuild — таблицы Postfix из списка ящиков
rebuild() {
  local b list target alias tmp
  install -d -m 755 /etc/postfix
  list=$(boxes)
  target=$SERVICE_TARGET
  if ! grep -qxF "$target" <<<"$list"; then target=$(head -n1 <<<"$list"); fi
  tmp=$(mktemp)
  for b in $list; do printf '%s@%s %s/%s/\n' "$b" "$DOMAIN" "$DOMAIN" "$b"; done >"$tmp"
  install -m 644 "$tmp" "$PF_BOXES"
  {
    echo "# Создано prostranstvo-pochta. Свои пересылки — в $EXTRA_ALIASES (строка: «откуда куда»)."
    if [[ -n $target ]]; then
      for alias in $SERVICE_ALIASES; do
        grep -qxF "$alias" <<<"$list" || printf '%s@%s %s@%s\n' "$alias" "$DOMAIN" "$target" "$DOMAIN"
      done
    fi
    if [[ -f $EXTRA_ALIASES ]]; then
      awk -v d="$DOMAIN" 'NF >= 2 && $1 !~ /^#/ {
          f = $1; if (f !~ /@/) f = f "@" d
          t = $2; if (t !~ /@/) t = t "@" d
          print f, t }' "$EXTRA_ALIASES"
    fi
  } >"$tmp"
  install -m 644 "$tmp" "$PF_ALIASES"
  {
    for b in $list; do
      if [[ " $SHARED_SENDERS " == *" $b "* ]]; then
        printf '%s@%s %s\n' "$b" "$DOMAIN" "$(sed "s/\$/@$DOMAIN/" <<<"$list" | paste -sd,)"
      else
        printf '%s@%s %s@%s\n' "$b" "$DOMAIN" "$b" "$DOMAIN"
      fi
    done
    for alias in $SHARED_SENDERS; do
      grep -qxF "$alias" <<<"$list" || printf '%s@%s %s\n' "$alias" "$DOMAIN" "$(sed "s/\$/@$DOMAIN/" <<<"$list" | paste -sd,)"
    done
  } >"$tmp"
  install -m 644 "$tmp" "$PF_SENDERS"
  printf '%s REJECT Sender address in our domain requires authentication\n' "$DOMAIN" >"$tmp"
  install -m 644 "$tmp" "$PF_OWN"
  rm -f "$tmp"
  postmap "$PF_BOXES" "$PF_ALIASES" "$PF_SENDERS" "$PF_OWN"
  install -d -m 750 -o vmail -g vmail "$VMAIL_DIR" "$VMAIL_DIR/$DOMAIN"
  if systemctl is-active --quiet postfix; then postfix reload >/dev/null 2>&1 || true; fi
}

cmd_add() {
  local a n added=()
  (($#)) || { echo "Укажите имя ящика: prostranstvo-pochta add zakaz" >&2; return 1; }
  for a in "$@"; do
    n=$(norm_box "$a")
    if has_box "$n"; then
      echo "Ящик $n@$DOMAIN уже есть — не меняю."
    else
      set_pw "$n" "$(gen_pw)"
      added+=("$n@$DOMAIN")
    fi
  done
  rebuild
  if ((${#added[@]})); then
    echo "Созданы ящики: ${added[*]}. Пароли: prostranstvo-pochta passwords"
  fi
}

cmd_passwd() {
  local n pw pw2
  (($# == 1)) || { echo "Нужно: prostranstvo-pochta passwd ЯЩИК" >&2; return 1; }
  n=$(norm_box "$1")
  has_box "$n" || { echo "Ящика $n@$DOMAIN нет. Создать: prostranstvo-pochta add $n" >&2; return 1; }
  if [[ -t 0 ]]; then
    read -r -s -p "Новый пароль для $n@$DOMAIN (Enter — придумать): " pw; echo
    if [[ -n $pw ]]; then
      read -r -s -p "Ещё раз: " pw2; echo
      [[ $pw == "$pw2" ]] || { echo "Пароли не совпали — ничего не изменено." >&2; return 1; }
      ((${#pw} >= 10)) || { echo "Слишком короткий (нужно от 10 символов) — ничего не изменено." >&2; return 1; }
      [[ $pw != *[[:space:]]* ]] || { echo "Без пробелов, пожалуйста — ничего не изменено." >&2; return 1; }
    fi
  else
    pw=""
  fi
  if [[ -z $pw ]]; then pw=$(gen_pw); fi
  set_pw "$n" "$pw"
  doveadm auth cache flush >/dev/null 2>&1 || true
  echo "Пароль $n@$DOMAIN изменён. Посмотреть: prostranstvo-pochta passwords"
}

cmd_passwords() {
  [[ -s $PASS_FILE ]] || { echo "Ящиков пока нет."; return 0; }
  cat <<EOF
==================================================================
 ПАРОЛИ ЯЩИКОВ — не фотографируйте и никому не пересылайте.
 Перепишите в телефон и закройте окно.
==================================================================
EOF
  awk '{printf "  %-28s %s\n", $1, $2}' "$PASS_FILE"
  cat <<EOF

 Настройка на iPhone: Настройки → Приложения → Почта → Учётные записи →
 Новая учётная запись → Другое → Новая учётная запись → IMAP.
   Сервер входящей почты:  $MAIL_HOST   (имя пользователя — весь адрес)
   Сервер исходящей почты: $MAIL_HOST   (то же имя и пароль)
   Порты, если спросит: входящая 993 (SSL), исходящая 465 (SSL) или 587.
 Веб-почта: https://$MAIL_HOST
EOF
}

dkim_pub() { openssl rsa -in "$DKIM_KEY" -pubout -outform DER 2>/dev/null | base64 -w0; }

dns_records() { # строки «ТИП|ИМЯ|ЗНАЧЕНИЕ»
  local ip
  ip=$(server_ip)
  printf 'A|mail|%s\n' "${ip:-IP_СЕРВЕРА}"
  printf 'MX|@|10 %s.\n' "$MAIL_HOST"
  printf 'TXT|@|v=spf1 ip4:%s mx ~all\n' "${ip:-IP_СЕРВЕРА}"
  if [[ -s $DKIM_KEY ]]; then printf 'TXT|%s._domainkey|v=DKIM1; k=rsa; p=%s\n' "$DKIM_SELECTOR" "$(dkim_pub)"; fi
  printf 'TXT|_dmarc|v=DMARC1; p=none; adkim=r; aspf=r\n'
  printf 'PTR|%s|%s\n' "${ip:-IP_СЕРВЕРА}" "$MAIL_HOST"
}

write_public_dns() { # то же — файлом на http://mail.ДОМЕН/pochta-dns.txt (тут только открытые данные)
  install -d -m 755 "$STATE/public"
  { echo "# Записи DNS для почты $DOMAIN ($(ts)). ТИП|ИМЯ|ЗНАЧЕНИЕ"; dns_records; } >"$STATE/public/pochta-dns.txt.tmp"
  mv -f "$STATE/public/pochta-dns.txt.tmp" "$STATE/public/pochta-dns.txt"
  chmod 644 "$STATE/public/pochta-dns.txt"
}

cmd_dns() {
  write_public_dns
  echo "Записи для DNS домена $DOMAIN (DNSmanager FirstVDS → домен → записи):"
  dns_records | while IFS='|' read -r t n v; do
    if [[ $t == PTR ]]; then
      printf '\n  PTR (обратная запись) — в кабинете FirstVDS: Товары → Виртуальные серверы →\n'
      printf '  сервер → IP-адреса → %s → Изменить → Домен: %s\n' "$n" "$v"
    else
      printf '  %-4s %-18s %s\n' "$t" "$n" "$v"
    fi
  done
  echo
  echo "Лишние MX-записи (кроме $MAIL_HOST) удалить."
}

# --- сертификат для mail.ДОМЕН ---------------------------------------------------
le_cert_ok() {
  local c=/etc/letsencrypt/live/$MAIL_HOST/fullchain.pem
  [[ -s $c && -s /etc/letsencrypt/live/$MAIL_HOST/privkey.pem ]] && openssl x509 -checkend 86400 -noout -in "$c" >/dev/null 2>&1
}
use_cert() { # use_cert le|snakeoil
  local src_c src_k
  if [[ $1 == le ]]; then
    src_c=/etc/letsencrypt/live/$MAIL_HOST/fullchain.pem; src_k=/etc/letsencrypt/live/$MAIL_HOST/privkey.pem
  else
    src_c=/etc/ssl/certs/ssl-cert-snakeoil.pem; src_k=/etc/ssl/private/ssl-cert-snakeoil.key
  fi
  install -d -m 755 "$TLS_DIR"
  if [[ $(readlink "$TLS_DIR/fullchain.pem" 2>/dev/null) == "$src_c" && $(readlink "$TLS_DIR/privkey.pem" 2>/dev/null) == "$src_k" ]]; then
    return 1   # уже так
  fi
  ln -sfn "$src_c" "$TLS_DIR/fullchain.pem"
  ln -sfn "$src_k" "$TLS_DIR/privkey.pem"
  return 0
}
reload_all() {
  local s
  for s in postfix dovecot nginx; do
    if systemctl is-active --quiet "$s"; then systemctl reload "$s" >/dev/null 2>&1 || systemctl restart "$s" >/dev/null 2>&1 || true; fi
  done
}

cmd_cert() {
  local auto=no ip recs rc=0 out last_fail
  [[ ${1:-} == --auto ]] && auto=yes
  if le_cert_ok; then
    if use_cert le; then reload_all; fi
    [[ $auto == yes ]] || echo "Сертификат для $MAIL_HOST есть (до $(date -d "$(openssl x509 -enddate -noout -in /etc/letsencrypt/live/$MAIL_HOST/fullchain.pem | cut -d= -f2)" '+%d.%m.%Y'), продлевается сам)."
    return 0
  fi
  [[ -e $TLS_DIR/fullchain.pem ]] || { use_cert snakeoil || true; }
  ip=$(server_ip)
  recs=$(dns_lookup A "$MAIL_HOST" | sort -u | paste -sd' ')
  if [[ $auto == yes ]]; then
    [[ -n $ip && $recs == "$ip" ]] || return 0
    last_fail=$(cat "$STATE/cert-last-fail" 2>/dev/null) || last_fail=0
    [[ $last_fail =~ ^[0-9]+$ ]] || last_fail=0
    (($(date +%s) - last_fail >= 3600)) || return 0
  else
    echo "$MAIL_HOST сейчас указывает на: ${recs:-никуда}; IP сервера: ${ip:-?}"
    if [[ -z $ip || $recs != "$ip" ]]; then
      echo "DNS ещё не указывает на сервер — сертификат получить не выйдет. Сервер сам попробует позже (каждые 15 минут)."
      return 2
    fi
  fi
  local args=(certonly --webroot -w "$STATE/acme" -d "$MAIL_HOST" --cert-name "$MAIL_HOST"
    --non-interactive --agree-tos --keep-until-expiring)
  if [[ -n ${EMAIL:-} ]]; then args+=(--email "$EMAIL" --no-eff-email); else args+=(--register-unsafely-without-email); fi
  log_to "$CERT_LOG" инфо "certbot ${args[*]}"
  out=$(certbot "${args[@]}" 2>&1) || rc=$?
  printf '%s\n' "$out" >>"$CERT_LOG"
  if ((rc == 0)) && le_cert_ok; then
    rm -f "$STATE/cert-last-fail"
    use_cert le || true
    reload_all
    log_to "$CERT_LOG" инфо "сертификат для $MAIL_HOST получен"
    logger -t prostranstvo-pochta "сертификат для $MAIL_HOST получен" 2>/dev/null || true
    [[ $auto == yes ]] || echo "ГОТОВО: сертификат для $MAIL_HOST получен, почта и веб-почта — с настоящим https."
    return 0
  fi
  date +%s >"$STATE/cert-last-fail"
  log_to "$CERT_LOG" ошибка "certbot код $rc"
  if [[ $auto == no ]]; then
    echo "Сертификат не получен (код $rc). Последние строки журнала $CERT_LOG:"
    printf '%s\n' "$out" | tail -n 8 | sed 's/^/   | /'
  fi
  return 1
}

# --- проверка ----------------------------------------------------------------------
line() { if [[ $2 == да ]]; then printf '   [да]  %s\n' "$1"; else printf '   [НЕТ] %s%s\n' "$1" "${3:+ — $3}"; fi; }

cmd_status() {
  local s ip got want port pub
  echo "Почта $DOMAIN — проверка ($(date '+%d.%m.%Y %H:%M'))"
  echo " Службы:"
  for s in postfix dovecot rspamd redis-server; do
    if systemctl is-active --quiet "$s"; then line "$s работает" да; else line "$s работает" нет "systemctl status $s"; fi
  done
  echo " Порты (снаружи открыты в firewall):"
  for port in 25 465 587 993; do
    if ss -Htln "sport = :$port" 2>/dev/null | grep -q .; then line "порт $port слушается" да; else line "порт $port слушается" нет; fi
  done
  echo " Ящики: $(boxes | sed "s/\$/@$DOMAIN/" | paste -sd' ')"
  if le_cert_ok; then
    line "сертификат $MAIL_HOST (Let's Encrypt)" да
  else
    line "сертификат $MAIL_HOST (Let's Encrypt)" нет "пока временный; сервер получит сам, когда домен заработает"
  fi
  ip=$(server_ip)
  echo " DNS (как видит интернет):"
  got=$(dns_lookup A "$MAIL_HOST" | sort -u | paste -sd' ')
  if [[ -n $ip && $got == "$ip" ]]; then line "A $MAIL_HOST → $ip" да; else line "A $MAIL_HOST → $ip" нет "сейчас: ${got:-нет}"; fi
  got=$(dig +short +time=3 +tries=1 MX "$DOMAIN" @77.88.8.8 2>/dev/null | awk '{print $2}' | sed 's/\.$//' | sort -u | paste -sd' ') || got=""
  if [[ $got == "$MAIL_HOST" ]]; then line "MX $DOMAIN → $MAIL_HOST" да; else line "MX $DOMAIN → $MAIL_HOST" нет "сейчас: ${got:-нет}"; fi
  got=$(dig +short +time=3 +tries=1 TXT "$DOMAIN" @77.88.8.8 2>/dev/null | tr -d '"' | grep -i 'v=spf1' | head -n1) || got=""
  if [[ -n $ip && $got == *"$ip"* ]]; then line "SPF" да; else line "SPF (TXT v=spf1 … $ip)" нет "сейчас: ${got:-нет}"; fi
  want=$(dkim_pub 2>/dev/null | cut -c1-60)
  got=$(dig +short +time=3 +tries=1 TXT "$DKIM_SELECTOR._domainkey.$DOMAIN" @77.88.8.8 2>/dev/null | tr -d '" \n') || got=""
  if [[ -n $want && $got == *"$want"* ]]; then line "DKIM ($DKIM_SELECTOR._domainkey)" да; else line "DKIM ($DKIM_SELECTOR._domainkey)" нет "${got:+не совпадает с ключом сервера}${got:-записи нет}"; fi
  got=$(dig +short +time=3 +tries=1 TXT "_dmarc.$DOMAIN" @77.88.8.8 2>/dev/null | tr -d '"') || got=""
  if [[ $got == *DMARC1* ]]; then line "DMARC" да; else line "DMARC (_dmarc)" нет; fi
  got=$(dig +short +time=3 +tries=1 -x "$ip" @77.88.8.8 2>/dev/null | sed 's/\.$//' | head -n1) || got=""
  if [[ $got == "$MAIL_HOST" ]]; then line "PTR $ip → $MAIL_HOST" да; else line "PTR $ip → $MAIL_HOST" нет "сейчас: ${got:-нет} (меняется в кабинете FirstVDS)"; fi
  echo " Отправка наружу (порт 25 у хостинга):"
  pub=no
  for s in mxs.mail.ru mx.yandex.ru gmail-smtp-in.l.google.com; do
    if timeout 8 bash -c "exec 3<>/dev/tcp/$s/25" 2>/dev/null; then pub=yes; break; fi
  done
  if [[ $pub == yes ]]; then line "соединение с почтовыми серверами ($s:25)" да; else line "соединение с почтовыми серверами по порту 25" нет "хостинг блокирует? написать в поддержку FirstVDS"; fi
  got=$(postqueue -p 2>/dev/null | tail -n1)
  if [[ $got == *"empty"* || -z $got ]]; then echo "   очередь писем пуста"; else echo "   в очереди: $got (письма, которые ещё не ушли)"; fi
}

cmd_test() {
  local to=${1:-} from subj qid out i log
  [[ $to =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || { echo "Нужно: prostranstvo-pochta test АДРЕС (например свой@mail.ru)" >&2; return 1; }
  from="info@$DOMAIN"
  has_box info || from="$(boxes | head -n1)@$DOMAIN"
  subj="=?UTF-8?B?$(printf 'Проверка почты %s' "$DOMAIN" | base64 -w0)?="
  out=$(swaks --server 127.0.0.1 --port 25 --from "$from" --to "$to" \
    --header "Subject: $subj" --header "Content-Type: text/plain; charset=UTF-8" \
    --body "Это пробное письмо с сервера $MAIL_HOST. Если оно пришло во «Входящие» — почта работает. Если в «Спам» — отметьте «Не спам»." 2>&1) || true
  qid=$(grep -oE 'queued as [A-Z0-9]+' <<<"$out" | awk '{print $3}' | tail -n1)
  if [[ -z $qid ]]; then echo "Письмо не принято сервером:"; printf '%s\n' "$out" | tail -n 5; return 1; fi
  echo "Письмо $from → $to принято (номер $qid), отправляю…"
  for i in $(seq 1 20); do
    sleep 3
    log=$(journalctl -q --since "-10min" -t postfix/smtp -t postfix/lmtp -t postfix/qmgr 2>/dev/null | grep "$qid" | grep -E 'status=' | tail -n1) || log=""
    [[ -n $log ]] && break
  done
  if [[ $log == *status=sent* ]]; then
    echo "ДОШЛО до сервера получателя: ${log##*status=sent }"
    echo "Проверьте «Входящие» и «Спам» у $to."
  elif [[ -n $log ]]; then
    echo "НЕ ушло: ${log##*status=}"
  else
    echo "Пока нет ответа от сервера получателя. Очередь: postqueue -p ; журнал: journalctl -t postfix/smtp -n 20"
  fi
}

usage() {
  cat <<EOF
prostranstvo-pochta — почта $DOMAIN
  prostranstvo-pochta                 — проверка: службы, порты, сертификат, DNS
  prostranstvo-pochta passwords       — показать пароли ящиков (НЕ фотографировать!)
  prostranstvo-pochta passwd ЯЩИК     — сменить пароль ящика
  prostranstvo-pochta add ЯЩИК …      — добавить ящик (пароль придумается сам)
  prostranstvo-pochta dns             — какие записи нужны в DNS домена
  prostranstvo-pochta test АДРЕС      — отправить пробное письмо (например на свой mail.ru)
  prostranstvo-pochta cert            — получить сертификат для $MAIL_HOST сейчас
EOF
}

case ${1:-status} in
  status) cmd_status ;;
  passwords | paroli) cmd_passwords ;;
  passwd | parol) shift; rc=0; cmd_passwd "$@" || rc=$?; exit "$rc" ;;
  add) shift; cmd_add "$@" ;;
  rebuild) rebuild ;;
  dns) cmd_dns ;;
  dns-file) write_public_dns ;;
  test) shift; rc=0; cmd_test "$@" || rc=$?; exit "$rc" ;;
  cert) shift; rc=0; cmd_cert "$@" || rc=$?; exit "$rc" ;;
  -h | --help | help) usage ;;
  *) usage; exit 1 ;;
esac
PRS_POCHTA
  ok "служебная команда: prostranstvo-pochta (help — список команд)"
}

step_mailboxes() {
  step "Ящики: ${BOXES[*]/%/@$DOMAIN}"
  if ! id -u vmail >/dev/null 2>&1; then
    run useradd --system --user-group --home-dir "$VMAIL_DIR" --no-create-home --shell /usr/sbin/nologin vmail
  fi
  install -d -m 750 -o vmail -g vmail "$VMAIL_DIR" "$VMAIL_DIR/$DOMAIN"
  install -d -m 755 "$POCHTA_STATE" "$POCHTA_STATE/acme" "$POCHTA_STATE/public"
  local before after
  before=$(cut -d: -f1 "$USERS_FILE" 2>/dev/null | grep -c "@$DOMAIN" || true)
  "$HELPER" add "${BOXES[@]}" >>"$DETAIL_LOG" 2>&1 || die "не удалось создать ящики — см. $DETAIL_LOG"
  after=$(cut -d: -f1 "$USERS_FILE" | grep -c "@$DOMAIN" || true)
  ok "ящиков: $after (новых: $((after - before))); пароли — только на сервере, команда prostranstvo-pochta passwords"
  # системная почта (root, postmaster) — тоже в общий ящик
  if [[ -f /etc/aliases ]] && ! grep -q '^root:' /etc/aliases; then
    printf 'root: info@%s\n' "$DOMAIN" >>/etc/aliases
  fi
  run newaliases || true
}

step_tls() {
  step "Сертификат для $MAIL_HOST"
  [[ -s /etc/ssl/certs/ssl-cert-snakeoil.pem ]] || run make-ssl-cert generate-default-snakeoil --force-overwrite || true
  install -d -m 755 "$TLS_DIR"
  if [[ ! -e $TLS_DIR/fullchain.pem ]]; then
    ln -sfn /etc/ssl/certs/ssl-cert-snakeoil.pem "$TLS_DIR/fullchain.pem"
    ln -sfn /etc/ssl/private/ssl-cert-snakeoil.key "$TLS_DIR/privkey.pem"
  fi
  # при продлении сертификата — перечитать его в почте и nginx
  put_file /etc/letsencrypt/renewal-hooks/deploy/prostranstvo-pochta 755 <<EOF
#!/bin/sh
# Создано setup-pochta.sh: после продления сертификата $MAIL_HOST перечитать его.
case "\${RENEWED_LINEAGE:-}" in
  */$MAIL_HOST) systemctl reload postfix dovecot nginx >/dev/null 2>&1 || true ;;
esac
EOF
  ok "пока временный сертификат; настоящий сервер получит сам (см. шаг «Веб-почта»)"
}

step_postfix() {
  step "Postfix: приём писем (порт 25) и отправка с паролем (465, 587)"
  local own_ip=""
  postconf -e \
    "compatibility_level = 3.6" \
    "myhostname = $MAIL_HOST" \
    "mydomain = $DOMAIN" \
    "myorigin = \$mydomain" \
    "mydestination = localhost, localhost.localdomain, $MAIL_HOST" \
    "inet_interfaces = all" \
    "inet_protocols = ipv4" \
    "mynetworks = 127.0.0.0/8" \
    "smtpd_banner = \$myhostname ESMTP" \
    "biff = no" \
    "append_dot_mydomain = no" \
    "recipient_delimiter = +" \
    "message_size_limit = 31457280" \
    "mailbox_size_limit = 0" \
    "disable_vrfy_command = yes" \
    "smtpd_helo_required = yes" \
    "virtual_mailbox_domains = $DOMAIN" \
    "virtual_mailbox_maps = hash:/etc/postfix/pochta-mailboxes" \
    "virtual_alias_maps = hash:/etc/postfix/pochta-aliases" \
    "virtual_transport = lmtp:unix:private/dovecot-lmtp" \
    "smtpd_sender_login_maps = hash:/etc/postfix/pochta-senders" \
    "smtpd_tls_cert_file = $TLS_DIR/fullchain.pem" \
    "smtpd_tls_key_file = $TLS_DIR/privkey.pem" \
    "smtpd_tls_security_level = may" \
    "smtpd_tls_auth_only = yes" \
    "smtpd_tls_mandatory_protocols = >=TLSv1.2" \
    "smtpd_tls_protocols = >=TLSv1.2" \
    "smtp_tls_security_level = may" \
    "smtp_tls_CApath = /etc/ssl/certs" \
    "smtp_tls_loglevel = 1" \
    "smtpd_sasl_type = dovecot" \
    "smtpd_sasl_path = private/auth" \
    "smtpd_sasl_auth_enable = no" \
    "smtpd_helo_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_invalid_helo_hostname, reject_non_fqdn_helo_hostname" \
    "smtpd_sender_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_non_fqdn_sender, reject_unknown_sender_domain, check_sender_access hash:/etc/postfix/pochta-own-domain" \
    "smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, defer_unauth_destination" \
    "smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_non_fqdn_recipient, reject_unknown_recipient_domain, reject_unauth_destination" \
    "milter_protocol = 6" \
    "milter_default_action = accept" \
    "smtpd_milters = inet:127.0.0.1:11332" \
    "non_smtpd_milters = inet:127.0.0.1:11332" \
    >>"$DETAIL_LOG" 2>&1 || die "не удалось записать настройки Postfix"
  printf '%s\n' "$MAIL_HOST" >/etc/mailname

  local svc opts=(
    "smtpd_tls_security_level=encrypt"
    "smtpd_sasl_auth_enable=yes"
    "smtpd_tls_auth_only=yes"
    "smtpd_client_restrictions=permit_sasl_authenticated,reject"
    "smtpd_sender_restrictions=reject_sender_login_mismatch,permit_sasl_authenticated,reject"
    "smtpd_relay_restrictions=permit_sasl_authenticated,reject"
    "smtpd_recipient_restrictions=permit_sasl_authenticated,reject"
    "milter_macro_daemon_name=ORIGINATING"
  )
  postconf -M "submission/inet=submission inet n - y - - smtpd"
  postconf -M "465/inet=465 inet n - y - - smtpd"
  local o
  for svc in submission 465; do
    for o in "${opts[@]}"; do postconf -P "$svc/inet/$o"; done
  done
  postconf -P "submission/inet/syslog_name=postfix/submission"
  postconf -P "465/inet/syslog_name=postfix/smtps"
  postconf -P "465/inet/smtpd_tls_wrappermode=yes"

  "$HELPER" rebuild >>"$DETAIL_LOG" 2>&1 || die "не удалось собрать таблицы ящиков Postfix"
  if ! out=$(postfix check 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    warn "postfix check: $(head -n1 <<<"$out")"
  fi
  run systemctl enable postfix
  run systemctl restart postfix || die "Postfix не запустился — см. journalctl -u postfix@-"
  ok "Postfix: $MAIL_HOST, ящики домена $DOMAIN, отправка только с паролем"
}

step_dovecot() {
  step "Dovecot: почта на телефонах и компьютерах (IMAP, порт 993)"
  local uid gid
  uid=$(id -u vmail); gid=$(id -g vmail)
  # вход только по ящикам из pochta-users (не системными пользователями сервера)
  if grep -Eq '^[[:space:]]*!include auth-system\.conf\.ext' /etc/dovecot/conf.d/10-auth.conf; then
    sed -i -E 's/^([[:space:]]*)!include auth-system\.conf\.ext/\1#!include auth-system.conf.ext  # выключено setup-pochta.sh/' /etc/dovecot/conf.d/10-auth.conf
  fi
  install -d -m 755 /etc/dovecot/sieve
  put_file /etc/dovecot/sieve/spam-to-junk.sieve 644 <<'EOF'
# Создано setup-pochta.sh: письма, помеченные фильтром как спам, — в папку «Спам» (Junk).
require ["fileinto", "mailbox"];
if header :is "X-Spam" "Yes" {
  fileinto :create "Junk";
  stop;
}
EOF
  put_file /etc/dovecot/local.conf 644 <<EOF
# Создано setup-pochta.sh — руками не править (повторная установка перезапишет файл).
protocols = imap lmtp
listen = *
ssl = required
ssl_cert = <$TLS_DIR/fullchain.pem
ssl_key = <$TLS_DIR/privkey.pem
ssl_min_protocol = TLSv1.2
ssl_prefer_server_ciphers = no
disable_plaintext_auth = yes
auth_mechanisms = plain login
auth_username_format = %Lu
first_valid_uid = $uid
last_valid_uid = $uid
mail_location = maildir:~/Maildir
mail_privileged_group = mail
postmaster_address = postmaster@$DOMAIN
hostname = $MAIL_HOST

passdb {
  driver = passwd-file
  args = scheme=SHA512-CRYPT username_format=%Lu $USERS_FILE
}
userdb {
  driver = static
  args = uid=$uid gid=$gid home=$VMAIL_DIR/%d/%n
}

namespace inbox {
  inbox = yes
  mailbox Drafts {
    special_use = \\Drafts
    auto = subscribe
  }
  mailbox Sent {
    special_use = \\Sent
    auto = subscribe
  }
  mailbox Junk {
    special_use = \\Junk
    auto = subscribe
  }
  mailbox Trash {
    special_use = \\Trash
    auto = subscribe
  }
}

service imap-login {
  inet_listener imap {
    address = 127.0.0.1
    port = 143
  }
  inet_listener imaps {
    port = 993
    ssl = yes
  }
}
service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}
service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0660
    user = postfix
    group = postfix
  }
}
protocol lmtp {
  mail_plugins = \$mail_plugins sieve
}
plugin {
  sieve_before = /etc/dovecot/sieve/spam-to-junk.sieve
}
EOF
  run sievec /etc/dovecot/sieve/spam-to-junk.sieve || warn "не скомпилировался фильтр «спам → папка Спам»"
  if ! out=$(doveconf -n 2>&1 >/dev/null); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    die "Dovecot не принял настройки: $(head -n2 <<<"$out")"
  fi
  run systemctl enable dovecot
  run systemctl restart dovecot || die "Dovecot не запустился — см. journalctl -u dovecot"
  ok "Dovecot: IMAP 993 (SSL), вход — полный адрес ящика и пароль"
}

step_rspamd() {
  step "Rspamd: подпись писем (DKIM) и фильтр спама"
  local ru
  ru=$(id -un _rspamd 2>/dev/null || id -un rspamd 2>/dev/null) || die "не найден пользователь rspamd"
  # Redis — память для фильтра (обучение, ограничения); не больше 64 МБ
  put_file /etc/redis/prostranstvo.conf 644 <<'EOF'
# Создано setup-pochta.sh: Redis для фильтра спама — только локально и не больше 64 МБ.
maxmemory 64mb
maxmemory-policy volatile-lru
EOF
  if ! grep -qxF 'include /etc/redis/prostranstvo.conf' /etc/redis/redis.conf; then
    printf '\ninclude /etc/redis/prostranstvo.conf\n' >>/etc/redis/redis.conf
  fi
  run systemctl enable redis-server
  run systemctl restart redis-server || warn "Redis не запустился — фильтр спама будет работать хуже"

  install -d -m 750 -o "$ru" -g "$ru" "$DKIM_DIR"
  local key="$DKIM_DIR/$DOMAIN.$DKIM_SELECTOR.key"
  if [[ ! -s $key ]]; then
    run openssl genrsa -out "$key" 2048 || die "не удалось создать ключ DKIM"
  fi
  chown "$ru:$ru" "$key"; chmod 640 "$key"

  put_file /etc/rspamd/local.d/worker-proxy.inc 644 <<'EOF'
# Создано setup-pochta.sh: Rspamd как фильтр (milter) для Postfix.
milter = yes;
timeout = 120s;
upstream "local" {
  default = yes;
  self_scan = yes;
}
EOF
  put_file /etc/rspamd/local.d/redis.conf 644 <<'EOF'
servers = "127.0.0.1:6379";
EOF
  put_file /etc/rspamd/local.d/dkim_signing.conf 644 <<EOF
# Создано setup-pochta.sh: подписывать письма своих ящиков и сайта ключом DKIM.
enabled = true;
path = "$DKIM_DIR/\$domain.\$selector.key";
selector = "$DKIM_SELECTOR";
sign_authenticated = true;
sign_local = true;
use_domain = "header";
allow_username_mismatch = true;
EOF
  put_file /etc/rspamd/local.d/arc.conf 644 <<EOF
path = "$DKIM_DIR/\$domain.\$selector.key";
selector = "$DKIM_SELECTOR";
sign_authenticated = true;
sign_local = true;
use_domain = "header";
allow_username_mismatch = true;
EOF
  # Без «серых списков»: первое письмо от нового клиента не должно задерживаться.
  put_file /etc/rspamd/local.d/greylist.conf 644 <<'EOF'
enabled = false;
EOF
  put_file /etc/rspamd/local.d/actions.conf 644 <<'EOF'
# Создано setup-pochta.sh: от 6 баллов — в папку «Спам», от 15 — отклонить.
reject = 15;
add_header = 6;
greylist = null;
EOF
  put_file /etc/rspamd/local.d/milter_headers.conf 644 <<'EOF'
use = ["authentication-results", "x-spamd-bar"];
authenticated_headers = ["authentication-results"];
skip_local = false;
skip_authenticated = true;
EOF
  put_file /etc/rspamd/local.d/classifier-bayes.conf 644 <<'EOF'
backend = "redis";
autolearn = true;
EOF
  if ! out=$(rspamadm configtest 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    die "Rspamd не принял настройки: $(tail -n2 <<<"$out")"
  fi
  run systemctl enable rspamd
  run systemctl restart rspamd || die "Rspamd не запустился — см. journalctl -u rspamd"
  local n
  for n in $(seq 1 15); do
    if ss -Htln 'sport = :11332' | grep -q .; then break; fi
    sleep 1
  done
  ok "Rspamd: подпись DKIM (селектор $DKIM_SELECTOR, 2048 бит), спам → папка «Спам»"
}

step_webmail() {
  step "Веб-почта https://$MAIL_HOST и сертификат"
  local site=/etc/nginx/sites-available/prostranstvo-pochta.conf link=/etc/nginx/sites-enabled/prostranstvo-pochta.conf
  local l6=no h2_listen="" h2_line="" ver bak=""
  [[ -e /proc/net/if_inet6 ]] && l6=yes
  ver=$(nginx -v 2>&1 | sed -n 's#^.*nginx/\([0-9][0-9.]*\).*$#\1#p') || ver=""
  if dpkg --compare-versions "${ver:-0}" ge 1.25.1; then h2_line="    http2 on;"; else h2_listen=" http2"; fi

  if [[ $WEBMAIL == yes ]]; then
    put_file /etc/roundcube/pochta.inc.php 640 root:www-data <<EOF
<?php
// Создано setup-pochta.sh — руками не править (повторная установка перезапишет файл).
\$config['imap_host'] = 'ssl://127.0.0.1:993';
\$config['default_host'] = 'ssl://127.0.0.1:993';
\$config['imap_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false]];
\$config['smtp_host'] = 'ssl://127.0.0.1:465';
\$config['smtp_server'] = 'ssl://127.0.0.1';
\$config['smtp_port'] = 465;
\$config['smtp_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false]];
\$config['smtp_user'] = '%u';
\$config['smtp_pass'] = '%p';
\$config['username_domain'] = '$DOMAIN';
\$config['username_domain_forced'] = true;
\$config['mail_domain'] = '$DOMAIN';
\$config['product_name'] = 'Почта «Наш декор»';
\$config['language'] = 'ru_RU';
\$config['skin'] = 'elastic';
\$config['plugins'] = ['archive', 'zipdownload'];
\$config['drafts_mbox'] = 'Drafts';
\$config['sent_mbox'] = 'Sent';
\$config['junk_mbox'] = 'Junk';
\$config['trash_mbox'] = 'Trash';
\$config['max_message_size'] = '25M';
\$config['session_lifetime'] = 120;
\$config['ip_check'] = true;
\$config['login_rate_limit'] = 3;
\$config['support_url'] = '';
EOF
    if ! grep -q 'pochta.inc.php' /etc/roundcube/config.inc.php; then
      # закрывающий «?>» в конце мешает дописать строку — убираем его
      sed -i -e ':a' -e '/^[[:space:]]*$/{$d;N;ba' -e '}' /etc/roundcube/config.inc.php
      sed -i '${/^[[:space:]]*?>[[:space:]]*$/d}' /etc/roundcube/config.inc.php
      printf "\n// Настройки почты «Наш декор» (setup-pochta.sh)\n@include('/etc/roundcube/pochta.inc.php');\n" >>/etc/roundcube/config.inc.php
    fi
    put_file "/etc/php/$PHP_VER/fpm/conf.d/99-prostranstvo-pochta.ini" 644 <<'EOF'
; Создано setup-pochta.sh: вложения в веб-почте до 25 МБ.
upload_max_filesize = 25M
post_max_size = 30M
memory_limit = 256M
expose_php = Off
EOF
    install -d -m 750 -o www-data -g adm /var/log/roundcube
    touch /var/log/roundcube/errors.log
    chown www-data:adm /var/log/roundcube/errors.log
    run systemctl enable "php$PHP_VER-fpm"
    run systemctl restart "php$PHP_VER-fpm" || warn "PHP не перезапустился — веб-почта может не открыться"
  fi

  local tmp
  tmp=$(mktemp)
  {
    echo "# Почта $MAIL_HOST. Создано setup-pochta.sh — руками не править."
    echo "server {"
    echo "    listen 80;"
    [[ $l6 == yes ]] && echo "    listen [::]:80;"
    echo "    server_name $MAIL_HOST;"
    echo "    location ^~ /.well-known/acme-challenge/ {"
    echo "        root $POCHTA_STATE/acme;"
    echo "        default_type text/plain;"
    echo "    }"
    echo "    location = /pochta-dns.txt {"
    echo "        root $POCHTA_STATE/public;"
    echo "        default_type \"text/plain; charset=utf-8\";"
    echo "    }"
    echo "    location / {"
    echo "        return 301 https://$MAIL_HOST\$request_uri;"
    echo "    }"
    echo "}"
    echo
    echo "server {"
    echo "    listen 443 ssl$h2_listen;"
    [[ $l6 == yes ]] && echo "    listen [::]:443 ssl$h2_listen;"
    [[ -n $h2_line ]] && echo "$h2_line"
    echo "    server_name $MAIL_HOST;"
    echo "    ssl_certificate     $TLS_DIR/fullchain.pem;"
    echo "    ssl_certificate_key $TLS_DIR/privkey.pem;"
    echo "    ssl_protocols TLSv1.2 TLSv1.3;"
    echo "    server_tokens off;"
    echo "    add_header X-Content-Type-Options \"nosniff\" always;"
    echo "    add_header Referrer-Policy \"same-origin\" always;"
    echo "    location = /pochta-dns.txt {"
    echo "        root $POCHTA_STATE/public;"
    echo "        default_type \"text/plain; charset=utf-8\";"
    echo "    }"
    if [[ $WEBMAIL == yes ]]; then
      echo "    root $RC_ROOT;"
      echo "    index index.php;"
      echo "    client_max_body_size 30m;"
      echo "    location ~ /\\. {"
      echo "        deny all;"
      echo "    }"
      echo "    location ~ ^/(bin|config|installer|logs|SQL|temp|vendor)/ {"
      echo "        deny all;"
      echo "    }"
      echo "    location ~ \\.php\$ {"
      echo "        include snippets/fastcgi-php.conf;"
      echo "        fastcgi_pass unix:$PHP_SOCK;"
      echo "    }"
    else
      echo "    location / {"
      echo "        default_type \"text/plain; charset=utf-8\";"
      echo "        return 200 \"Почта $DOMAIN работает. Веб-почта не установлена — используйте почту на телефоне.\\n\";"
      echo "    }"
    fi
    echo "}"
  } >"$tmp"
  if [[ -f $site ]]; then bak=$(mktemp); cp -a "$site" "$bak"; fi
  install -m 644 "$tmp" "$site"; rm -f "$tmp"
  ln -sfn "$site" "$link"
  if ! out=$(nginx -t 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    if [[ -n $bak ]]; then cp -a "$bak" "$site"; else rm -f "$site" "$link"; fi
    warn "nginx не принял настройки веб-почты — вернул прежние (сайт не затронут): $(grep -m1 emerg <<<"$out")"
  else
    run systemctl reload nginx || run systemctl restart nginx || true
    if [[ $WEBMAIL == yes ]]; then ok "веб-почта: https://$MAIL_HOST (вход — имя ящика и пароль)"; fi
  fi
  [[ -n $bak ]] && rm -f "$bak"
  "$HELPER" dns-file >>"$DETAIL_LOG" 2>&1 || true

  # настоящий сертификат — сейчас (если домен уже работает) и потом каждые 15 минут сам
  put_file /etc/cron.d/prostranstvo-pochta 644 <<'EOF'
# Создано setup-pochta.sh: получить сертификат для mail.ДОМЕН, как только домен заработает.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/15 * * * *  root  /usr/local/sbin/prostranstvo-pochta cert --auto 2>&1 | logger -t prostranstvo-pochta
EOF
  local rc=0
  "$HELPER" cert 2>&1 | sed 's/^/     /' || rc=${PIPESTATUS[0]}
  if ((rc == 2)); then
    info "пока временный сертификат: телефоны при первом входе спросят «Доверять?» — лучше подождать настоящего."
  fi
}

step_protect() {
  step "Firewall и защита от подбора паролей"
  local p
  for p in 25 465 587 993; do run ufw allow "$p/tcp" comment 'Почта' || true; done
  ok "ufw: открыты 25 (приём писем), 465 и 587 (отправка), 993 (IMAP)"

  put_file /etc/fail2ban/jail.d/prostranstvo-pochta.local 644 <<'EOF'
# Создано setup-pochta.sh: 6 неверных паролей за 10 минут — адрес блокируется на 1 час.
[postfix-sasl]
enabled    = true
backend    = systemd
journalmatch = _SYSTEMD_UNIT=postfix@-.service
port       = smtp,465,submission
maxretry   = 6
findtime   = 10m
bantime    = 1h

[dovecot]
enabled    = true
backend    = systemd
journalmatch = _SYSTEMD_UNIT=dovecot.service
port       = imap,imaps
maxretry   = 6
findtime   = 10m
bantime    = 1h
EOF
  if [[ $WEBMAIL == yes ]]; then
    cat >>/etc/fail2ban/jail.d/prostranstvo-pochta.local <<'EOF'

[roundcube-auth]
enabled    = true
backend    = auto
logpath    = /var/log/roundcube/errors.log
port       = http,https
maxretry   = 6
findtime   = 10m
bantime    = 1h
EOF
  fi
  if ! out=$(fail2ban-client -t 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    rm -f /etc/fail2ban/jail.d/prostranstvo-pochta.local
    warn "fail2ban не принял защиту почты — убрал её (защита SSH работает как раньше)"
  fi
  if run systemctl restart fail2ban; then
    sleep 3
    ok "fail2ban: $(fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:[[:space:]]*//p')"
  else
    warn "fail2ban не перезапустился — см. journalctl -u fail2ban"
  fi

  put_file /etc/logrotate.d/prostranstvo-pochta 644 <<'EOF'
# Создано setup-pochta.sh
/var/log/prostranstvo-pochta-cert.log /var/log/prostranstvo-pochta-setup.log /var/log/prostranstvo-pochta-setup-details.log {
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

# --- самопроверка ------------------------------------------------------------------
maildir_count() { # maildir_count ЯЩИК — писем во «Входящих»
  local d="$VMAIL_DIR/$DOMAIN/$1/Maildir"
  { find "$d/new" "$d/cur" -type f 2>/dev/null || true; } | wc -l
}
last_mail() { # last_mail ЯЩИК — путь к последнему письму
  local d="$VMAIL_DIR/$DOMAIN/$1/Maildir"
  { ls -1t "$d/new"/* "$d/cur"/* 2>/dev/null || true; } | sed -n 1p
}
pw_of() { awk -v a="$1@$DOMAIN" '$1 == a {print $2}' "$PASS_FILE"; }
check() { if [[ $2 == "$3" ]]; then printf '   [да]  %s\n' "$1"; else printf '   [НЕТ] %s (%s)\n' "$1" "$2"; SELFTEST_FAIL=$((SELFTEST_FAIL + 1)); fi; }

step_selftest() {
  step "Самопроверка"
  SELFTEST_FAIL=0
  local a b pw before f res code ip
  a=${BOXES[0]}; b=${BOXES[1]:-${BOXES[0]}}
  local s
  for s in postfix dovecot rspamd redis-server; do
    if systemctl is-active --quiet "$s"; then check "$s работает" да да; else check "$s работает" нет да; fi
  done
  for s in 25 465 587 993; do
    if ss -Htln "sport = :$s" | grep -q .; then check "порт $s" да да; else check "порт $s" "не слушается" да; fi
  done

  # 1) письмо снаружи (без пароля) — в ящик
  before=$(maildir_count "$a")
  res=$(swaks --silent 1 --server 127.0.0.1 --port 25 --from "selftest@example.org" --to "$a@$DOMAIN" \
    --header "Subject: selftest-in" --body "Проверка приёма" 2>&1) && code=ok || code="$res"
  for s in $(seq 1 15); do (($(maildir_count "$a") > before)) && break; sleep 1; done
  if (($(maildir_count "$a") > before)); then check "приём письма в ящик $a@" да да; else check "приём письма в ящик $a@" "${code:0:80}" да; fi

  # 2) отправка с паролем (как телефон) — подпись DKIM
  pw=$(pw_of "$a")
  before=$(maildir_count "$b")
  res=$(swaks --silent 1 --server 127.0.0.1 --port 465 --tls-on-connect --auth LOGIN \
    --auth-user "$a@$DOMAIN" --auth-password "$pw" --from "$a@$DOMAIN" --to "$b@$DOMAIN" \
    --header "Subject: selftest-out" --body "Проверка отправки" 2>&1) && code=ok || code=$(grep -m1 -E '^<~?\*+ *[45]' <<<"$res" || echo "ошибка")
  for s in $(seq 1 15); do (($(maildir_count "$b") > before)) && break; sleep 1; done
  if (($(maildir_count "$b") > before)); then
    check "отправка с паролем (порт 465)" да да
    f=$(last_mail "$b")
    if grep -q '^DKIM-Signature:.*d='"$DOMAIN" "$f" 2>/dev/null || grep -A3 '^DKIM-Signature:' "$f" 2>/dev/null | grep -q "d=$DOMAIN"; then
      check "подпись DKIM у исходящих" да да
    else
      check "подпись DKIM у исходящих" "нет подписи" да
    fi
  else
    check "отправка с паролем (порт 465)" "${code:0:80}" да
  fi

  # 3) неверный пароль — отказ; чужим (без пароля) — не пересылаем
  if swaks --silent 2 --server 127.0.0.1 --port 587 --tls --auth LOGIN --auth-user "$a@$DOMAIN" \
    --auth-password "wrong-$RANDOM" --from "$a@$DOMAIN" --to "$b@$DOMAIN" --quit-after AUTH >/dev/null 2>&1; then
    check "неверный пароль не принимается" "принят!" да
  else
    check "неверный пароль не принимается" да да
  fi
  ip=$(ip -4 -o addr show scope global 2>/dev/null | awk 'NR == 1 {sub(/\/.*/, "", $4); print $4}') || ip=""
  if [[ -n $ip ]]; then
    res=$(swaks --server "$ip" --port 25 --from "relaytest@gmail.com" --to "relaytest@example.com" --quit-after RCPT 2>&1) && code=ok || code=fail
    if [[ $code == fail ]] && grep -qiE 'Relay access denied' <<<"$res"; then
      check "чужие письма не пересылаются (нет «открытого релея»)" да да
    else
      check "чужие письма не пересылаются (нет «открытого релея»)" "пересылает!" да
    fi
  fi

  # 4) IMAP — как телефон
  pw=$(pw_of "$b")
  res=$(curl -s --max-time 15 -k "imaps://127.0.0.1/" --user "$b@$DOMAIN:$pw" -X 'STATUS INBOX (MESSAGES)' 2>&1) || res=""
  if [[ $res == *MESSAGES* ]]; then check "вход в ящик по IMAP (993)" да да; else check "вход в ящик по IMAP (993)" "не вошёл" да; fi

  # 5) веб-почта
  if [[ $WEBMAIL == yes ]]; then
    code=$(curl -sk -o /tmp/rc-selftest.html -w '%{http_code}' --max-time 15 --resolve "$MAIL_HOST:443:127.0.0.1" "https://$MAIL_HOST/" 2>/dev/null) || code=000
    if [[ $code == 200 ]] && grep -qi 'rcmloginuser\|roundcube' /tmp/rc-selftest.html; then check "веб-почта открывается" да да; else check "веб-почта открывается" "ответ $code" да; fi
    rm -f /tmp/rc-selftest.html
  fi
  # пробные письма убрать
  for s in "$a" "$b"; do
    doveadm expunge -u "$s@$DOMAIN" mailbox '*' subject selftest- >>"$DETAIL_LOG" 2>&1 || true
  done
  if ((SELFTEST_FAIL == 0)); then ok "всё работает внутри сервера"; else warn "самопроверка: не прошло проверок — $SELFTEST_FAIL (подробности выше)"; fi
}

summary() {
  printf '\n==================================================================\n'
  if ((${#WARNINGS[@]})); then printf ' ПОЧТА УСТАНОВЛЕНА, но есть замечания:\n'; for w in "${WARNINGS[@]}"; do printf '   ! %s\n' "$w"; done
  else printf ' ПОЧТА УСТАНОВЛЕНА\n'; fi
  printf '==================================================================\n'
  printf ' Ящики: %s\n' "$(cut -d: -f1 "$USERS_FILE" | paste -sd' ')"
  printf ' Пароли — только на сервере. Показать (не фотографировать!):\n'
  printf '     prostranstvo-pochta passwords\n'
  printf ' Веб-почта: https://%s\n\n' "$MAIL_HOST"
  "$HELPER" dns 2>/dev/null | sed 's/^/ /' || true
  printf '\n Проверка в любой момент:  prostranstvo-pochta\n'
  printf ' Пробное письмо наружу:     prostranstvo-pochta test свой@mail.ru\n'
  printf ' Журнал установки: %s\n' "$SETUP_LOG"
  printf '==================================================================\n'
}

main() {
  trap '' HUP
  exec </dev/null
  parse_args "$@"
  install -d -m 755 /var/log
  touch "$SETUP_LOG" "$DETAIL_LOG"
  chmod 640 "$SETUP_LOG" "$DETAIL_LOG"
  exec > >(tee --output-error=warn -a "$SETUP_LOG") 2>&1
  TEE_PID=$!
  trap on_exit EXIT
  trap 'on_err $? $LINENO' ERR
  printf '\n=== Почта для сервера «Наш декор» — %s ===\n' "$(date '+%d.%m.%Y %H:%M')"
  printf '\n=== %s: запуск ===\n' "$(date '+%F %T')" >>"$DETAIL_LOG"
  exec 9>/run/prostranstvo-pochta-setup.lock
  flock -n 9 || die "установка почты уже идёт в другом окне."
  check_all
  info "домен: $DOMAIN, почтовый сервер: $MAIL_HOST"

  step_packages
  write_helper
  step_mailboxes
  step_tls
  step_postfix
  step_dovecot
  step_rspamd
  step_webmail
  step_protect
  step_selftest
  summary
}

main "$@"
