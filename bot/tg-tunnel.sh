#!/usr/bin/env bash
# Туннель до Telegram для бота «Наш декор»: сервер магазина в РФ (FirstVDS) не достаёт до api.telegram.org
# (замедление Telegram с 02.2026), поэтому связь бота с Telegram идёт через наш сервер в Казахстане.
#
#   Через туннель идёт ТОЛЬКО связь бота с api.telegram.org — зашифрованная (TLS внутри SSH).
#   Казахстанский сервер её не читает и ничего не записывает. База, заявки, переписка — только на сервере в РФ.
#   VPN на казахстанском сервере не трогается: туда добавляется только ключ с правом «пробросить порт».
#
# Запуск (на сервере магазина, root):
#   tg-tunnel.sh key          — создать ключ туннеля и напечатать строку для authorized_keys сервера в Казахстане
#   tg-tunnel.sh on [--tg …]  — проверить прямую связь; если её нет — включить туннель (служба
#                               prostranstvo-tg-tunnel, SOCKS 127.0.0.1:1080), прописать TELEGRAM_PROXY и обновить
#                               бота установщиком (параметры после on передаются установщику, например --tg "ТОКЕН")
#   tg-tunnel.sh off          — аварийная кнопка: выключить туннель, бот снова ходит в Telegram напрямую
#   tg-tunnel.sh status       — что сейчас: прямая связь, туннель, связь через туннель
#
# С Мака (одной строкой, см. claude/artdec-messendzhery-boty.md):
#   K=$(ssh root@185.60.134.150 'curl -fsSL …/tg-tunnel.sh | bash -s -- key') && [ -n "$K" ] && \
#     ssh root@89.126.192.214 "mkdir -p .ssh && chmod 700 .ssh && echo '$K' >> .ssh/authorized_keys"
#   ssh -t root@185.60.134.150 'read -rsp "Токен: " T; echo; curl -fsSL …/tg-tunnel.sh | bash -s -- on --tg "$T"'
set -euo pipefail

TUNNEL_HOST=${TG_TUNNEL_HOST:-89.126.192.214}       # сервер в Казахстане (Hoster.kz)
TUNNEL_PORT=1080
KEY=/root/.ssh/tg_tunnel
KNOWN=/root/.ssh/known_hosts_tg
SERVICE=prostranstvo-tg-tunnel
UNIT=/etc/systemd/system/$SERVICE.service
ENV_FILE=/etc/prostranstvo/bot.env
PROXY_URL="socks5://127.0.0.1:$TUNNEL_PORT"
INSTALL_URL=${INSTALL_URL:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/server/bot/install-bot.sh}

say() { printf '%s\n' "$*" >&2; }
die() { say "ОШИБКА: $*"; exit 1; }
[[ $EUID -eq 0 ]] || die "запускайте от root (ssh root@185.60.134.150 …)"

# код ответа api.telegram.org: напрямую или через прокси ("000" — нет связи)
tg_code() {
  local proxy=${1:-}
  local args=(-sS -o /dev/null -w '%{http_code}' --max-time 15)
  [[ -n $proxy ]] && args+=(--proxy "$proxy")
  curl "${args[@]}" https://api.telegram.org/ 2>/dev/null || true
}
reachable() { local c; c=$(tg_code "${1:-}"); [[ -n $c && $c != 000 ]]; }

set_proxy_env() {
  local value=$1
  [[ -f $ENV_FILE ]] || die "нет $ENV_FILE — сначала установите бота (install-bot.sh)"
  if grep -q '^TELEGRAM_PROXY=' "$ENV_FILE"; then
    sed -i "s|^TELEGRAM_PROXY=.*|TELEGRAM_PROXY=$value|" "$ENV_FILE"
  else
    printf '# Прокси до api.telegram.org (ставит tg-tunnel.sh on; пусто — напрямую)\nTELEGRAM_PROXY=%s\n' "$value" >>"$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
}

