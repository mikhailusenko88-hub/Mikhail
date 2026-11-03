#!/bin/bash
# Голос «Альбина» (мягкий тон) для бота «Почему так?» — установка на сервер.
# Казахский бот «Білесің бе?», VPN, сайты и nginx не трогаются.
#
# Поставить (в фоне, 5–15 минут, вывод в /root/albina.log):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/pochemu-albina/deploy_albina.sh -o /root/albina.sh && setsid nohup bash /root/albina.sh > /root/albina.log 2>&1 &
# Посмотреть, как идёт:   tail -n 25 /root/albina.log
# Вернуть Дмитрия:        bash /root/albina.sh back
# Снова Альбину:          bash /root/albina.sh on
set -u
RAW=${ALBINA_RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/pochemu-albina}
MULTIK=${MULTIK_RAW:-https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/mebel-3d/tools/multik/tts}
T=/opt/multik-tts
STAMP=$(date +%Y%m%d-%H%M%S)
MODE=${1:-install}
export DEBIAN_FRONTEND=noninteractive PIP_DISABLE_PIP_VERSION_CHECK=1

dl() {  # dl URL FILE
  curl -fsSL --retry 3 --max-time 600 -o "$2.part" "$1" && [ -s "$2.part" ] && mv -f "$2.part" "$2" || { rm -f "$2.part"; return 1; }
}

echo "== $(date '+%d.%m %H:%M') Голос «Альбина» для «Почему так?» ($MODE)"
echo "== 1/6 Ищу бота «Почему так?»"
mapfile -t DIRS < <(find "${SEARCH_ROOT:-/}" -xdev -name make_video.py -not -path '/proc/*' -not -path '*/.git/*' \
                    -not -path '*/node_modules/*' -not -path '*/work/*' -not -path '/opt/*' 2>/dev/null | xargs -r -n1 dirname | sort -u)
BOTS=()
for D in "${DIRS[@]}"; do
  [ -f "$D/config.json" ] && [ -f "$D/run_daily.py" ] || continue
  L=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('lang','ru'))" "$D/config.json" 2>/dev/null || echo ru)
  [ "$L" = "kk" ] && { echo "   $D — «Білесің бе?», не трогаю"; continue; }
  BOTS+=("$D"); echo "   $D — «Почему так?»"
