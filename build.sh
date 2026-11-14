#!/bin/bash
# Сборка: dist/<игра>/ — для Playgama (SDK и three.js внутри); dist-web/ — для страницы проверки (без SDK, three.js с cdnjs)
set -e
cd /home/claude/games
GAMES="g1-draw g2-descent g3-cars g4-runner g5-io"
rm -rf dist dist-web; mkdir -p dist dist-web
for g in $GAMES; do
  [ -d "$g" ] || continue
  mkdir -p dist/$g dist-web/$g
  cp $g/*.js $g/index.html dist/$g/
  cp core/core.js dist/$g/
  cp vendor/playgama-bridge.js dist/$g/
  echo '{}' > dist/$g/playgama-bridge-config.json
  if grep -q 'three.min.js' $g/index.html; then cp vendor/three.min.js dist/$g/; fi
  # веб-версия
  cp $g/*.js dist-web/$g/; cp core/core.js dist-web/$g/
  grep -v 'playgama-bridge.js' $g/index.html | sed 's#<script src="three.min.js"></script>#<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>#' > dist-web/$g/index.html
done
rm -f dist/*/*.bak dist-web/*/*.bak
[ -f hub/index.html ] && cp hub/index.html dist/index.html && cp hub/index.html dist-web/index.html
echo built: $(ls dist)

# ---- онлайн «Flagball Arena» для площадок (CrazyGames и др.): SDK внутри, сервер — защищённое подключение ----
FB_WSS="${FB_WSS:-wss://89.126.192.214/ws}"  # порт 443 (8443 на сервере занят VPN)
rm -rf dist/flagball; mkdir -p dist/flagball zips
FB_ADS="${FB_ADS:-false}"  # пробный запуск CrazyGames: реклама отключена площадкой → кнопок «за рекламу» нет; на полном запуске FB_ADS=true
cp online/game.js core/core.js dist/flagball/
# мост: у гостя CrazyGames (не вошёл в аккаунт) он оставлял «Uncaught (in promise)» в консоли — гасим это ожидание
sed 's/Promise.all(\[e\]).finally(/Promise.allSettled([e]).finally(/' vendor/playgama-bridge.js > dist/flagball/playgama-bridge.js
grep -q 'Promise.allSettled(\[e\]).finally(' dist/flagball/playgama-bridge.js || { echo 'bridge patch failed'; exit 1; }
echo '{}' > dist/flagball/playgama-bridge-config.json
grep -v 'name="robots"' online/index.html | sed "s#<script src=\"core.js\"></script>#<script src=\"playgama-bridge.js\"></script>\n<script>window.FB_SERVER='$FB_WSS'; window.GAME_ADS=$FB_ADS;</script>\n<script src=\"core.js\"></script>#" > dist/flagball/index.html
(cd dist/flagball && rm -f ../../zips/flagball-arena-crazygames.zip && zip -qr ../../zips/flagball-arena-crazygames.zip .)
echo flagball: $(du -sh zips/flagball-arena-crazygames.zip | cut -f1)
