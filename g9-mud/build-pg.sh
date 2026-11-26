#!/bin/bash
# «Mud Haul» («Грязь») для Playgama: архив dist/mud-pg → zips/mud-haul-playgama.zip (мост Playgama, без меток «не индексировать», без следов)
set -e; cd "$(dirname "$0")/.."
D=dist/mud-pg Z=zips/mud-haul-playgama.zip
rm -rf $D; mkdir -p $D zips
cp g8-hook3d/physics.js g8-hook3d/r3d.js g9-mud/mud2d.js g9-mud/i18n.js g9-mud/view2d.js g9-mud/boot-pg.js vendor/three.min.js $D/
mkdir -p $D/snd && cp g9-mud/snd/*.mp3 g9-mud/snd/CREDITS.txt $D/snd/
sed 's/Promise.all(\[e\]).finally(/Promise.allSettled([e]).finally(/' vendor/playgama-bridge.js > $D/playgama-bridge.js
grep -q 'Promise.allSettled(\[e\]).finally(' $D/playgama-bridge.js || { echo 'мост не пропатчен'; exit 1; }
echo '{}' > $D/playgama-bridge-config.json
python3 - "$D/index.html" <<'PY'
import re, sys
s = open('g9-mud/side.html', encoding='utf8').read()
s = re.sub(r'<meta name="robots"[^>]*>\n?', '', s)
s = re.sub(r'<title>[^<]*</title>', '<title>Mud Haul</title>', s)
s = s.replace('<head>\n', '<head>\n<script src="playgama-bridge.js"></script>\n', 1)  # мост — первый скрипт в head
s = re.sub(r'(<script src="[^"]+"></script>\n)+</body>', '<script src="boot-pg.js"></script>\n</body>', s)  # игру грузит загрузчик после моста
open(sys.argv[1], 'w', encoding='utf8').write(s)
PY
grep -q 'playgama-bridge.js' $D/index.html && grep -q 'boot-pg.js' $D/index.html && ! grep -q 'view2d.js' $D/index.html || { echo 'index не пропатчен'; exit 1; }
! grep -rqiE 'claude|anthropic' $D/ || { echo 'следы в сборке'; exit 1; }
(cd $D && rm -f ../../$Z && zip -qr ../../$Z .)
echo "mud-pg: $(stat -c %s $Z) байт"
