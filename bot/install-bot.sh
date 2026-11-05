#!/usr/bin/env bash
# =============================================================================
#  install-bot.sh — установка и обновление бота магазина «Наш декор» в Telegram и MAX
#  (Selectel, Ubuntu 24.04; сервер, настроенный setup-prostranstvo.sh). От root:
#
#  Установка (токены необязательны и независимы — можно один из двух):
#    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/bot/install-bot.sh | bash -s -- --tg 'ТОКЕН_TELEGRAM' --max 'ТОКЕН_MAX'
#  Старый вызов с одним токеном — это Telegram:   … | bash -s -- 'ТОКЕН_TELEGRAM'
#
#  Обновить код бота (токены, настройки и база заявок НЕ трогаются):
#    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/bot/install-bot.sh | bash
#
#  Параметры:  --tg ТОКЕН | --max ТОКЕН   токен бота (вместо токена «-» — отключить этот мессенджер)
#              --tg-contacts 0|1          Telegram: принимать заявки с телефоном (по умолчанию 0)
#              --new-code                 новый одноразовый код для /owner
#              --site-url АДРЕС           адрес сайта для ссылок в боте («-» — без ссылок)
#              --force                    ставить, даже если это не сервер сайта «Наш декор»
#
#  Что делает: python3-venv, пользователь prostranstvo, код бота из GitHub (ветка server,
#  папка bot) → /opt/prostranstvo-bot, venv + pip, /etc/prostranstvo/bot.env (chmod 600),
#  службы systemd prostranstvo-bot (Telegram) и prostranstvo-max (MAX) — независимые.
#  Токены никогда не печатаются и не пишутся в журнал.
#  Секретов в скрипте нет и быть не должно — репозиторий открытый.
# =============================================================================
set -euo pipefail
export LC_ALL=C.UTF-8

