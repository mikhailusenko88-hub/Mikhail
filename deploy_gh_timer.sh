#!/bin/bash
# Будильник для роликов на GitHub: сервер сам нажимает «Run workflow» в нужное время.
# GitHub иногда пропускает запуски по расписанию — с сервера запуск срабатывает сразу.
# Свой бот на GitHub не выложит дубль: если ролик слота уже есть, он просто ничего не делает.
#
# Установка (один раз):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/kz-bot/deploy_gh_timer.sh | bash -s -- ТОКЕН
# Проверка:   gh-kick status
# Убрать:     curl -fsSL .../deploy_gh_timer.sh | bash -s -- --remove
set -u
REPO=mikhailusenko88-hub/Mikhail
TOK=/root/.gh_timer_token
BIN=/usr/local/bin/gh-kick
CRON=/etc/cron.d/gh-timer
LOGF=/var/log/gh-kick.log

if [ "${1:-}" = "--remove" ]; then
  rm -f "$CRON" "$BIN" "$TOK"; echo "Будильник убран."; exit 0
fi

T="${1:-}"
if [ -z "$T" ] || [ "$T" = "ТОКЕН" ]; then
  [ -s "$TOK" ] && T=$(cat "$TOK") || { echo "!! Нет токена: вставьте токен GitHub вместо слова ТОКЕН"; exit 1; }
fi

echo "== Проверяю токен…"
code=$(curl -s -o /tmp/ghk.json -w '%{http_code}' --max-time 20 -H "Authorization: Bearer $T" \
  -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$REPO/actions/workflows/uz-race.yml")
if [ "$code" != "200" ]; then
  echo "!! GitHub ответил $code — токен не подходит (нужен доступ к репозиторию Mikhail, Actions: Read and write)"
  head -c 300 /tmp/ghk.json; echo; exit 1
fi
umask 077; printf '%s' "$T" > "$TOK"; chmod 600 "$TOK"
echo "   токен ОК, сохранён"

cat > "$BIN" <<'KICK'
#!/bin/bash
# gh-kick ИМЯ.yml [json-inputs]  — нажать «Run workflow»;  gh-kick tick — по расписанию;  gh-kick status
REPO=mikhailusenko88-hub/Mikhail
TOK=$(cat /root/.gh_timer_token 2>/dev/null)
LOGF=/var/log/gh-kick.log
log() { echo "$(date -u '+%F %H:%M') UTC $*" >> "$LOGF"; }
kick() {
  local wf=$1 inputs=${2:-'{}'} code n
  for n in 1 2 3; do
    code=$(curl -s -o /tmp/ghk-$$.txt -w '%{http_code}' --max-time 30 -X POST \
      -H "Authorization: Bearer $TOK" -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$REPO/actions/workflows/$wf/dispatches" \
      -d "{\"ref\":\"main\",\"inputs\":$inputs}")
    [ "$code" = "204" ] && { log "$wf запущен"; rm -f /tmp/ghk-$$.txt; return 0; }
    sleep 20
  done
  log "$wf ОШИБКА $code $(head -c 200 /tmp/ghk-$$.txt)"; rm -f /tmp/ghk-$$.txt; return 1
}
case "${1:-}" in
  tick)
    hm=$(date -u +%H:%M)
    # Kim yutadi? (Ташкент = UTC+5): слоты 12:00, 16:00, 20:00 — запуск за 25 мин и два повтора
    case "$hm" in 06:35|07:00|07:25|10:35|11:00|11:25|14:35|15:00|15:25)
      kick uz-race.yml '{"kind":"schedule"}' ;; esac
    # Flagball Arena (Москва = UTC+3): слоты 07:00, 15:00, 23:00 — запуск за 30 мин и два повтора
    case "$hm" in 03:30|03:55|04:20|11:30|11:55|12:20|19:30|19:55|20:20)
      kick flagball.yml '{}' ;; esac
    # журнал не растёт бесконечно
    [ -f "$LOGF" ] && [ "$(wc -l < "$LOGF")" -gt 1000 ] && tail -n 500 "$LOGF" > "$LOGF.tmp" && mv "$LOGF.tmp" "$LOGF"
    ;;
  status) echo "Время сервера: $(date -u '+%F %H:%M') UTC"; echo "--- последние запуски:"; tail -n 15 "$LOGF" 2>/dev/null || echo "(ещё не было)";;
  *.yml) kick "$1" "${2:-}" && echo "запущен $1" || { echo "ошибка, см. gh-kick status"; exit 1; } ;;
  *) echo "gh-kick tick | status | uz-race.yml '{\"kind\":\"schedule\"}' | flagball.yml";;
esac
KICK
chmod 755 "$BIN"

cat > "$CRON" <<CR
# будильник роликов на GitHub (deploy_gh_timer.sh); раз в 5 минут смотрит, не пора ли
SHELL=/bin/bash
*/5 * * * * root $BIN tick
CR
chmod 644 "$CRON"
touch "$LOGF"
command -v systemctl >/dev/null && (systemctl reload cron 2>/dev/null || systemctl restart cron 2>/dev/null || systemctl restart crond 2>/dev/null)
pgrep -x cron >/dev/null || pgrep -x crond >/dev/null || echo "!! служба cron не запущена — напишите Claude"
echo "== Готово. Будильник стоит."
echo "   узбекский канал: 11:35, 15:35, 19:35 по Ташкенту (+ повторы через 25 и 50 мин)"
echo "   Flagball:        06:30, 14:30, 22:30 по Москве (+ повторы через 25 и 50 мин)"
echo "   Проверить: gh-kick status"