done
[ ${#BOTS[@]} -gt 0 ] || { echo "!! Не нашёл бота «Почему так?» (папка с make_video.py, run_daily.py и config.json)"; exit 1; }

set_voice() {  # set_voice DIR albina|old
  python3 - "$1/config.json" "$2" <<'PY'
import json, sys
p, want = sys.argv[1], sys.argv[2]
cfg = json.load(open(p, encoding="utf-8"))
cur = cfg.get("voices") or ["ru-RU-DmitryNeural"]
if want == "albina":
    if not any(str(v).startswith("albina") for v in cur):
        cfg["voices_old"] = cur
    cfg["voices"] = ["albina"]
else:
    cfg["voices"] = cfg.get("voices_old") or ["ru-RU-DmitryNeural"]
tmp = p + ".tmp"
open(tmp, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
json.load(open(tmp, encoding="utf-8"))
import os; os.replace(tmp, p)
print("   голос в config.json:", ", ".join(cfg["voices"]))
PY
}

if [ "$MODE" = back ] || [ "$MODE" = on ]; then
  for D in "${BOTS[@]}"; do
    cp -p "$D/config.json" "$D/config.json.bak-$STAMP"
    if [ "$MODE" = back ]; then set_voice "$D" old; else set_voice "$D" albina; fi
  done
  echo "== Готово: следующий ролик выйдет $([ "$MODE" = back ] && echo 'прежним голосом' || echo 'голосом Альбины')."
  exit 0
fi

wait_bot() {  # не менять файлы, пока бот собирает ролик
  local D=$1 i pid busy
  for i in $(seq 1 90); do
    busy=0
    for pid in $(pgrep -f run_daily.py 2>/dev/null); do
      [ "$(readlink -f /proc/$pid/cwd 2>/dev/null)" = "$D" ] && busy=1
    done
    [ $busy = 0 ] && return 0
    [ $i = 1 ] && echo "   бот сейчас собирает ролик — жду, пока закончит"
    sleep 10
  done
  echo "   ! бот занят больше 15 минут — продолжаю"
}

bot_py() {  # каким python бот запускается из cron
  local D=$1 py
  py=$(crontab -l 2>/dev/null | grep -v '^\s*#' | grep run_daily | grep -F "$D" | head -1 | grep -oE '[^ ;&|()]*python[0-9.]*' | head -1)
  [ -n "$py" ] && command -v "$py" >/dev/null 2>&1 && { echo "$py"; return; }
  [ -x "$D/.venv/bin/python" ] && { echo "$D/.venv/bin/python"; return; }
  [ -x "$D/venv/bin/python" ] && { echo "$D/venv/bin/python"; return; }
  echo python3
}

echo "== 2/6 Голос (Silero v5 CIS, ударения ruaccent)"
need=0
[ -x $T/venv/bin/python ] && $T/venv/bin/python -c "import torch, ruaccent, numpy" 2>/dev/null || need=1
[ -s $T/v5_cis_base.pt ] || need=1
if [ $need = 0 ]; then
  echo "   уже установлен в $T (тот же, что у «Мультиков») — беру его"
else
  free_mb=$(df -BM --output=avail / | tail -1 | tr -dc 0-9)
  echo "   ставлю в $T (свободно на диске: ${free_mb} МБ, нужно около 2500)"
  [ "${free_mb:-0}" -gt 2600 ] || { echo "!! Мало места на диске — нужно хотя бы 2,6 ГБ свободных. Ничего не менял."; exit 1; }
  if ! python3 -c "import ensurepip" 2>/dev/null; then
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq python3-venv >/dev/null 2>&1 || apt-get install -y -qq "python3.$(python3 -c 'import sys;print(sys.version_info.minor)')-venv" >/dev/null 2>&1 || true
  fi
  mkdir -p $T/hf
  if [ ! -x $T/venv/bin/pip ]; then
    rm -rf $T/venv
    python3 -m venv $T/venv 2>/dev/null || { python3 -m venv --without-pip $T/venv && curl -fsSL https://bootstrap.pypa.io/get-pip.py | $T/venv/bin/python - -q; }
  fi
  echo "   python-пакеты (несколько минут)…"
  $T/venv/bin/pip install -q --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu || { echo "!! torch не поставился"; exit 1; }
  $T/venv/bin/pip install -q --no-cache-dir numpy ruaccent || { echo "!! ruaccent не поставился"; exit 1; }
  if [ ! -s $T/v5_cis_base.pt ]; then
    echo "   модель голоса…"
    dl https://models.silero.ai/models/tts/ru/v5_cis_base.pt $T/v5_cis_base.pt || { echo "!! модель голоса не скачалась"; exit 1; }
  fi
fi
if ! command -v ffmpeg >/dev/null; then echo "!! на сервере нет ffmpeg (а бот без него не работает?) — проверь"; exit 1; fi
mem=$(free -m | awk '/Mem:/{print $2}'); sw=$(free -m | awk '/Swap:/{print $2}')
echo "   память ${mem} МБ, подкачка ${sw} МБ"
if [ $((mem + sw)) -lt 2500 ] && [ ! -f /swapfile-tts ] && [ "$(df -BM --output=avail / | tail -1 | tr -dc 0-9)" -gt 5000 ]; then
  fallocate -l 2G /swapfile-tts && chmod 600 /swapfile-tts && mkswap /swapfile-tts >/dev/null && swapon /swapfile-tts \
    && { grep -q swapfile-tts /etc/fstab || echo '/swapfile-tts none swap sw 0 0' >> /etc/fstab; } && echo "   добавил подкачку 2 ГБ"
fi
[ -s $T/server.py ] || dl "$MULTIK/server.py" $T/server.py || { echo "!! не скачался server.py"; exit 1; }
dl "$RAW/albina_worker.py" $T/albina_worker.py || { echo "!! не скачался albina_worker.py"; exit 1; }
du -sh $T 2>/dev/null | awk '{print "   занимает на диске: "$1}'

FAIL=0
for D in "${BOTS[@]}"; do
  echo "== 3/6 Подключаю к боту ($D)"
  wait_bot "$D"
  PY=$(bot_py "$D"); echo "   бот запускается через: $PY"
  for f in make_video.py config.json albina.py albina_fix.json; do [ -f "$D/$f" ] && cp -p "$D/$f" "$D/$f.bak-$STAMP"; done
  restore() { for f in make_video.py albina.py albina_fix.json; do [ -f "$D/$f.bak-$STAMP" ] && cp -p "$D/$f.bak-$STAMP" "$D/$f"; done; }
  if ! { dl "$RAW/albina.py" "$D/albina.py" && dl "$RAW/albina_fix.json" "$D/albina_fix.json" && dl "$RAW/patch_bot.py" /tmp/albina_patch.py; }; then
    echo "!! файлы не скачались с GitHub — ничего не менял"; restore; FAIL=1; continue
  fi
  python3 /tmp/albina_patch.py "$D/make_video.py"; RC=$?
  if [ $RC -ne 0 ] || ! python3 -m py_compile "$D/make_video.py" "$D/albina.py" \
     || ! (cd "$D" && "$PY" -c "import make_video as m, sys; sys.exit(0 if getattr(m.speak,'_albina',0) and getattr(m.build,'_albina',0) else 1)"); then
    echo "!! не получилось подключить — вернул файлы как были, бот работает с прежним голосом"; restore; FAIL=1; continue
  fi

  echo "== 4/6 Проверка голоса (первый раз до 10 минут: скачиваются словари ударений)"
  if ! (cd "$D" && timeout 1500 "$PY" albina.py); then
    echo "!! Альбина не заговорила — голос НЕ переключаю, бот работает как раньше. Последние строки озвучщика:"
    tail -n 15 $T/worker.log 2>/dev/null
    FAIL=1; continue
  fi

  echo "== 5/6 Переключаю голос"
  set_voice "$D" albina || { cp -p "$D/config.json.bak-$STAMP" "$D/config.json"; echo "!! config.json не записался"; FAIL=1; continue; }

  echo "== 6/6 Пробный ролик (ничего не выкладывается, 2–5 минут)"
  N0=$(wc -l < "$D/bot.log" 2>/dev/null || echo 0)
  if (cd "$D" && timeout 1200 "$PY" run_daily.py --test > /tmp/albina_run.txt 2>&1); then
    tail -n +$((N0 + 1)) "$D/bot.log" 2>/dev/null | grep -E "Сценарий|Озвучка|голос загружен|ударения|прежним|Ролик готов" | cut -c21-230
    V=$(ls -t "$D"/out/*.mp4 2>/dev/null | head -1)
    KEY=$(cat "$D/.web_key" 2>/dev/null)
    WEB=$(python3 -c "import json,sys;c=json.load(open(sys.argv[1],encoding='utf-8'));print(c.get('web_root','/var/www/html')+'|'+c.get('web_base_url','http://89.126.192.214:8080'))" "$D/config.json" 2>/dev/null)
    if [ -n "$V" ] && [ -n "$KEY" ] && [ -d "${WEB%%|*}/klipy-$KEY" ]; then
      cp -f "$V" "${WEB%%|*}/klipy-$KEY/proba-albina.mp4" && chmod 644 "${WEB%%|*}/klipy-$KEY/proba-albina.mp4"
      URL=$(echo "${WEB#*|}" | sed 's/89\.207\.252\.121/89.126.192.214/; s:/*$::')
      echo "   послушать пробный ролик: $URL/klipy-$KEY/proba-albina.mp4"
    elif [ -n "$V" ]; then
      echo "   пробный ролик: $V"
    fi
  else
    echo "   ! пробный ролик не собрался (голос уже переключён, вечером бот попробует сам). Хвост вывода:"
    tail -n 12 /tmp/albina_run.txt
  fi
done

echo
if [ $FAIL = 0 ]; then
  echo "== ГОТОВО: «Почему так?» теперь говорит голосом Альбины (мягкий тон)."
  echo "   Если Альбина вдруг не загрузится — ролик выйдет прежним голосом, выкладка не сорвётся."
  echo "   Вернуть Дмитрия: bash /root/albina.sh back"
else
  echo "== НЕ ДО КОНЦА: см. сообщения выше (копии файлов: *.bak-$STAMP)"
  exit 1
fi
