#!/bin/bash
# Hook Truck для Playgama: dist/hook-truck-pg → zips/hook-truck-playgama.zip. Мост — первый скрипт в head, игру грузит boot-pg.js после моста; звуки — snd/*.mp3
set -e; cd "$(dirname "$0")/.."
D=dist/hook-truck-pg Z=zips/hook-truck-playgama.zip
rm -rf $D; mkdir -p $D zips
cp g8-hook3d/physics.js g8-hook3d/sim.js g8-hook3d/levels.js g8-hook3d/r3d.js g8-hook3d/i18n.js g8-hook3d/view.js g8-hook3d/boot-pg.js vendor/three.min.js $D/
mkdir -p $D/snd && cp g8-hook3d/snd/*.mp3 g8-hook3d/snd/CREDITS.txt $D/snd/
sed 's/Promise.all(\[e\]).finally(/Promise.allSettled([e]).finally(/' vendor/playgama-bridge.js > $D/playgama-bridge.js
grep -q 'Promise.allSettled(\[e\]).finally(' $D/playgama-bridge.js || { echo 'мост не пропатчен'; exit 1; }
echo '{}' > $D/playgama-bridge-config.json
python3 - "$D/index.html" <<'PY'
import re, sys
s = open('g8-hook3d/index.html', encoding='utf8').read()
s = re.sub(r'<meta name="robots"[^>]*>\n?', '', s)
s = re.sub(r'\?v=\d+', '', s)
s = s.replace('<head>\n', '<head>\n<script src="playgama-bridge.js"></script>\n', 1)  # мост — первый скрипт в head
body = s.split('<body>', 1)
body[1] = re.sub(r'(<script src="[^"]+"></script>\n)+', '<script src="boot-pg.js"></script>\n', body[1], count=1)  # игру грузит загрузчик после моста
s = '<body>'.join(body)
open(sys.argv[1], 'w', encoding='utf8').write(s)
PY
grep -q 'playgama-bridge.js' $D/index.html && grep -q 'boot-pg.js' $D/index.html && ! grep -q 'src="view.js"' $D/index.html || { echo 'index не пропатчен'; exit 1; }
! grep -rqiE 'claude|anthropic|HOOK_TEST = true' $D/ || { echo 'следы в сборке'; exit 1; }
(cd $D && rm -f ../../$Z && zip -qr ../../$Z .)
echo "hook-truck-pg: $(stat -c %s $Z) байт"
