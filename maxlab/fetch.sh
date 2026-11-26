#!/usr/bin/env bash
# Достать открытый читатель .max (дополнение Blender io_scene_max, GPL) и образцы .max для разбора формата.
set -u
OUT=out; mkdir -p $OUT/src $OUT/samples
log(){ echo "$*" | tee -a $OUT/log.txt; }
B=https://projects.blender.org
# 1) исходник дополнения
git clone -q --depth 1 --filter=blob:none --sparse $B/blender/blender-addons-contrib.git c 2>>$OUT/log.txt && \
  (cd c && git sparse-checkout set io_scene_max >/dev/null 2>&1; ls -la io_scene_max >> ../$OUT/log.txt 2>&1; cp -r io_scene_max ../$OUT/src/ 2>/dev/null) || log "clone contrib: нет"
for u in "$B/blender/blender-addons-contrib/raw/branch/main/io_scene_max/import_max.py" \
         "$B/blender/blender-addons-contrib/raw/branch/main/io_scene_max/__init__.py" \
         "$B/NRGSille/blender-addons/raw/commit/2bcb045779b1b64810b0c0ea9708873804267f79/io_import_max.py"; do
  f=$OUT/src/$(echo "$u" | sed 's#.*/##; s#^#raw_#'); curl -fsSL -m 60 "$u" -o "$f" && log "ok $u $(wc -c <"$f")" || log "нет $u"
done
# страница дополнения на extensions.blender.org — ссылка на архив
curl -fsSL -m 60 https://extensions.blender.org/add-ons/io-scene-max/ -o $OUT/ext.html && \
  grep -o 'href="[^"]*download[^"]*"' $OUT/ext.html | head -5 | tee -a $OUT/log.txt | while read -r h; do
    u=$(echo "$h" | sed 's/href="//; s/"$//'); case "$u" in /*) u="https://extensions.blender.org$u";; esac
    curl -fsSL -m 120 "$u" -o $OUT/src/ext.zip && log "ok ext.zip $u" && break; done
[ -f $OUT/src/ext.zip ] && (cd $OUT/src && unzip -oq ext.zip -d ext && ls -R ext | head -30 >> ../log.txt)
# 2) образцы .max из пулл-реквестов (файлы, которые автор приложил для проверки)
for pr in "blender/blender-addons-contrib 17" "blender/blender-addons-contrib 18" "blender/blender-addons-contrib 19" \
          "blender/blender-addons-contrib 21" "blender/blender-addons-contrib 22" "blender/blender-addons 105013"; do
  set -- $pr; repo=$1; n=$2
  curl -fsSL -m 60 "$B/api/v1/repos/$repo/pulls/$n/files?limit=100" -o $OUT/pr_$n.json || { log "нет api $repo#$n"; continue; }
  python3 - "$OUT/pr_$n.json" <<'PY' >> $OUT/urls.txt
import json,sys
for f in json.load(open(sys.argv[1])):
    n=f.get("filename",""); 
    if n.lower().endswith(".max"): print(f.get("raw_url",""), n)
PY
done
sort -u $OUT/urls.txt | while read -r u n; do [ -n "$u" ] || continue
  f="$OUT/samples/$(basename "$n")"; [ -f "$f" ] && continue
  curl -fsSL -m 120 "$u" -o "$f" && log "образец $n $(wc -c <"$f")" || log "нет образца $u"; done
ls -la $OUT/samples >> $OUT/log.txt
