#!/bin/bash
# Почему Альбина сбивается: память, служба голоса, убитые процессы — коротко для экрана телефона.
#   curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/pochemu-albina/albina-diag.sh | bash
echo "== Сервер: $(nproc) ядра, сейчас $(date '+%H:%M') (часы сервера)"
free -m | awk '/^Mem/{print "Память: "$2" МБ, свободно "$7} /^Swap/{print "Подкачка: "$2" МБ, занято "$3}'
P=$(systemctl show -p MainPID --value multik-tts 2>/dev/null)
echo "== Служба голоса: $(systemctl is-active multik-tts 2>/dev/null), перезапусков: $(systemctl show -p NRestarts --value multik-tts 2>/dev/null)"
[ -n "$P" ] && [ "$P" != 0 ] && awk '/VmRSS|VmSwap/{printf "  %s %d МБ\n",$1,$2/1024}' /proc/$P/status 2>/dev/null
echo "  запущена с: $(systemctl show -p ActiveEnterTimestamp --value multik-tts 2>/dev/null | cut -c5-)"
echo "== Убитые из-за памяти (сегодня):"
journalctl -k --since today --no-pager 2>/dev/null | grep -iE "killed process|out of memory" | tail -4 | sed -E 's/.*(Killed process [0-9]+ \([^)]*\)).*anon-rss:([0-9]+)kB.*/  \1 \2 кБ/' | cut -c1-110
dmesg -T 2>/dev/null | grep -iE "killed process" | tail -3 | cut -c1-110
echo "== Журнал службы (последнее):"
journalctl -u multik-tts --since today --no-pager -o short 2>/dev/null | grep -vE "озвучено за" | tail -8 | cut -c8-140
echo "== Сколько шла озвучка фраз:"
journalctl -u multik-tts --since today --no-pager -o cat 2>/dev/null | grep "озвучено за" | tail -6 | cut -c1-70
