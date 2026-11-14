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
