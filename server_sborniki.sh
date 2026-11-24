#!/bin/bash
# Сборники «Кота Барсика» для Rutube: скачать из релизов GitHub на сервер страницы (89.126.192.214),
# чтобы Юля качала их со страницы s9kbars так же, как Shorts (с того же сервера).
# Запуск (iPhone «Команды» → «Сервер»):
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/studio/server_sborniki.sh | bash
# Проверить, что скачалось:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/studio/server_sborniki.sh | bash -s status
D=/var/www/mebel/s9kbars-sb
NAMES="27-31 32-36 27-36"
mkdir -p "$D"
if [ "$1" = "status" ]; then
  ls -la "$D"
  echo "---"; tail -6 /tmp/sborniki.log 2>/dev/null
  echo "---"; df -h "$D" | tail -1
  exit 0
fi
free=$(df -Pk "$D" | awk 'NR==2{print $4}')
echo "свободно на диске: $((free / 1024)) МБ"
if [ "$free" -lt 3800000 ]; then
  echo "МАЛО МЕСТА: нужно около 3600 МБ — пришли это сообщение Claude"
  exit 1
fi
cat > /tmp/sborniki-dl.sh <<EOF
for n in $NAMES; do
  f="$D/rutube-\$n.mp4"
  if [ -s "\$f" ]; then echo "уже есть \$f"; continue; fi
  if curl -fsSL --retry 3 -o "\$f.part" "https://github.com/mikhailusenko88-hub/Mikhail/releases/download/rutube-\$n/rutube-\$n.mp4"; then
    mv "\$f.part" "\$f"; chmod 644 "\$f"; echo "скачан \$f"
  else
    rm -f "\$f.part"; echo "ОШИБКА \$n"
  fi
done
echo ГОТОВО
EOF
setsid nohup bash /tmp/sborniki-dl.sh > /tmp/sborniki.log 2>&1 < /dev/null &
echo "ЗАПУЩЕНО: 3 сборника (~3,5 ГБ) качаются в фоне, обычно 5–15 минут."
