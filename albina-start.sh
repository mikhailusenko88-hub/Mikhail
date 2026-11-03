#!/bin/bash
# Запуск установки Альбины в фоне — короткая команда для «Сервер» на iPhone:
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/pochemu-albina/albina-start.sh | bash
RAW=https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/pochemu-albina
if pgrep -f "bash /root/albina.sh" >/dev/null; then
  echo "Установка Альбины уже идёт. Как она — команда: tail -n 25 /root/albina.log"
  tail -n 5 /root/albina.log 2>/dev/null
  exit 0
fi
curl -fsSL "$RAW/deploy_albina.sh" -o /root/albina.sh || { echo "Не скачалось с GitHub — попробуй ещё раз"; exit 1; }
(setsid nohup bash /root/albina.sh > /root/albina.log 2>&1 < /dev/null &)
sleep 3
echo "Запустил установку Альбины (5–15 минут). Как она — команда: tail -n 25 /root/albina.log"
tail -n 4 /root/albina.log 2>/dev/null
exit 0
