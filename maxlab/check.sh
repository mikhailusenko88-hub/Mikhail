#!/usr/bin/env bash
# Проверка файлов .max без 3ds Max и без аккаунтов:
#  1) открытый читатель io_scene_max в Blender (фоновый режим) — что прочитал + снимок (Cycles, CPU);
#  2) онлайн-просмотрщик innerscene (без регистрации) в безголовом Chromium — снимок и сообщения страницы.
# Список файлов — maxlab/check.txt: «путь_в_out_или_repo  [url для онлайн-просмотрщика]».
set -u
OUT=out; mkdir -p $OUT/shots
log(){ echo "$*" | tee -a $OUT/check.txt; }
[ -f maxlab/check.txt ] || exit 0
# Blender 4.2 LTS
V=$(curl -fsSL https://download.blender.org/release/Blender4.2/ | grep -o 'blender-4\.2\.[0-9]*-linux-x64\.tar\.xz' | sort -V | tail -1)
log "blender: $V"
curl -fsSL "https://download.blender.org/release/Blender4.2/$V" -o /tmp/b.tar.xz && tar -xf /tmp/b.tar.xz -C /tmp && BL=$(ls -d /tmp/blender-4.2*/blender | head -1)
cat > /tmp/chk.py <<'PY'
import bpy, sys, json, os, math, mathutils
f, shot = sys.argv[sys.argv.index('--')+1:][:2]
sys.path.insert(0, os.path.abspath('out/src/ext'))
from io_scene_max import import_max as im
bpy.ops.wm.read_factory_settings(use_empty=True)
res = {"file": f}
try:
    im.parent_dict.clear(); im.matrix_dict.clear()
    im.read(bpy.context, f, mathutils.Matrix.Identity(4), {'MATERIAL','UV','PRIMITIVE','EMPTY'}, False, True)
    obs = [o for o in bpy.data.objects if o.type == 'MESH']
    res["objects"] = len(obs)
    res["verts"] = sum(len(o.data.vertices) for o in obs); res["faces"] = sum(len(o.data.polygons) for o in obs)
    res["names"] = [o.name for o in obs][:20]
    res["materials"] = [m.name for m in bpy.data.materials][:20]
    if obs:
        pts = [o.matrix_world @ mathutils.Vector(c) for o in obs for c in o.bound_box]
        lo = [min(p[i] for p in pts) for i in range(3)]; hi = [max(p[i] for p in pts) for i in range(3)]
        res["bbox"] = [round(x, 3) for x in lo + hi]
        ctr = mathutils.Vector([(a+b)/2 for a, b in zip(lo, hi)]); size = max(b-a for a, b in zip(lo, hi)) or 1
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); bpy.context.scene.collection.objects.link(cam)
        cam.location = ctr + mathutils.Vector((1.2, -1.6, 1.0)) * size
        cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler(); bpy.context.scene.camera = cam
        sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); bpy.context.scene.collection.objects.link(sun)
        sun.rotation_euler = (0.7, 0.2, 0.6); sun.data.energy = 3
        w = bpy.data.worlds.new("w"); bpy.context.scene.world = w; w.color = (0.8, 0.8, 0.8)
        sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 16; sc.cycles.device = 'CPU'
        sc.render.resolution_x, sc.render.resolution_y = 800, 600; sc.render.filepath = shot
        bpy.ops.render.render(write_still=True); res["shot"] = os.path.basename(shot)
except Exception as e:
    import traceback; res["error"] = repr(e); res["trace"] = traceback.format_exc()[-1500:]
print("RESULT " + json.dumps(res, ensure_ascii=False))
PY
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1 || log "playwright: не встал"
cat > /tmp/web.py <<'PY'
import sys, asyncio
from playwright.async_api import async_playwright
url, shot = sys.argv[1], sys.argv[2]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = await b.new_page(viewport={"width": 1200, "height": 900}); msgs = []
        pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text}"[:300]))
        pg.on("pageerror", lambda e: msgs.append(f"pageerror: {e}"[:300]))
        await pg.goto(url, wait_until="networkidle", timeout=90000); await pg.wait_for_timeout(25000)
        await pg.screenshot(path=shot)
        txt = (await pg.inner_text("body"))[:1500].replace("\n", " | ")
        print("WEB", url); print("TEXT", txt)
        for m in msgs[:30]: print("MSG", m)
        await b.close()
asyncio.run(main())
PY
grep -v '^#' maxlab/check.txt | while read -r f url; do [ -n "$f" ] || continue
  n=$(basename "$f" .max | tr ' ' '_')
  if [ -n "${BL:-}" ] && [ -f "$f" ]; then
    timeout 600 "$BL" -b -noaudio --python /tmp/chk.py -- "$f" "$PWD/$OUT/shots/blender_$n.png" 2>&1 | grep -E "^RESULT|Error|error" | head -20 >> $OUT/check.txt
  else log "нет файла или Blender: $f"; fi
  if [ -n "$url" ]; then
    timeout 200 python3 /tmp/web.py "https://www.innerscene.com/tools/max-viewer?embedded=1&url=$url" "$OUT/shots/innerscene_$n.png" >> $OUT/check.txt 2>&1 || log "innerscene: ошибка $n"
  fi
done
