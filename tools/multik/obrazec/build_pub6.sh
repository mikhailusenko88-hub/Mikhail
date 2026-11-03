#!/bin/sh
# собрать pub6 из bench6.html + engine6.js + data4 (без grass.wasm — трава растёт на телефоне)
set -e
cd /home/claude/obrazec
rm -rf pub6; mkdir -p pub6/data
cp engine6.js pub6/
for f in barsik.json barsik_0.wasm pik.json pik_0.wasm ron.json ron_0.wasm env.json; do cp data4/$f pub6/data/; done
TOT=$(python3 -c "import os;print(round(sum(os.path.getsize('data4/'+f) for f in ['barsik_0.wasm','pik_0.wasm','ron_0.wasm'])/1e6,2))")
sed "s/__TOTAL__/$TOT/g" bench6.html > pub6/index.html
sed 's#https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.min.js#../three.module.min.js#' pub6/index.html > pub6/local.html
echo "total $TOT MB"; du -sh pub6