REPO_URL=${PROSTRANSTVO_BOT_REPO:-https://github.com/mikhailusenko88-hub/Mikhail.git}
REPO_BRANCH=${PROSTRANSTVO_BOT_BRANCH:-server}
RAW_INSTALL_URL="https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/bot/install-bot.sh"
BOT_SUBDIR=bot
BOT_USER=prostranstvo
BASE_DIR=/opt/prostranstvo-bot
SRC_DIR=$BASE_DIR/src
APP_DIR=$BASE_DIR/app
VENV_DIR=$BASE_DIR/venv
CONF_DIR=/etc/prostranstvo
ENV_FILE=$CONF_DIR/bot.env
SITE_CONF=$CONF_DIR/prostranstvo.conf
STATE_DIR=/var/lib/prostranstvo
DB_FILE=$STATE_DIR/bot.db
SYSTEMD_DIR=/etc/systemd/system
SVC_TG=prostranstvo-bot
SVC_MAX=prostranstvo-max
MAX_API_DEFAULT=https://platform-api2.max.ru
LOG_FILE=/var/log/prostranstvo-bot-install.log
TOTAL_STEPS=6
TG_TOKEN_RE='^[0-9]{5,15}:[A-Za-z0-9_-]{30,64}$'
MAX_TOKEN_RE='^[A-Za-z0-9._~+/=:-]{16,512}$'
SITE_URL_RE='^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?$'

STEP=0
ARG_TG=""
ARG_TG_SET=no
ARG_MAX=""
ARG_MAX_SET=no
ARG_CONTACTS=""
ARG_SITE_URL=""
ARG_SITE_URL_SET=no
NEW_CODE=no
FORCE=no
WARNINGS=()
TG_NAME=""
MAX_LINK=""
OWNER_CODE=""
SITE_URL=""
TG_ON=no
MAX_ON=no
TG_RUNNING=no
MAX_RUNNING=no

# --- вывод ---------------------------------------------------------------------
step() { STEP=$((STEP + 1)); printf '\n[%d/%d] %s\n' "$STEP" "$TOTAL_STEPS" "$*"; }
ok() { printf '   + %s\n' "$*"; }
info() { printf '     %s\n' "$*"; }
warn() { printf '   ! ВНИМАНИЕ: %s\n' "$*"; WARNINGS+=("$*"); }
die() {
  printf '\nОШИБКА: %s\n' "$*" >&2
  printf 'Исправьте причину и запустите ту же команду ещё раз — повторный запуск безопасен.\n' >&2
  if [[ -s $LOG_FILE ]]; then printf 'Подробный журнал: %s\n' "$LOG_FILE" >&2; fi
  exit 1
}

# Выполнить команду «тихо»: вывод — в журнал, на экран — только при ошибке.
run() {
  local rc=0
  printf '\n### %s  $ %s\n' "$(date '+%F %T')" "$*" >>"$LOG_FILE"
  "$@" >>"$LOG_FILE" 2>&1 || rc=$?
  if ((rc != 0)); then
    printf '   Команда не выполнилась (код %s): %s\n' "$rc" "$*"
    tail -n 10 "$LOG_FILE" | sed 's/^/   | /'
  fi
  return "$rc"
}

usage() {
  cat <<EOF
Установка бота «Наш декор» (от root), токены — от @BotFather (Telegram) и с платформы MAX:
  curl -fsSL $RAW_INSTALL_URL | bash -s -- --tg 'ТОКЕН_TELEGRAM' --max 'ТОКЕН_MAX'
Можно только один из токенов. Обновление (токены и база сохраняются):
  curl -fsSL $RAW_INSTALL_URL | bash
Параметры: --tg ТОКЕН|- | --max ТОКЕН|- | --tg-contacts 0|1 | --new-code | --site-url АДРЕС|- | --force
EOF
}

parse_args() {
  local pos=() key val
  while (($#)); do
    case $1 in
      -h | --help) usage; exit 0 ;;
      --new-code) NEW_CODE=yes ;;
      --force) FORCE=yes ;;
      --tg=* | --max=* | --site-url=* | --tg-contacts=*)
        key=${1%%=*}; val=${1#*=}; set -- "$key" "$val" "${@:2}"; continue ;;
      --tg | --max | --site-url | --tg-contacts)
        (($# >= 2)) || die "после $1 укажите значение (см. --help)"
        val=${2//[[:space:]]/}
        case $1 in
          --tg) ARG_TG=$val; ARG_TG_SET=yes ;;
          --max) ARG_MAX=$val; ARG_MAX_SET=yes ;;
          --site-url) ARG_SITE_URL=$val; ARG_SITE_URL_SET=yes ;;
          --tg-contacts) ARG_CONTACTS=$val ;;
        esac
        shift ;;
      --*) die "неизвестный параметр: $1 (см. --help)" ;;
      *) pos+=("$1") ;;
    esac
    shift
  done
  ((${#pos[@]} <= 1)) || die "лишние параметры. Токены передавайте так: --tg 'ТОКЕН' --max 'ТОКЕН'"
  if ((${#pos[@]} == 1)); then
    [[ $ARG_TG_SET == no ]] || die "токен Telegram указан дважды"
    ARG_TG=${pos[0]//[[:space:]]/}; ARG_TG_SET=yes   # старый вызов: один токен — Telegram
  fi
  if [[ $ARG_TG_SET == yes && $ARG_TG != - && ! $ARG_TG =~ $TG_TOKEN_RE ]]; then
    die "это не похоже на токен Telegram (вид: 1234567890:AA…). Скопируйте токен из @BotFather целиком."
  fi
  if [[ $ARG_MAX_SET == yes && $ARG_MAX != - && ! $ARG_MAX =~ $MAX_TOKEN_RE ]]; then
    die "это не похоже на токен MAX. Скопируйте его на платформе MAX: Чат-боты → ⋮ → Настройки."
  fi
  if [[ -n $ARG_CONTACTS && $ARG_CONTACTS != 0 && $ARG_CONTACTS != 1 ]]; then
    die "--tg-contacts: 0 (заявки только на сайте и в MAX) или 1 (принимать и в Telegram)"
  fi
}

check_root_and_os() {
  [[ $(id -u) -eq 0 ]] || die "запустите от root (пользователь root на сервере)."
  [[ -r /etc/os-release ]] || die "не найден /etc/os-release — это не Ubuntu."
  local id ver
  # shellcheck source=/dev/null
  id=$(. /etc/os-release && printf '%s' "${ID:-}")
  # shellcheck source=/dev/null
  ver=$(. /etc/os-release && printf '%s' "${VERSION_ID:-}")
  [[ $id == ubuntu ]] || die "нужна Ubuntu, а здесь «$id»."
  if [[ $ver != 24.04 ]]; then warn "скрипт рассчитан на Ubuntu 24.04, здесь $ver — продолжаю"; fi
  command -v systemctl >/dev/null 2>&1 || die "нет systemd (systemctl)."
}

# Бот хранит данные клиентов — по закону они должны лежать на сервере в России.
# Защита от запуска «не на том» сервере (например, на старом сервере в Казахстане).
check_server() {
  [[ $FORCE == yes || -f $SITE_CONF || -f $ENV_FILE ]] && return 0
  printf '\nНа этом сервере нет настроек сайта «Наш декор» (%s).\n' "$SITE_CONF"
  printf 'Похоже, команда запущена не на том сервере. Бот хранит заявки клиентов,\n'
  printf 'поэтому его ставят на сервер Selectel в России, настроенный setup-prostranstvo.sh.\n'
  printf 'НИЧЕГО НЕ ИЗМЕНЕНО. Если сервер точно нужный — добавьте в конец команды: --force\n'
  exit 1
}

# --- bot.env ---------------------------------------------------------------------
# get_env ФАЙЛ КЛЮЧ — значение (последняя строка КЛЮЧ=…), без кавычек по краям
get_env() {
  local file=$1 key=$2 line value=""
  [[ -r $file ]] || return 0
  while IFS= read -r line || [[ -n $line ]]; do
    if [[ $line == "$key="* ]]; then value=${line#*=}; fi
  done <"$file"
  value=${value%$'\r'}
  if [[ $value == \"*\" || $value == \'*\' ]]; then value=${value:1:${#value}-2}; fi
  printf '%s' "$value"
}

has_env() { [[ -r $1 ]] && grep -q "^$2=" "$1"; }

# set_env ФАЙЛ КЛЮЧ ЗНАЧЕНИЕ [КОММЕНТАРИЙ] — заменить строку КЛЮЧ=… (или дописать с комментарием).
# Всё через встроенные команды bash: значения (токены) не попадают в списки процессов.
set_env() {
  local file=$1 key=$2 value=$3 comment=${4:-} tmp line found=no
  [[ $value != *$'\n'* ]] || die "недопустимое значение для $key"
  tmp=$(mktemp "$CONF_DIR/.bot.env.XXXXXX")
  if [[ -f $file ]]; then
    while IFS= read -r line || [[ -n $line ]]; do
      if [[ $line == "$key="* ]]; then
        if [[ $found == no ]]; then printf '%s=%s\n' "$key" "$value"; found=yes; fi
      else
        printf '%s\n' "$line"
      fi
    done <"$file" >"$tmp"
  fi
  if [[ $found == no ]]; then
    if [[ -n $comment ]]; then printf '%s\n' "$comment" >>"$tmp"; fi
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
  fi
  chmod 600 "$tmp"
  chown root:root "$tmp"
  mv -f "$tmp" "$file"
}

# ensure_env ФАЙЛ КЛЮЧ ЗНАЧЕНИЕ КОММЕНТАРИЙ — дописать ключ, только если его ещё нет
ensure_env() { has_env "$1" "$2" || set_env "$1" "$2" "$3" "$4"; }

write_env_template() {
  local tmp
  tmp=$(mktemp "$CONF_DIR/.bot.env.XXXXXX")
  cat >"$tmp" <<'EOF'
# Настройки бота «Наш декор» в Telegram и MAX (создано install-bot.sh).
# СЕКРЕТНО: файл читает только root (chmod 600). Не публиковать и не пересылать.
# После правки:  systemctl restart prostranstvo-bot prostranstvo-max
#
# Токен Telegram от @BotFather (пусто — Telegram-бот выключен). Сменить: установщик с --tg 'ТОКЕН'
BOT_TOKEN=
# Токен MAX (платформа MAX для партнёров → Чат-боты → ⋮ → Настройки). Сменить: установщик с --max 'ТОКЕН'
MAX_TOKEN=
# Ссылка на бота в MAX (заполняется сама): ведём туда клиентов из Telegram за заявкой
MAX_BOT_URL=
# Telegram: принимать заявки с телефоном (1) или вести за ними на сайт и в MAX (0).
# Включать 1 — только после уведомления Роскомнадзора о трансграничной передаче данных.
TELEGRAM_COLLECT_CONTACTS=0
# Куда присылать заявки сотруднику, подключённому в обоих мессенджерах (пока он сам не выбрал): max или tg
STAFF_DEFAULT_CHANNEL=max
# Адрес сайта для ссылок в боте; пусто — ссылки на сайт не показываются
SITE_URL=
# Одноразовый код: кто первым отправит боту /owner КОД (в Telegram или MAX), тот станет менеджером.
# Новый код — запустить установщик с параметром --new-code
OWNER_CODE=
# Версия текста согласия на обработку персональных данных (пишется в каждую заявку)
CONSENT_VERSION=1
# id постоянных менеджеров через запятую (обычно не нужно: есть /owner и /invite)
ADMIN_IDS=
MAX_ADMIN_IDS=
# Оператор персональных данных — для текста согласия, когда SITE_URL пуст (можно не заполнять)
OPERATOR_NAME=
# Заготовка, выключено: черновики ответов через YandexGPT (ключи — только здесь, не в GitHub)
YANDEXGPT_ENABLED=0
YANDEXGPT_API_KEY=
YANDEXGPT_FOLDER_ID=
EOF
  chmod 600 "$tmp"
  chown root:root "$tmp"
  mv -f "$tmp" "$ENV_FILE"
}

# старый bot.env (только Telegram) — дописать новые настройки, ничего не меняя
upgrade_env() {
  ensure_env "$ENV_FILE" MAX_TOKEN "" "# Токен MAX (платформа MAX для партнёров → Чат-боты → ⋮ → Настройки)"
  ensure_env "$ENV_FILE" MAX_BOT_URL "" "# Ссылка на бота в MAX (заполняется сама)"
  ensure_env "$ENV_FILE" TELEGRAM_COLLECT_CONTACTS 0 \
    "# Telegram: принимать заявки с телефоном (1) или вести на сайт и в MAX (0). 1 — после уведомления РКН"
  ensure_env "$ENV_FILE" STAFF_DEFAULT_CHANNEL max "# Куда присылать сотруднику, подключённому в обоих мессенджерах"
  ensure_env "$ENV_FILE" MAX_ADMIN_IDS "" "# id постоянных менеджеров в MAX (обычно не нужно)"
}

new_code() {
  local n
  n=$(od -An -N4 -tu4 /dev/urandom | tr -d '[:space:]')
  printf '%06d' $((n % 900000 + 100000))
}

valid_site_url() { [[ $1 =~ $SITE_URL_RE ]]; }

# Адрес сайта из настроек setup-prostranstvo.sh: https://ДОМЕН, если сертификат уже есть
site_url_from_server() {
  [[ -r $SITE_CONF ]] || return 0
  local url="" domain=""
  # shellcheck source=/dev/null
  url=$(. "$SITE_CONF" && printf '%s' "${SITE_URL:-}") || url=""
  if [[ -n $url ]]; then printf '%s' "${url%/}"; return 0; fi
  # shellcheck source=/dev/null
  domain=$(. "$SITE_CONF" && printf '%s' "${DOMAIN:-}") || domain=""
  [[ -n $domain ]] || return 0
  if [[ -s /etc/letsencrypt/live/$domain/fullchain.pem ]]; then
    printf 'https://%s' "$domain"
  else
    printf 'http://%s' "$domain"
  fi
}

# --- проверка токенов -------------------------------------------------------------
# tg_get_me ТОКЕН — «OK имя» | «BAD» (Telegram не принял токен) | «NET» (нет связи).
# Адрес с токеном передаётся curl через stdin (--config -), а не в командной строке.
tg_get_me() {
  local token=$1 out code body
  out=$(printf 'url = "https://api.telegram.org/bot%s/getMe"\n' "$token" |
    curl -sS --max-time 20 --retry 2 --retry-delay 2 --config - -w '\n%{http_code}' 2>/dev/null) || out=$'\n000'
  code=${out##*$'\n'}
  body=${out%$'\n'*}
  case $code in
    200)
      local name
      name=$(printf '%s' "$body" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["result"].get("username","") if d.get("ok") else "")' 2>/dev/null) || name=""
      if [[ -n $name ]]; then printf 'OK %s' "$name"; else printf 'NET'; fi ;;
    401 | 404) printf 'BAD' ;;
    *) printf 'NET' ;;
  esac
}

# max_get_me ТОКЕН — «OK ник» | «BAD» | «NET». Токен — через переменную окружения (не в аргументах);
# сертификат Минцифры — только для этого запроса (системное хранилище не меняется).
max_get_me() {
  local api
  api=$(get_env "$ENV_FILE" MAX_API_URL)
  MAX_CHECK_TOKEN=$1 MAX_CHECK_API=${api:-$MAX_API_DEFAULT} MAX_CHECK_CA=$APP_DIR/certs/russian_trusted_ca.pem \
    python3 - <<'PY' 2>/dev/null || printf 'NET'
import json, os, ssl, urllib.error, urllib.request
ctx = ssl.create_default_context()
if os.path.isfile(os.environ["MAX_CHECK_CA"]):
    ctx.load_verify_locations(cafile=os.environ["MAX_CHECK_CA"])
req = urllib.request.Request(os.environ["MAX_CHECK_API"].rstrip("/") + "/me",
                             headers={"Authorization": os.environ["MAX_CHECK_TOKEN"]})
try:
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        data = json.load(resp)
    print("OK", data.get("username") or "", end="")
except urllib.error.HTTPError as exc:
    print("BAD" if exc.code in (401, 403) else "NET", end="")
except Exception:
    print("NET", end="")
PY
}

# =============================================================================
step_packages() {
  step "Программы: python3-venv, git"
  local need=() p
  for p in python3 python3-venv git ca-certificates curl; do
    # shellcheck disable=SC2016 # ${Status} — формат dpkg-query, а не переменная bash
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || need+=("$p")
  done
  if ! python3 -c 'import ensurepip, venv' >/dev/null 2>&1; then need+=(python3-venv); fi
  if ((${#need[@]})); then
    export DEBIAN_FRONTEND=noninteractive NEEDRESTART_SUSPEND=1 NEEDRESTART_MODE=l
    local apt=(apt-get -y -q -o DPkg::Lock::Timeout=600)
    local n
    for n in 1 2 3; do
      if run "${apt[@]}" update && run "${apt[@]}" install --no-install-recommends "${need[@]}"; then break; fi
      ((n < 3)) || die "не удалось установить: ${need[*]} (apt-get)."
      info "повторяю через 20 секунд…"; sleep 20
    done
    ok "установлено: ${need[*]}"
  else
    ok "всё нужное уже установлено"
  fi
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' ||
    die "нужен Python 3.10 или новее, здесь $(python3 -V 2>&1)"
  ok "$(python3 -V 2>&1)"
}

step_user() {
  step "Пользователь $BOT_USER и папки"
  if ! id -u "$BOT_USER" >/dev/null 2>&1; then
    run useradd --system --user-group --home-dir "$STATE_DIR" --no-create-home --shell /usr/sbin/nologin "$BOT_USER" ||
      die "не удалось создать пользователя $BOT_USER"
    ok "создан пользователь $BOT_USER"
  else
    ok "пользователь $BOT_USER уже есть"
  fi
  if [[ ! -d $STATE_DIR ]]; then
    install -d -o "$BOT_USER" -g "$BOT_USER" -m 750 "$STATE_DIR"
  else
    chown "$BOT_USER:$BOT_USER" "$STATE_DIR"
  fi
  install -d -o root -g root -m 755 "$CONF_DIR" "$BASE_DIR"
  ok "база заявок: $DB_FILE (только на этом сервере)"
}

step_code() {
  step "Код бота из GitHub (ветка $REPO_BRANCH, папка $BOT_SUBDIR)"
  export GIT_TERMINAL_PROMPT=0
  local n fetched=no
  for n in 1 2 3; do
    if [[ -d $SRC_DIR/.git ]]; then
      if run git -C "$SRC_DIR" remote set-url origin "$REPO_URL" &&
        run timeout 180 git -C "$SRC_DIR" fetch --quiet --depth 1 --no-tags origin "+refs/heads/$REPO_BRANCH:refs/remotes/origin/$REPO_BRANCH" &&
        run git -C "$SRC_DIR" reset --quiet --hard "refs/remotes/origin/$REPO_BRANCH" &&
        run git -C "$SRC_DIR" clean -ffdxq; then
        fetched=yes; break
      fi
    else
      rm -rf "$SRC_DIR"
      if run timeout 180 git clone --quiet --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$SRC_DIR"; then
        fetched=yes; break
      fi
    fi
    info "GitHub не ответил — повторяю через 15 секунд…"; sleep 15
  done
  [[ $fetched == yes ]] || die "не удалось скачать код бота с GitHub."
  [[ -s $SRC_DIR/$BOT_SUBDIR/bot.py && -s $SRC_DIR/$BOT_SUBDIR/requirements.txt ]] ||
    die "в ветке $REPO_BRANCH нет папки $BOT_SUBDIR с ботом."

  rm -rf "$APP_DIR.new" "$APP_DIR.old"
  cp -a "$SRC_DIR/$BOT_SUBDIR" "$APP_DIR.new"
  chown -R root:root "$APP_DIR.new"
  chmod -R u=rwX,go=rX "$APP_DIR.new"
  if [[ -d $APP_DIR ]]; then mv "$APP_DIR" "$APP_DIR.old"; fi
  mv "$APP_DIR.new" "$APP_DIR"
  rm -rf "$APP_DIR.old"
  local commit
  commit=$(git -C "$SRC_DIR" log -1 --format='%h от %cd' --date=format-local:'%d.%m.%Y %H:%M' 2>/dev/null) || commit="?"
  printf '%s\n' "$commit" >"$BASE_DIR/VERSION"
  ok "версия $commit → $APP_DIR"
}

step_venv() {
  step "Python-окружение и библиотеки (aiogram, aiohttp) — до 2 минут"
  local want have
  want=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  have=$("$VENV_DIR/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) || have=""
  if [[ $have != "$want" ]]; then
    rm -rf "$VENV_DIR"
    run python3 -m venv "$VENV_DIR" || die "не удалось создать окружение Python (python3 -m venv)."
    ok "создано окружение Python $want"
  fi
  local pip=("$VENV_DIR/bin/python" -m pip install --disable-pip-version-check --no-input -q)
  local n installed=no
  for n in 1 2 3; do
    if run "${pip[@]}" -r "$APP_DIR/requirements.txt"; then installed=yes; break; fi
    info "pip не справился — повторяю через 20 секунд…"; sleep 20
  done
  if [[ $installed == no ]]; then
    local core
    core=$(grep -E '^aiogram==' "$APP_DIR/requirements.txt" | head -n 1) || core=""
    if [[ -n $core ]] && run "${pip[@]}" "$core"; then
      installed=yes
      warn "точные версии зависимостей не установились, поставлен $core с подходящими версиями"
    fi
  fi
  [[ $installed == yes ]] || die "не удалось установить библиотеки (pip). Проверьте интернет на сервере."
  "$VENV_DIR/bin/python" -c 'import aiogram, aiohttp' >/dev/null 2>&1 || die "библиотеки aiogram/aiohttp не загружаются."
  run "$VENV_DIR/bin/python" -m compileall -q "$APP_DIR" || true
  ok "aiogram $("$VENV_DIR/bin/python" -c 'import aiogram; print(aiogram.__version__)')"
}

# apply_token КЛЮЧ ЗНАЧЕНИЕ_ИЗ_АРГУМЕНТА ЗАДАН(yes/no) — записать, удалить («-») или оставить
apply_token() {
  local key=$1 value=$2 given=$3
  [[ $given == yes ]] || return 0
  if [[ $value == - ]]; then
    set_env "$ENV_FILE" "$key" ""
  elif [[ $(get_env "$ENV_FILE" "$key") != "$value" ]]; then
    set_env "$ENV_FILE" "$key" "$value"
  fi
}

step_config() {
  step "Настройки бота: $ENV_FILE (секретно, chmod 600)"
  local token result
  if [[ ! -f $ENV_FILE ]]; then
    if [[ ! ( $ARG_TG_SET == yes && $ARG_TG != - ) && ! ( $ARG_MAX_SET == yes && $ARG_MAX != - ) ]]; then
      die "нужен хотя бы один токен: … | bash -s -- --tg 'ТОКЕН_TELEGRAM' --max 'ТОКЕН_MAX'"
    fi
    write_env_template
    ok "создан $ENV_FILE"
  fi
  chown root:root "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  upgrade_env

  # --- Telegram
  if [[ $ARG_TG_SET == yes && $ARG_TG != - ]]; then
    result=$(tg_get_me "$ARG_TG")
    [[ $result != BAD ]] || die "Telegram не принял этот токен. Скопируйте токен из @BotFather заново (ничего не сохранено)."
  fi
  apply_token BOT_TOKEN "$ARG_TG" "$ARG_TG_SET"
  token=$(get_env "$ENV_FILE" BOT_TOKEN)
  if [[ -n $token ]]; then
    TG_ON=yes
    result=$(tg_get_me "$token")
    case $result in
      OK\ *) TG_NAME=${result#OK }; ok "Telegram: токен принят, бот @$TG_NAME" ;;
      BAD) warn "Telegram не принимает токен из $ENV_FILE — получите новый в @BotFather: --tg 'ТОКЕН'" ;;
      *) warn "нет связи с api.telegram.org — токен не проверен; бот подключится сам, когда связь появится" ;;
    esac
  else
    ok "Telegram: токена нет — Telegram-бот выключен"
  fi

  # --- MAX
  if [[ $ARG_MAX_SET == yes && $ARG_MAX != - ]]; then
    result=$(max_get_me "$ARG_MAX")
    [[ $result != BAD ]] || die "MAX не принял этот токен. Скопируйте его заново: Чат-боты → ⋮ → Настройки (ничего не сохранено)."
  fi
  apply_token MAX_TOKEN "$ARG_MAX" "$ARG_MAX_SET"
  token=$(get_env "$ENV_FILE" MAX_TOKEN)
  if [[ -n $token ]]; then
    MAX_ON=yes
    result=$(max_get_me "$token")
    case $result in
      OK\ ?*)
        MAX_LINK="https://max.ru/${result#OK }"
        ok "MAX: токен принят, бот $MAX_LINK"
        if [[ $(get_env "$ENV_FILE" MAX_BOT_URL) != "$MAX_LINK" ]]; then set_env "$ENV_FILE" MAX_BOT_URL "$MAX_LINK"; fi ;;
      OK*) ok "MAX: токен принят" ;;
      BAD) warn "MAX не принимает токен из $ENV_FILE — возьмите новый на платформе MAX: --max 'ТОКЕН'" ;;
      *) warn "нет связи с platform-api2.max.ru — токен не проверен; бот подключится сам, когда связь появится" ;;
    esac
    [[ -n $MAX_LINK ]] || MAX_LINK=$(get_env "$ENV_FILE" MAX_BOT_URL)
  else
    ok "MAX: токена нет — бот в MAX выключен"
  fi
  [[ $TG_ON == yes || $MAX_ON == yes ]] || die "не задан ни один токен — бот выключен. Добавьте: --tg 'ТОКЕН' и/или --max 'ТОКЕН'"

  # --- заявки в Telegram
  if [[ -n $ARG_CONTACTS ]]; then set_env "$ENV_FILE" TELEGRAM_COLLECT_CONTACTS "$ARG_CONTACTS"; fi
  if [[ $TG_ON == yes ]]; then
    if [[ $(get_env "$ENV_FILE" TELEGRAM_COLLECT_CONTACTS) == 1 ]]; then
      ok "Telegram: заявки с телефоном принимаются (TELEGRAM_COLLECT_CONTACTS=1)"
    else
      ok "Telegram: считает и показывает цены; за заявкой ведёт на сайт и в MAX (TELEGRAM_COLLECT_CONTACTS=0)"
    fi
  fi

  # --- адрес сайта
  local current auto
  current=$(get_env "$ENV_FILE" SITE_URL)
  auto=$(site_url_from_server)
  if [[ $ARG_SITE_URL_SET == yes ]]; then
    if [[ $ARG_SITE_URL == - ]]; then
      SITE_URL=""
    else
      SITE_URL=${ARG_SITE_URL%/}
      [[ $SITE_URL == http://* || $SITE_URL == https://* ]] || SITE_URL="https://$SITE_URL"
      valid_site_url "$SITE_URL" || die "непонятный адрес сайта «$ARG_SITE_URL». Пример: https://nashdekor.ru"
    fi
  elif [[ -z $current && -n $auto ]]; then
    SITE_URL=$auto
  elif [[ -n $current && -n $auto && $current == "http://${auto#https://}" && $auto == https://* ]]; then
    SITE_URL=$auto   # появился HTTPS — переходим на https
  else
    SITE_URL=$current
  fi
  if [[ -n $SITE_URL ]] && ! valid_site_url "$SITE_URL"; then
    warn "адрес сайта «$SITE_URL» выглядит странно — ссылки на сайт отключены"
    SITE_URL=""
  fi
  if [[ $SITE_URL != "$current" ]]; then set_env "$ENV_FILE" SITE_URL "$SITE_URL"; fi
  ok "сайт в сообщениях бота: ${SITE_URL:-не задан (ссылки на сайт не показываются)}"

  # --- одноразовый код для /owner
  OWNER_CODE=$(get_env "$ENV_FILE" OWNER_CODE)
  if [[ $NEW_CODE == yes || ! $OWNER_CODE =~ ^[0-9]{6}$ ]]; then
    OWNER_CODE=$(new_code)
    set_env "$ENV_FILE" OWNER_CODE "$OWNER_CODE"
    ok "создан новый одноразовый код для /owner"
  fi
  if [[ -z $(get_env "$ENV_FILE" CONSENT_VERSION) ]]; then set_env "$ENV_FILE" CONSENT_VERSION 1; fi
}

# start_service СЛУЖБА СЛОВО_В_ЖУРНАЛЕ — перезапустить и дождаться строки «…запущен»
start_service() {
  local svc=$1 t0 n0 n1 i started=no
  run systemctl enable "$svc" || { warn "не удалось включить службу $svc"; return 1; }
  t0=$(date +%s)
  run systemctl restart "$svc" || { warn "служба $svc не запустилась: journalctl -u $svc -n 30"; return 1; }
  n0=$(systemctl show -p NRestarts --value "$svc" 2>/dev/null) || n0=0
  for i in $(seq 1 25); do
    if journalctl -u "$svc" --since "@$t0" -o cat --no-pager 2>/dev/null | grep -q 'бот .*запущен'; then
      started=yes; break
    fi
    sleep 1
  done
  n1=$(systemctl show -p NRestarts --value "$svc" 2>/dev/null) || n1=0
  if [[ $started == yes ]] && systemctl is-active --quiet "$svc" && [[ $n0 == "$n1" ]]; then
    return 0
  fi
  warn "служба $svc пока не запустилась (через $i с). Последние строки журнала:"
  journalctl -u "$svc" --since "@$t0" -o cat --no-pager -n 12 2>/dev/null | sed 's/^/   | /' || true
  return 1
}

stop_service() {
  local svc=$1
  if systemctl is-enabled --quiet "$svc" 2>/dev/null || systemctl is-active --quiet "$svc" 2>/dev/null; then
    run systemctl disable --now "$svc" || true
    ok "служба $svc остановлена (нет токена)"
  fi
}

step_service() {
  step "Службы systemd: $SVC_TG (Telegram) и $SVC_MAX (MAX) — независимые"
  local svc changed=no
  for svc in "$SVC_TG" "$SVC_MAX"; do
    if [[ ! -f $SYSTEMD_DIR/$svc.service ]] || ! cmp -s "$APP_DIR/$svc.service" "$SYSTEMD_DIR/$svc.service"; then
      install -m 644 -o root -g root "$APP_DIR/$svc.service" "$SYSTEMD_DIR/$svc.service"
      changed=yes
    fi
  done
  if [[ $changed == yes ]]; then run systemctl daemon-reload || die "systemctl daemon-reload не выполнился"; fi
  # Обе службы при первом запуске переводят базу на новую версию — по очереди, под общим замком.
  if [[ $TG_ON == yes ]]; then
    if start_service "$SVC_TG"; then TG_RUNNING=yes; ok "Telegram-бот работает (стартует сам после перезагрузки)"; fi
  else
    stop_service "$SVC_TG"
  fi
  if [[ $MAX_ON == yes ]]; then
    if start_service "$SVC_MAX"; then MAX_RUNNING=yes; ok "бот в MAX работает (стартует сам после перезагрузки)"; fi
  else
    stop_service "$SVC_MAX"
  fi
}

# «использован_ли_код менеджеров отгрузка» из базы бота (только чтение; старая и новая схема)
team_status() {
  [[ -f $DB_FILE ]] || { printf 'no 0 0'; return 0; }
  OWNER_CODE_CHECK=$OWNER_CODE python3 - "$DB_FILE" <<'PY' 2>/dev/null || printf 'no 0 0'
import hashlib, os, sqlite3, sys
code = os.environ.get("OWNER_CODE_CHECK", "")
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
key = "owner_code_used:" + hashlib.sha256(("prostranstvo-owner:" + code).encode()).hexdigest()
used, roles = False, {}
try:
    used = con.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone() is not None
    roles = dict(con.execute("SELECT role, COUNT(*) FROM persons GROUP BY role").fetchall())
except sqlite3.Error:
    try:
        roles = dict(con.execute("SELECT role, COUNT(*) FROM team GROUP BY role").fetchall())
    except sqlite3.Error:
        pass
print("yes" if used else "no", roles.get("manager", 0), roles.get("shipping", 0), end="")
PY
}

summary() {
  local used managers shipping where
  read -r used managers shipping <<<"$(team_status)"
  where=""
  if [[ $MAX_ON == yes ]]; then where="бота в MAX${MAX_LINK:+ ($MAX_LINK)}"; fi
  if [[ $TG_ON == yes ]]; then where="${where:+$where или }бота в Telegram${TG_NAME:+ (@$TG_NAME)}"; fi
  printf '\n==================================================\n'
  if ((${#WARNINGS[@]})); then
    printf ' ГОТОВО, но есть замечания (см. ниже)\n'
  else
    printf ' ГОТОВО: бот «Наш декор» работает\n'
  fi
  printf '==================================================\n'
  if [[ $TG_ON == yes ]]; then
    printf ' Telegram: %s  [%s]\n' "${TG_NAME:+https://t.me/$TG_NAME}" "$([[ $TG_RUNNING == yes ]] && echo работает || echo 'НЕ запущен')"
  else
    printf ' Telegram: выключен (нет токена)\n'
  fi
  if [[ $MAX_ON == yes ]]; then
    printf ' MAX:      %s  [%s]\n' "${MAX_LINK:-}" "$([[ $MAX_RUNNING == yes ]] && echo работает || echo 'НЕ запущен')"
  else
    printf ' MAX:      выключен (нет токена)\n'
  fi
  printf ' Сайт в сообщениях бота: %s\n' "${SITE_URL:-не задан}"
  printf ' Версия: %s\n' "$(cat "$BASE_DIR/VERSION" 2>/dev/null || echo '?')"
  printf ' В команде: менеджеров %s, отгрузка %s\n' "${managers:-0}" "${shipping:-0}"

  printf '\n Подключить команду магазина:\n'
  if [[ $used == no ]]; then
    printf '  1) Менеджер: откройте %s, нажмите «Начать»/«Старт» и отправьте\n' "$where"
    printf '        /owner %s\n' "$OWNER_CODE"
    printf '     Код одноразовый: кто первым отправит — станет менеджером.\n'
  else
    printf '  1) Менеджер уже назначен (код /owner использован). Новый код: установка с --new-code\n'
  fi
  printf '  2) Отгрузка: менеджер в боте — «Команда» → «Пригласить на отгрузку», пересылает код;\n'
  printf '     второй человек открывает бота и отправляет /join КОД (код действует 24 часа).\n'
  if [[ $TG_ON == yes && $MAX_ON == yes ]]; then
    printf '  3) Второй мессенджер для себя: «Уведомления» → «Подключить MAX/Telegram» → /join КОД\n'
    printf '     в другом мессенджере. Заявки придут туда, где выбрано (по умолчанию — MAX).\n'
  fi

  if ((${#WARNINGS[@]})); then
    printf '\n Замечания:\n'
    local w
    for w in "${WARNINGS[@]}"; do printf '  - %s\n' "$w"; done
  fi
  printf '\n Обновить бота (токены и заявки сохранятся):\n'
  printf '   curl -fsSL %s | bash\n' "$RAW_INSTALL_URL"
  printf ' Журналы:  journalctl -u %s -n 50   |   journalctl -u %s -n 50\n' "$SVC_TG" "$SVC_MAX"
  printf ' Заявки и переписка: %s (только на этом сервере)\n' "$DB_FILE"
  printf ' Настройки и токены: %s (секретно)\n' "$ENV_FILE"
  printf '==================================================\n'
}

main() {
  trap '' HUP          # не прерываться, если связь с телефоном оборвётся
  exec </dev/null      # ничего не спрашивать
  parse_args "$@"
  check_root_and_os
  install -d -m 755 /var/log
  touch "$LOG_FILE"
  chmod 640 "$LOG_FILE"
  chown root:adm "$LOG_FILE" 2>/dev/null || true
  printf '\n=== %s: запуск install-bot.sh ===\n' "$(date '+%F %T')" >>"$LOG_FILE"
  exec 9>/run/prostranstvo-bot-install.lock
  flock -n 9 || die "установка бота уже идёт в другом окне. Дождитесь её окончания."
  check_server

  printf '\n=== Установка бота «Наш декор» (Telegram и MAX) — %s ===\n' "$(date '+%d.%m.%Y %H:%M')"
  step_packages
  step_user
  step_code
  step_venv
  step_config
  step_service
  summary
}

if [[ ${INSTALL_BOT_NO_MAIN:-0} != 1 ]]; then
  main "$@"
fi
