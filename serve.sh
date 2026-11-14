#!/bin/bash
# Поднять локальный сервер для тестов, если не запущен
if ! curl -s -o /dev/null http://localhost:8765/index.html; then
  pkill -f "http.server 8765" 2>/dev/null; cd /home/claude/games/dist && (nohup python3 -m http.server 8765 >/tmp/http.log 2>&1 &); sleep 1
fi
curl -s -o /dev/null -w "server %{http_code}\n" http://localhost:8765/index.html
