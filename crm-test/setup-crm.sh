#!/usr/bin/env bash
# =============================================================================
#  setup-crm.sh — CRM магазина «Наш декор» на своём сервере (Ubuntu 24.04).
#  Запускать от root ПОСЛЕ setup-prostranstvo.sh с доменом:
#
#    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-crm.sh | bash
#
#  Адрес: https://crm.ДОМЕН. Пользователи по умолчанию: yulia (Юлия) и mikhail (Михаил),
#  оба — владельцы. Пароли — только на сервере: /etc/prostranstvo/crm-paroli.txt (root, 600),
#  показать: prostranstvo-crm passwords.
#  Что ставит: Flask + gunicorn (пакеты Ubuntu), служба prostranstvo-crm (127.0.0.1:8081),
#  nginx для crm.ДОМЕН (сертификат — сам, когда домен заработает), fail2ban на вход,
#  ночные копии баз CRM и бота (14 дней). Заявки с сайта выключены, пока нет уведомления
#  в Роскомнадзор (включить: prostranstvo-crm site-leads on).
#  Повторный запуск безопасен: база, пользователи и пароли не трогаются, код обновляется.
#  Секретов в скрипте нет — репозиторий открытый.
# =============================================================================
set -Eeuo pipefail
export LC_ALL=C.UTF-8

CONF_FILE="/etc/prostranstvo/prostranstvo.conf"
LIB_SH="/usr/local/lib/prostranstvo/common.sh"
REPO_URL="https://github.com/mikhailusenko88-hub/Mikhail.git"
REPO_BRANCH="server"
APP_USER="prostranstvo"
BASE="/opt/prostranstvo-crm"
SRC="$BASE/src"
APP="$SRC/crm"
ENV_FILE="/etc/prostranstvo/crm.env"
SECRET_FILE="/etc/prostranstvo/crm-secret"
PASS_FILE="/etc/prostranstvo/crm-paroli.txt"
STATE_DIR="/var/lib/prostranstvo"
CRM_DB="$STATE_DIR/crm.db"
BOT_DB="$STATE_DIR/bot.db"
CATALOG_FILE="/var/www/prostranstvo/index.html"
TLS_DIR="/etc/prostranstvo/crm-tls"
CRM_STATE="/var/lib/prostranstvo-crm"
BACKUP_DIR="/var/backups/prostranstvo"
HELPER="/usr/local/sbin/prostranstvo-crm"
PORT=8081
SETUP_LOG="/var/log/prostranstvo-crm-setup.log"
DETAIL_LOG="/var/log/prostranstvo-crm-setup-details.log"
TOTAL_STEPS=7
DEFAULT_USERS=("yulia|Юлия|admin" "mikhail|Михаил|admin")