cmd_key() {
  command -v ssh-keygen >/dev/null || die "нет ssh-keygen — apt-get install -y openssh-client"
  mkdir -p /root/.ssh && chmod 700 /root/.ssh
  if [[ ! -s $KEY ]]; then
    ssh-keygen -q -t ed25519 -N "" -C "tg-tunnel@nashdekor" -f "$KEY" >&2
    say "+ ключ туннеля создан: $KEY"
  else
    say "+ ключ туннеля уже есть: $KEY"
  fi
  # restrict — без входа в консоль, без агента; port-forwarding — только проброс портов
  printf 'restrict,port-forwarding %s\n' "$(cat "$KEY.pub")"
}

write_unit() {
  cat >"$UNIT" <<EOF
[Unit]
Description=Наш декор: туннель до Telegram через сервер в Казахстане (SOCKS 127.0.0.1:$TUNNEL_PORT)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
ExecStart=/usr/bin/ssh -N -D 127.0.0.1:$TUNNEL_PORT -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$KNOWN root@$TUNNEL_HOST
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
}

cmd_on() {
  say "[1/3] Прямая связь сервера с api.telegram.org"
  if reachable && reachable; then
    say "  + Telegram доступен напрямую — туннель не нужен"
    if [[ -f $ENV_FILE ]] && grep -q '^TELEGRAM_PROXY=.' "$ENV_FILE"; then
      say "  ! туннель был включён раньше — оставляю (выключить: tg-tunnel.sh off)"
    fi
  else
    say "  - напрямую нет связи — включаю туннель через $TUNNEL_HOST"
    [[ -s $KEY ]] || die "нет ключа туннеля — сначала шаг с «key» (ключ добавляется на сервер в Казахстане)"
    say "[2/3] Туннель: служба $SERVICE"
    write_unit
    systemctl daemon-reload
    systemctl enable "$SERVICE" >/dev/null 2>&1 || true
    systemctl restart "$SERVICE" || true
    local ok=no i
    for i in $(seq 1 12); do
      sleep 2
      if reachable "socks5h://127.0.0.1:$TUNNEL_PORT"; then ok=yes; break; fi
    done
    if [[ $ok != yes ]]; then
      journalctl -u "$SERVICE" -n 8 --no-pager >&2 || true
      systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
      die "через $TUNNEL_HOST до Telegram не достучаться. Если выше «Permission denied» — ключ не добавлен на сервер в Казахстане (повторите шаг с «key»). Ничего не изменено."
    fi
    say "  + через туннель Telegram отвечает"
    set_proxy_env "$PROXY_URL"
    say "  + TELEGRAM_PROXY=$PROXY_URL в $ENV_FILE"
  fi
  say "[3/3] Обновление бота (библиотеки для прокси, перезапуск)"
  curl -fsSL "$INSTALL_URL" | bash -s -- "$@"
}

cmd_off() {
  systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
  if [[ -f $ENV_FILE ]]; then set_proxy_env ""; fi
  systemctl restart prostranstvo-bot >/dev/null 2>&1 || true
  say "+ туннель выключен, бот ходит в Telegram напрямую (включить снова: tg-tunnel.sh on)"
}

cmd_status() {
  local direct via proxy
  direct=$(tg_code)
  via=$(tg_code "socks5h://127.0.0.1:$TUNNEL_PORT")
  proxy=$(grep '^TELEGRAM_PROXY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
  say "напрямую до api.telegram.org: $([[ $direct != 000 ]] && echo есть || echo нет)"
  say "служба туннеля $SERVICE: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
  say "через туннель: $([[ $via != 000 ]] && echo есть || echo нет)"
  say "бот настроен: ${proxy:-напрямую}"
}

case ${1:-} in
  key) cmd_key ;;
  on) shift; cmd_on "$@" ;;
  off) cmd_off ;;
  status) cmd_status ;;
  *) say "использование: tg-tunnel.sh key | on [параметры установщика] | off | status"; exit 2 ;;
esac
