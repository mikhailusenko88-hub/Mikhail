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
# fb_build <папка> <zip> <реклама true|false>
fb_build() {
  local D=dist/$1 Z=zips/$2 ADS=$3
  rm -rf $D; mkdir -p $D zips
  cp online/game.js core/core.js $D/
  # мост: у гостя CrazyGames (не вошёл в аккаунт) он оставлял «Uncaught (in promise)» в консоли — гасим это ожидание
  sed 's/Promise.all(\[e\]).finally(/Promise.allSettled([e]).finally(/' vendor/playgama-bridge.js > $D/playgama-bridge.js
  grep -q 'Promise.allSettled(\[e\]).finally(' $D/playgama-bridge.js || { echo 'bridge patch failed'; exit 1; }
  echo '{}' > $D/playgama-bridge-config.json
  grep -v 'name="robots"' online/index.html | sed "s#<script src=\"core.js\"></script>#<script src=\"playgama-bridge.js\"></script>\n<script>window.FB_SERVER='$FB_WSS'; window.GAME_ADS=$ADS;</script>\n<script src=\"core.js\"></script>#" > $D/index.html
  (cd $D && rm -f ../../$Z && zip -qr ../../$Z .)
  echo $1: $(du -sh $Z | cut -f1) "(реклама: $ADS)"
}
# CrazyGames: на пробном запуске реклама отключена площадкой → кнопок «за рекламу» нет; на полном запуске FB_ADS=true
fb_build flagball flagball-arena-crazygames.zip "${FB_ADS:-false}"
# Playgama и другие площадки через мост: реклама за награду работает сразу; друзья — комната по коду
fb_build flagball-pg flagball-arena-playgama.zip true