STEP=0
CURRENT_STEP="подготовка"
WARNINGS=()
DOMAIN=""
EMAIL=""
CRM_HOST=""
TEE_PID=""
FAILS=0

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
gen_pw() {
  local s=""
  while ((${#s} < 14)); do s+=$(head -c 96 /dev/urandom | LC_ALL=C tr -dc 'A-HJ-NP-Za-km-z2-9'); done
  printf '%s\n' "${s:0:14}"
}
# manage.py от пользователя приложения, с настройками из crm.env
manage() {
  runuser -u "$APP_USER" -- env CRM_DB="$CRM_DB" BOT_DB="$BOT_DB" CATALOG_FILE="$CATALOG_FILE" \
    python3 "$APP/manage.py" "$@"
}

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
  id -u "$APP_USER" >/dev/null 2>&1 || die "нет пользователя $APP_USER — сначала setup-prostranstvo.sh"
  CRM_HOST="crm.$DOMAIN"
}

step_packages() {
  step "Программы (Python Flask, gunicorn) — 1–2 минуты"
  export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
  local apt=(apt-get -y -q -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)
  local pkgs=(python3 python3-flask gunicorn git sqlite3 ssl-cert curl ca-certificates cron bind9-dnsutils) n
  for n in 1 2 3 4 5; do
    if run "${apt[@]}" update; then break; fi
    ((n < 5)) || die "не удалось обновить список пакетов (apt-get update)."
    sleep 20
  done
  for n in 1 2 3; do
    if run "${apt[@]}" install --no-install-recommends "${pkgs[@]}"; then break; fi
    ((n < 3)) || die "не удалось установить программы (apt-get install)."
    sleep 30
  done
  ok "Flask $(python3 -c 'import importlib.metadata as m; print(m.version("flask"))' 2>/dev/null), gunicorn $(gunicorn --version 2>/dev/null | awk '{print $NF}' | tr -d '()')"
}

step_code() {
  step "Код CRM из GitHub (ветка $REPO_BRANCH)"
  install -d -m 755 "$BASE"
  if [[ -d $SRC/.git ]]; then
    run git -C "$SRC" fetch --depth 1 origin "$REPO_BRANCH" || die "не удалось скачать код CRM из GitHub"
    run git -C "$SRC" reset --hard FETCH_HEAD
    run git -C "$SRC" clean -fdq
  else
    rm -rf "$SRC"
    run git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$SRC" || die "не удалось скачать код CRM из GitHub"
  fi
  [[ -f $APP/app.py ]] || die "в ветке $REPO_BRANCH нет папки crm"
  chown -R root:root "$SRC"; chmod -R a+rX,go-w "$SRC"
  find "$APP" -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  ok "версия $(git -C "$SRC" rev-parse --short HEAD) → $APP"
  if (cd "$APP" && runuser -u "$APP_USER" -- env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -q test_crm >>"$DETAIL_LOG" 2>&1); then
    ok "проверки кода прошли (тесты CRM)"
  else
    warn "тесты CRM не прошли — подробности в $DETAIL_LOG (CRM всё равно ставлю)"
  fi
}

step_config() {
  step "Настройки, база и пользователи"
  install -d -m 755 -o "$APP_USER" -g "$APP_USER" "$STATE_DIR"
  install -d -m 755 "$CRM_STATE" "$CRM_STATE/acme" /etc/prostranstvo
  if [[ ! -s $SECRET_FILE ]]; then
    head -c 48 /dev/urandom | base64 -w0 >"$SECRET_FILE"
  fi
  chown "root:$APP_USER" "$SECRET_FILE"; chmod 640 "$SECRET_FILE"
  local leads=0 notify=""
  if [[ -f $ENV_FILE ]]; then
    leads=$(sed -n 's/^SITE_LEADS=\([01]\)$/\1/p' "$ENV_FILE" | tail -n1); leads=${leads:-0}
  fi
  if grep -q "^zakaz@$DOMAIN:" /etc/dovecot/pochta-users 2>/dev/null; then notify="zakaz@$DOMAIN"; fi
  put_file "$ENV_FILE" 600 <<EOF
# Создано setup-crm.sh. SITE_LEADS меняется командой: prostranstvo-crm site-leads on|off
CRM_DB=$CRM_DB
BOT_DB=$BOT_DB
CATALOG_FILE=$CATALOG_FILE
CRM_SECRET_FILE=$SECRET_FILE
SITE_ORIGINS=https://$DOMAIN,https://www.$DOMAIN
SITE_LEADS=$leads
NOTIFY_EMAIL=$notify
COOKIE_SECURE=1
SHOP_DOMAIN=$DOMAIN
PYTHONDONTWRITEBYTECODE=1
EOF
  manage init >>"$DETAIL_LOG" 2>&1 || die "не удалось создать базу CRM — см. $DETAIL_LOG"
  touch "$PASS_FILE"; chmod 600 "$PASS_FILE"
  local u login name role pw res created=()
  for u in "${DEFAULT_USERS[@]}"; do
    IFS='|' read -r login name role <<<"$u"
    pw=$(gen_pw)
    res=$(printf '%s\n' "$pw" | manage ensure-user "$login" "$name" "$role" 2>>"$DETAIL_LOG") || die "не удалось создать пользователя $login"
    if [[ $res == created ]]; then
      awk -v l="$login" '$1 != l' "$PASS_FILE" >"$PASS_FILE.tmp"; printf '%s %s\n' "$login" "$pw" >>"$PASS_FILE.tmp"
      install -m 600 "$PASS_FILE.tmp" "$PASS_FILE"; rm -f "$PASS_FILE.tmp"
      created+=("$login")
    fi
  done
  ok "база: $CRM_DB; пользователи: $(manage users 2>/dev/null | awk '{print $1}' | paste -sd' ')${created[*]:+ (новые: ${created[*]})}"
  ok "заявки с сайта: $([[ $leads == 1 ]] && echo включены || echo 'выключены (до уведомления в Роскомнадзор)'); письмо о заявке: ${notify:-нет почты на сервере}"
}

write_helper() {
  put_file "$HELPER" 755 <<'PRS_CRM'
#!/bin/bash
# prostranstvo-crm — CRM сервера «Наш декор». Создано setup-crm.sh — руками не править.
set -Eeuo pipefail
# shellcheck source=/dev/null
. /usr/local/lib/prostranstvo/common.sh
if [[ $(id -u) -ne 0 ]]; then echo "Запустите от root." >&2; exit 1; fi
CRM_HOST="crm.$DOMAIN"
ENV_FILE=/etc/prostranstvo/crm.env
PASS_FILE=/etc/prostranstvo/crm-paroli.txt
APP=/opt/prostranstvo-crm/src/crm
STATE=/var/lib/prostranstvo-crm
TLS_DIR=/etc/prostranstvo/crm-tls
CERT_LOG=/var/log/prostranstvo-crm-cert.log
BACKUP_DIR=/var/backups/prostranstvo
# shellcheck source=/dev/null
set -a; . "$ENV_FILE"; set +a

manage() { runuser -u prostranstvo -- env CRM_DB="$CRM_DB" BOT_DB="$BOT_DB" CATALOG_FILE="$CATALOG_FILE" python3 "$APP/manage.py" "$@"; }
gen_pw() { local s=""; while ((${#s} < 14)); do s+=$(head -c 96 /dev/urandom | LC_ALL=C tr -dc 'A-HJ-NP-Za-km-z2-9'); done; printf '%s\n' "${s:0:14}"; }
save_pw() {
  touch "$PASS_FILE"; chmod 600 "$PASS_FILE"
  awk -v l="$1" '$1 != l' "$PASS_FILE" >"$PASS_FILE.tmp"; printf '%s %s\n' "$1" "$2" >>"$PASS_FILE.tmp"
  install -m 600 "$PASS_FILE.tmp" "$PASS_FILE"; rm -f "$PASS_FILE.tmp"
}

le_cert_ok() {
  local c=/etc/letsencrypt/live/$CRM_HOST/fullchain.pem
  [[ -s $c ]] && openssl x509 -checkend 86400 -noout -in "$c" >/dev/null 2>&1
}
use_cert() {
  local c k
  if [[ $1 == le ]]; then c=/etc/letsencrypt/live/$CRM_HOST/fullchain.pem; k=/etc/letsencrypt/live/$CRM_HOST/privkey.pem
  else c=/etc/ssl/certs/ssl-cert-snakeoil.pem; k=/etc/ssl/private/ssl-cert-snakeoil.key; fi
  install -d -m 755 "$TLS_DIR"
  [[ $(readlink "$TLS_DIR/fullchain.pem" 2>/dev/null) == "$c" ]] && return 1
  ln -sfn "$c" "$TLS_DIR/fullchain.pem"; ln -sfn "$k" "$TLS_DIR/privkey.pem"
  return 0
}
cmd_cert() {
  local auto=no ip recs rc=0 out last
  [[ ${1:-} == --auto ]] && auto=yes
  if le_cert_ok; then
    if use_cert le; then systemctl reload nginx >/dev/null 2>&1 || true; fi
    [[ $auto == yes ]] || echo "Сертификат для $CRM_HOST есть, продлевается сам."
    return 0
  fi
  [[ -e $TLS_DIR/fullchain.pem ]] || { use_cert snakeoil || true; }
  ip=$(server_ip); recs=$(dns_lookup A "$CRM_HOST" | sort -u | paste -sd' ')
  if [[ $auto == yes ]]; then
    [[ -n $ip && $recs == "$ip" ]] || return 0
    last=$(cat "$STATE/cert-last-fail" 2>/dev/null) || last=0
    [[ $last =~ ^[0-9]+$ ]] || last=0
    (($(date +%s) - last >= 3600)) || return 0
  elif [[ -z $ip || $recs != "$ip" ]]; then
    echo "$CRM_HOST пока указывает на «${recs:-никуда}», а сервер — $ip. Сертификат сервер получит сам, когда домен заработает."
    return 2
  fi
  local args=(certonly --webroot -w "$STATE/acme" -d "$CRM_HOST" --cert-name "$CRM_HOST" --non-interactive --agree-tos --keep-until-expiring)
  if [[ -n ${EMAIL:-} ]]; then args+=(--email "$EMAIL" --no-eff-email); else args+=(--register-unsafely-without-email); fi
  out=$(certbot "${args[@]}" 2>&1) || rc=$?
  printf '%s %s\n%s\n' "$(ts)" "certbot rc=$rc" "$out" >>"$CERT_LOG"
  if ((rc == 0)) && le_cert_ok; then
    rm -f "$STATE/cert-last-fail"; use_cert le || true; systemctl reload nginx >/dev/null 2>&1 || true
    [[ $auto == yes ]] || echo "ГОТОВО: сертификат для $CRM_HOST получен."
    return 0
  fi
  date +%s >"$STATE/cert-last-fail"
  [[ $auto == yes ]] || { echo "Сертификат не получен (код $rc):"; printf '%s\n' "$out" | tail -n 6 | sed 's/^/   | /'; }
  return 1
}

cmd_status() {
  local code
  echo "CRM $DOMAIN — проверка ($(date '+%d.%m.%Y %H:%M'))"
  if systemctl is-active --quiet prostranstvo-crm; then echo "   [да]  служба prostranstvo-crm работает"; else echo "   [НЕТ] служба prostranstvo-crm — journalctl -u prostranstvo-crm -n 50"; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:${PORT:-8081}/api/health" 2>/dev/null) || code=000
  if [[ $code == 200 ]]; then echo "   [да]  приложение отвечает"; else echo "   [НЕТ] приложение отвечает (код $code)"; fi
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 --resolve "$CRM_HOST:443:127.0.0.1" "https://$CRM_HOST/login" 2>/dev/null) || code=000
  if [[ $code == 200 ]]; then echo "   [да]  https://$CRM_HOST/login через nginx"; else echo "   [НЕТ] https://$CRM_HOST через nginx (код $code)"; fi
  if le_cert_ok; then echo "   [да]  сертификат Let's Encrypt"; else echo "   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)"; fi
  echo "   заявки с сайта: $([[ ${SITE_LEADS:-0} == 1 ]] && echo включены || echo выключены)"
  echo "   $(manage stats 2>/dev/null || echo 'база: ошибка')"
  echo "   последняя копия: $(ls -1d "$BACKUP_DIR"/20* 2>/dev/null | tail -n1 || true)"
}

cmd_passwords() {
  [[ -s $PASS_FILE ]] || { echo "Паролей в файле нет (их меняли в CRM или командой passwd)."; return 0; }
  echo "=================================================================="
  echo " ПАРОЛИ CRM — не фотографируйте и никому не пересылайте."
  echo " Вход: https://$CRM_HOST . Пароль можно сменить в CRM: Ещё → Настройки."
  echo "=================================================================="
  awk '{printf "  %-12s %s\n", $1, $2}' "$PASS_FILE"
}

cmd_passwd() {
  local login=${1:-} pw pw2
  [[ -n $login ]] || { echo "Нужно: prostranstvo-crm passwd ЛОГИН" >&2; return 1; }
  if [[ -t 0 ]]; then
    read -r -s -p "Новый пароль для $login (Enter — придумать): " pw; echo
    if [[ -n $pw ]]; then read -r -s -p "Ещё раз: " pw2; echo; [[ $pw == "$pw2" ]] || { echo "Не совпали." >&2; return 1; }; fi
  else pw=""; fi
  [[ -n $pw ]] || pw=$(gen_pw)
  ((${#pw} >= 10)) || { echo "Пароль — от 10 символов." >&2; return 1; }
  printf '%s\n' "$pw" | manage passwd "$login" >/dev/null
  save_pw "$login" "$pw"
  echo "Пароль $login изменён (вход на всех устройствах сброшен). Посмотреть: prostranstvo-crm passwords"
}

cmd_add_user() {
  local login=${1:-} name=${2:-} role=${3:-staff} pw res
  [[ -n $login && -n $name ]] || { echo "Нужно: prostranstvo-crm add-user ЛОГИН \"Имя\" [admin|staff]" >&2; return 1; }
  pw=$(gen_pw)
  res=$(printf '%s\n' "$pw" | manage ensure-user "$login" "$name" "$role")
  if [[ $res == created ]]; then save_pw "$login" "$pw"; echo "Создан $login. Пароль: prostranstvo-crm passwords"; else echo "Пользователь $login уже есть."; fi
}

cmd_site_leads() {
  local v
  case ${1:-} in on) v=1 ;; off) v=0 ;; *) echo "Нужно: prostranstvo-crm site-leads on|off" >&2; return 1 ;; esac
  sed -i "s/^SITE_LEADS=.*/SITE_LEADS=$v/" "$ENV_FILE"
  systemctl restart prostranstvo-crm
  echo "Заявки с сайта: $([[ $v == 1 ]] && echo включены || echo выключены)."
}

cmd_backup() {
  local d f keep=14
  d="$BACKUP_DIR/$(date +%F)"
  install -d -m 700 "$BACKUP_DIR" "$d"
  local tmp=/var/lib/prostranstvo/.crm-backup.tmp ok=yes
  rm -f "$tmp"
  if manage backup "$tmp" >/dev/null 2>&1 && [[ -s $tmp ]]; then
    mv -f "$tmp" "$d/crm.db"
  else
    ok=no; rm -f "$tmp"; echo "копия базы CRM не получилась" >&2
  fi
  if [[ -f ${BOT_DB:-/var/lib/prostranstvo/bot.db} ]]; then
    sqlite3 "$BOT_DB" ".backup '$d/bot.db'" 2>/dev/null || cp -a "$BOT_DB" "$d/bot.db" || ok=no
  fi
  for f in /etc/prostranstvo/*.env /etc/prostranstvo/*.conf; do [[ -f $f ]] && cp -a "$f" "$d/"; done
  chmod -R go-rwx "$d"
  find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +$keep -exec rm -rf {} + 2>/dev/null || true
  logger -t prostranstvo-backup "копия баз: $d ($ok)" 2>/dev/null || true
  if [[ -t 1 ]]; then echo "Копия: $d"; fi
  [[ $ok == yes ]]
}

cmd_update() {
  curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/setup-crm.sh | bash
}

usage() {
  cat <<EOF
prostranstvo-crm — CRM https://$CRM_HOST
  prostranstvo-crm                      — проверка
  prostranstvo-crm passwords            — пароли входа (НЕ фотографировать!)
  prostranstvo-crm passwd ЛОГИН         — сменить пароль
  prostranstvo-crm add-user ЛОГИН "Имя" [admin|staff]
  prostranstvo-crm site-leads on|off    — заявки с формы сайта (включать после уведомления РКН)
  prostranstvo-crm backup               — копия баз сейчас (ночью делается сама)
  prostranstvo-crm update               — обновить CRM из GitHub
  prostranstvo-crm cert                 — получить сертификат для $CRM_HOST сейчас
EOF
}

rc=0
case ${1:-status} in
  status) cmd_status ;;
  passwords) cmd_passwords ;;
  passwd) shift; cmd_passwd "$@" || rc=$? ;;
  add-user) shift; cmd_add_user "$@" || rc=$? ;;
  site-leads) shift; cmd_site_leads "$@" || rc=$? ;;
  backup) cmd_backup || rc=$? ;;
  update) cmd_update ;;
  cert) shift; cmd_cert "$@" || rc=$? ;;
  -h | --help | help) usage ;;
  *) usage; rc=1 ;;
esac
exit "$rc"
PRS_CRM
  ok "служебная команда: prostranstvo-crm (help — список)"
}

step_service() {
  step "Служба prostranstvo-crm"
  put_file /etc/systemd/system/prostranstvo-crm.service 644 <<EOF
# Создано setup-crm.sh
[Unit]
Description=CRM магазина «Наш декор»
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
EnvironmentFile=$ENV_FILE
WorkingDirectory=$APP
ExecStart=/usr/bin/gunicorn --workers 1 --threads 8 --bind 127.0.0.1:$PORT --timeout 60 --graceful-timeout 20 app:app
Restart=always
RestartSec=3
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$STATE_DIR
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
LockPersonality=yes
UMask=0077

[Install]
WantedBy=multi-user.target
EOF
  run systemctl daemon-reload
  run systemctl enable prostranstvo-crm
  run systemctl restart prostranstvo-crm || die "служба CRM не запустилась — journalctl -u prostranstvo-crm -n 50"
  local n code=000
  for n in $(seq 1 20); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/api/health" 2>/dev/null) || code=000
    [[ $code == 200 ]] && break
    sleep 1
  done
  [[ $code == 200 ]] || { journalctl -u prostranstvo-crm -n 30 --no-pager >>"$DETAIL_LOG" 2>&1 || true; die "CRM не отвечает (код $code) — см. $DETAIL_LOG"; }
  ok "CRM работает на 127.0.0.1:$PORT (gunicorn, пользователь $APP_USER)"
}

step_nginx() {
  step "nginx: https://$CRM_HOST и сертификат"
  "$HELPER" help >/dev/null
  [[ -s /etc/ssl/certs/ssl-cert-snakeoil.pem ]] || run make-ssl-cert generate-default-snakeoil --force-overwrite || true
  install -d -m 755 "$TLS_DIR"
  if [[ ! -e $TLS_DIR/fullchain.pem ]]; then
    ln -sfn /etc/ssl/certs/ssl-cert-snakeoil.pem "$TLS_DIR/fullchain.pem"
    ln -sfn /etc/ssl/private/ssl-cert-snakeoil.key "$TLS_DIR/privkey.pem"
  fi
  local l6=no h2l="" h2="" ver site=/etc/nginx/sites-available/prostranstvo-crm.conf link=/etc/nginx/sites-enabled/prostranstvo-crm.conf bak="" tmp
  [[ -e /proc/net/if_inet6 ]] && l6=yes
  ver=$(nginx -v 2>&1 | sed -n 's#^.*nginx/\([0-9][0-9.]*\).*$#\1#p') || ver=""
  if dpkg --compare-versions "${ver:-0}" ge 1.25.1; then h2="    http2 on;"; else h2l=" http2"; fi
  tmp=$(mktemp)
  {
    echo "# CRM $CRM_HOST. Создано setup-crm.sh — руками не править."
    echo "server {"
    echo "    listen 80;"
    [[ $l6 == yes ]] && echo "    listen [::]:80;"
    echo "    server_name $CRM_HOST;"
    echo "    location ^~ /.well-known/acme-challenge/ { root $CRM_STATE/acme; default_type text/plain; }"
    echo "    location / { return 301 https://$CRM_HOST\$request_uri; }"
    echo "}"
    echo "server {"
    echo "    listen 443 ssl$h2l;"
    [[ $l6 == yes ]] && echo "    listen [::]:443 ssl$h2l;"
    [[ -n $h2 ]] && echo "$h2"
    echo "    server_name $CRM_HOST;"
    echo "    ssl_certificate     $TLS_DIR/fullchain.pem;"
    echo "    ssl_certificate_key $TLS_DIR/privkey.pem;"
    echo "    ssl_protocols TLSv1.2 TLSv1.3;"
    echo "    server_tokens off;"
    echo "    client_max_body_size 1m;"
    echo "    add_header Strict-Transport-Security \"max-age=15552000\" always;"
    echo "    location / {"
    echo "        proxy_pass http://127.0.0.1:$PORT;"
    echo "        proxy_set_header Host \$host;"
    echo "        proxy_set_header X-Forwarded-For \$remote_addr;"
    echo "        proxy_set_header X-Forwarded-Proto \$scheme;"
    echo "        proxy_set_header X-Forwarded-Host \$host;"
    echo "        proxy_read_timeout 60s;"
    echo "    }"
    echo "}"
  } >"$tmp"
  if [[ -f $site ]]; then bak=$(mktemp); cp -a "$site" "$bak"; fi
  install -m 644 "$tmp" "$site"; rm -f "$tmp"
  ln -sfn "$site" "$link"
  if ! out=$(nginx -t 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    if [[ -n $bak ]]; then cp -a "$bak" "$site"; else rm -f "$site" "$link"; fi
    die "nginx не принял настройки CRM (сайт не затронут): $(grep -m1 emerg <<<"$out")"
  fi
  [[ -n $bak ]] && rm -f "$bak"
  run systemctl reload nginx || run systemctl restart nginx
  ok "nginx: $CRM_HOST → CRM"
  put_file /etc/cron.d/prostranstvo-crm 644 <<'EOF'
# Создано setup-crm.sh: сертификат для crm.ДОМЕН, когда домен заработает; ночные копии баз в 03:15.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
7,22,37,52 * * * *  root  /usr/local/sbin/prostranstvo-crm cert --auto 2>&1 | logger -t prostranstvo-crm
15 3 * * *          root  /usr/local/sbin/prostranstvo-crm backup 2>&1 | logger -t prostranstvo-backup
EOF
  local rc=0
  "$HELPER" cert 2>&1 | sed 's/^/     /' || rc=${PIPESTATUS[0]}
  ((rc == 2)) && info "пока временный сертификат — браузер предупредит; настоящий будет в течение часа после запуска домена."
  return 0
}

step_protect() {
  step "Защита входа (fail2ban) и ночные копии"
  put_file /etc/fail2ban/filter.d/prostranstvo-crm.conf 644 <<'EOF'
# Создано setup-crm.sh: неудачные входы в CRM.
[Definition]
failregex = crm login (?:failed|blocked) login=\S* ip=<HOST>$
ignoreregex =
journalmatch = _SYSTEMD_UNIT=prostranstvo-crm.service
EOF
  put_file /etc/fail2ban/jail.d/prostranstvo-crm.local 644 <<'EOF'
# Создано setup-crm.sh: 8 неверных паролей за 10 минут — адрес блокируется на 1 час.
[prostranstvo-crm]
enabled  = true
backend  = systemd
filter   = prostranstvo-crm
port     = http,https
maxretry = 8
findtime = 10m
bantime  = 1h
EOF
  if ! out=$(fail2ban-client -t 2>&1); then
    printf '%s\n' "$out" >>"$DETAIL_LOG"
    rm -f /etc/fail2ban/jail.d/prostranstvo-crm.local
    warn "fail2ban не принял защиту CRM — убрал её (защита SSH как раньше)"
  fi
  if run systemctl restart fail2ban; then
    sleep 2; ok "fail2ban: $(fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:[[:space:]]*//p')"
  else
    warn "fail2ban не перезапустился — см. journalctl -u fail2ban"
  fi
  "$HELPER" backup >>"$DETAIL_LOG" 2>&1 || warn "первая копия баз не сделалась — см. $DETAIL_LOG"
  ok "копии баз — каждую ночь в 03:15 в $BACKUP_DIR (14 дней)"
}

check() { if [[ $2 == "$3" ]]; then printf '   [да]  %s\n' "$1"; else printf '   [НЕТ] %s (%s)\n' "$1" "$2"; FAILS=$((FAILS + 1)); fi; }

step_selftest() {
  step "Самопроверка"
  local code body
  if systemctl is-active --quiet prostranstvo-crm; then check "служба работает" да да; else check "служба работает" нет да; fi
  code=$(curl -sk -o /tmp/crm-st.html -w '%{http_code}' --max-time 10 --resolve "$CRM_HOST:443:127.0.0.1" "https://$CRM_HOST/login" 2>/dev/null) || code=000
  if [[ $code == 200 ]] && grep -q 'name="password"' /tmp/crm-st.html; then check "страница входа https://$CRM_HOST" да да; else check "страница входа https://$CRM_HOST" "код $code" да; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 --resolve "$CRM_HOST:80:127.0.0.1" "http://$CRM_HOST/" 2>/dev/null) || code=000
  check "http → https" "$code" 301
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 10 --resolve "$CRM_HOST:443:127.0.0.1" "https://$CRM_HOST/" 2>/dev/null) || code=000
  check "без входа данные закрыты" "$code" 302
  body=$(curl -sk --max-time 10 --resolve "$CRM_HOST:443:127.0.0.1" -X POST -H 'Content-Type: application/json' \
    -H 'Origin: https://evil.example' -d '{}' "https://$CRM_HOST/api/lead" 2>/dev/null) || body=""
  if [[ $body == *origin* ]]; then check "чужие сайты не могут слать заявки" да да; else check "чужие сайты не могут слать заявки" "${body:0:40}" да; fi
  code=$(ss -Htln "sport = :$PORT" | awk '{print $4}' | head -n1)
  if [[ $code == 127.0.0.1:* ]]; then check "приложение снаружи напрямую не видно" да да; else check "приложение снаружи напрямую не видно" "$code" да; fi
  rm -f /tmp/crm-st.html
  if ((FAILS == 0)); then ok "всё работает"; else warn "самопроверка: не прошло — $FAILS"; fi
}

summary() {
  printf '\n==================================================================\n'
  if ((${#WARNINGS[@]})); then printf ' CRM УСТАНОВЛЕНА, но есть замечания:\n'; for w in "${WARNINGS[@]}"; do printf '   ! %s\n' "$w"; done
  else printf ' CRM УСТАНОВЛЕНА\n'; fi
  printf '==================================================================\n'
  printf ' Адрес: https://%s\n' "$CRM_HOST"
  printf ' Логины: %s\n' "$(manage users 2>/dev/null | awk '{print $1}' | paste -sd' ')"
  printf ' Пароли — только на сервере. Показать (не фотографировать!):\n     prostranstvo-crm passwords\n'
  printf ' Проверка: prostranstvo-crm      Все команды: prostranstvo-crm help\n'
  printf ' Журнал установки: %s\n' "$SETUP_LOG"
  printf '==================================================================\n'
}

main() {
  trap '' HUP
  exec </dev/null
  case ${1:-} in -h | --help) sed -n '2,18p' "$0" 2>/dev/null || true; exit 0 ;; esac
  install -d -m 755 /var/log
  touch "$SETUP_LOG" "$DETAIL_LOG"; chmod 640 "$SETUP_LOG" "$DETAIL_LOG"
  exec > >(tee --output-error=warn -a "$SETUP_LOG") 2>&1
  TEE_PID=$!
  trap on_exit EXIT
  trap 'on_err $? $LINENO' ERR
  printf '\n=== CRM для сервера «Наш декор» — %s ===\n' "$(date '+%d.%m.%Y %H:%M')"
  printf '\n=== %s: запуск ===\n' "$(date '+%F %T')" >>"$DETAIL_LOG"
  exec 9>/run/prostranstvo-crm-setup.lock
  flock -n 9 || die "установка CRM уже идёт в другом окне."
  check_all
  info "домен: $DOMAIN, CRM: https://$CRM_HOST"
  step_packages
  step_code
  step_config
  write_helper
  step_service
  step_nginx
  step_protect
  step_selftest
  summary
}

main "$@"
