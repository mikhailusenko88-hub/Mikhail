# 3D-модели всех позиций «Наш декор» для дизайнеров: OBJ+MTL, FBX, DAE, GLB, DXF-профиль, превью.
# blender -b --factory-startup -P build_models.py -- [only=A703,3-7] [prev=1]
import bpy, bmesh, json, math, os, random, sys, time, shutil, re
from mathutils import Vector

T0 = time.time()
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = dict(x.split('=', 1) for x in argv if '=' in x)
ONLY = set(A['only'].split(',')) if A.get('only') else None
PREV = A.get('prev', '1') == '1'
FLAT = A.get('flat', '0') == '1'
ROOT = os.path.abspath('.')
OUT = f'{ROOT}/out/Наш декор — 3D-модели'
C = json.load(open('catalog.json', encoding='utf-8'))
TEX = json.load(open('tex_out/tex.json', encoding='utf-8'))
CAT_DIR = {'panel': '1 Панели белые под покраску', 'color': '2 Панели с декором', 'plinth': '3 Плинтусы напольные',
           'cornice': '4 Потолочные плинтусы', 'mold': '5 Молдинги', 'corner': '6 Уголки'}
R = math.radians
LOG = []


def log(*a):
    s = '[%6.1fs] ' % (time.time() - T0) + ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
us = scene.unit_settings
us.system, us.scale_length, us.length_unit = 'METRIC', 0.001, 'MILLIMETERS'
os.makedirs(OUT + '/textures', exist_ok=True)
for suf, t in TEX.items():
    shutil.copy(f'tex_out/{t["file"]}', f'{OUT}/textures/{t["file"]}')


# ---------------------------------------------------------------- материалы
def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


MATS = {}


def mat_basic(name, rgb, rough):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1)
    b.inputs['Roughness'].default_value = rough
    m.diffuse_color = (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1)
    MATS[name] = m
    return m


def mat_decor(suf):
    name = f'decor_{suf}'
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.5
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(f'{OUT}/textures/{TEX[suf]["file"]}', check_existing=True)
    nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
    MATS[name] = m
    return m


PAINT = lambda: mat_basic('paint_white', (236, 236, 233), 0.55)
BLACK = lambda: mat_basic('base_black', (20, 20, 21), 0.7)


# ---------------------------------------------------------------- профили
def clean(pts):
    out = []
    for p in pts:
        p = (round(float(p[0]), 4), round(float(p[1]), 4))
        if not out or abs(out[-1][0] - p[0]) > 1e-4 or abs(out[-1][1] - p[1]) > 1e-4:
            out.append(p)
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) < 1e-4 and abs(out[0][1] - out[-1][1]) < 1e-4:
        out.pop()
    return out


def wood_layout(series):
    """Раскладка ламелей по фото каталога: серия 2 — 2 ламели по 30 мм слева в шаге 60;
    серия 3 — 3 ламели 24,8 мм справа в шаге 40; серия 5 — 5 ламелей 12 мм справа в шаге 24."""
    if series == '2':
        return [(i * 60.0, i * 60.0 + 30.0) for i in range(2)]
    if series == '5':
        return [(i * 24.0 + 12.0, i * 24.0 + 24.0) for i in range(5)]
    return [(i * 40.0 + 15.2, i * 40.0 + 40.0) for i in range(3)]


def wood_profile(series, w=120.0, t=12.0, base=4.2):
    lams = wood_layout(series)
    xs = sorted({0.0, w} | {x for l in lams for x in l})
    segs = []
    for x0, x1 in zip(xs, xs[1:]):
        mid = (x0 + x1) / 2
        segs.append((x0, x1, t if any(a <= mid <= b for a, b in lams) else base))
    pts = [(0.0, 0.0), (w, 0.0)]
    for x0, x1, h in reversed(segs):
        pts += [(x1, h), (x0, h)]
    return clean(pts), lams


# ---------------------------------------------------------------- сетка
def extrude(name, pts, L, mapfn, matfn=None, uvfn=None, mats=()):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    n = len(pts)
    v0 = [bm.verts.new(mapfn(a, b, 0.0)) for a, b in pts]
    v1 = [bm.verts.new(mapfn(a, b, L)) for a, b in pts]
    per = [0.0]
    for i in range(1, n + 1):
        (a0, b0), (a1, b1) = pts[i - 1], pts[i % n]
        per.append(per[-1] + math.hypot(a1 - a0, b1 - b0))
    sides = []
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((v0[i], v0[j], v1[j], v1[i]))
        sides.append(f)
        f.material_index = matfn(pts[i], pts[j]) if matfn else 0
        uv = uvfn(pts[i], pts[j], L, i) if uvfn else None
        if uv is None:
            uv = [(per[i] / 1000, 0), (per[i + 1] / 1000, 0), (per[i + 1] / 1000, L / 1000), (per[i] / 1000, L / 1000)]
        for lp, u in zip(f.loops, uv):
            lp[uvl].uv = u
    caps = [bm.faces.new(list(reversed(v0))), bm.faces.new(v1)]
    bm.normal_update()
    for f in caps:
        f.material_index = matfn(None, None) if matfn else 0
    res = bmesh.ops.triangulate(bm, faces=caps, quad_method='BEAUTY', ngon_method='BEAUTY')
    for f in res['faces']:
        for lp in f.loops:
            k = v0.index(lp.vert) if lp.vert in v0 else v1.index(lp.vert)
            lp[uvl].uv = (pts[k][0] / 1000, pts[k][1] / 1000)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    capf = [f for f in res['faces'] if f.is_valid]
    # сглаживание: боковые грани гладкие, рёбра с изломом > 30° и края торцов — острые; торцы плоские
    for f in sides:
        f.smooth = not FLAT
    for f in capf:
        f.smooth = False
    for i in range(n):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[(i + 1) % n]
        d1, d2 = (bx - ax, by - ay), (cx - bx, cy - by)
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        cosang = (d1[0] * d2[0] + d1[1] * d2[1]) / (l1 * l2) if l1 and l2 else -1
        e = bm.edges.get((v0[i], v1[i]))
        if e:
            e.smooth = cosang > math.cos(R(30))
        for vv in (v0, v1):
            ce = bm.edges.get((vv[i], vv[(i + 1) % n]))
            if ce:
                ce.smooth = False
    pa = abs(0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)))
    ca = sum(f.calc_area() for f in capf) / 2
    if abs(ca - pa) > 0.01 * pa + 0.5:
        log('CAP AREA MISMATCH', name, round(pa, 2), round(ca, 2), len(capf))
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume(signed=True)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    return ob, nonman, vol


def build(name, a, it, L, prev=False):
    """Возвращает (объект, проверка, профиль для DXF, описание)."""
    c = it['c']
    if c == 'color':
        series, suf = a.split('-')
        pts, lams = wood_profile(series)
        tinfo = TEX[suf]
        rnd = random.Random(sum(ord(ch) * (i + 1) for i, ch in enumerate(a)))
        offs = [(rnd.uniform(0, tinfo['w_mm'] - 31), rnd.uniform(0, tinfo['h_mm'])) for _ in lams]

        def matfn(p, q):
            if p is None:
                return 1
            return 0 if (abs(p[1] - 12.0) < 1e-3 and abs(q[1] - 12.0) < 1e-3) else 1

        def uvfn(p, q, L_, i):
            if not (abs(p[1] - 12.0) < 1e-3 and abs(q[1] - 12.0) < 1e-3):
                return None
            k = next(k for k, (l0, l1) in enumerate(lams) if l0 - 1e-3 <= min(p[0], q[0]) and max(p[0], q[0]) <= l1 + 1e-3)
            l0 = lams[k][0]
            ou, ov = offs[k]
            u0, u1 = (p[0] - l0 + ou) / tinfo['w_mm'], (q[0] - l0 + ou) / tinfo['w_mm']
            return [(u0, ov / tinfo['h_mm']), (u1, ov / tinfo['h_mm']), (u1, (ov + L_) / tinfo['h_mm']), (u0, (ov + L_) / tinfo['h_mm'])]

        mapfn = (lambda x, t, s: (x, s, t)) if prev else (lambda x, t, s: (x, -t, s))
        ob, nm, vol = extrude(name, pts, L, mapfn, matfn, uvfn, (mat_decor(suf), BLACK()))
        return ob, nm, vol, [pts], 'panel'
    if c == 'panel':
        prof = C['prof'][a]
        w = float(it['w'])
        top = [(float(x), float(t)) for x, t in prof]
        pts = clean([(top[0][0], 0.0), (top[-1][0], 0.0)] + list(reversed(top)))
        mapfn = (lambda x, t, s: (x, s, t)) if prev else (lambda x, t, s: (x, -t, s))
        ob, nm, vol = extrude(name, pts, L, mapfn, None, None, (PAINT(),))
        return ob, nm, vol, [pts], 'panel'
    poly = it['poly']
    h = float(poly['w'])
    pts = clean([(float(u), float(t)) for u, t in poly['outer']])
    mapfn = lambda u, t, s: (s, -t, h - u)
    ob, nm, vol = extrude(name, pts, L, mapfn, None, None, (PAINT(),))
    return ob, nm, vol, [[(t, h - u) for u, t in pts]], 'linear'


# ---------------------------------------------------------------- экспорт
def select_only(ob):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def write_dxf(path, polys):
    L = ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009', '9', '$INSUNITS', '70', '4', '0', 'ENDSEC',
         '0', 'SECTION', '2', 'ENTITIES']
    for pl in polys:
        L += ['0', 'POLYLINE', '8', 'PROFILE', '66', '1', '10', '0.0', '20', '0.0', '30', '0.0', '70', '1']
        for x, y in pl:
            L += ['0', 'VERTEX', '8', 'PROFILE', '10', f'{x:.3f}', '20', f'{y:.3f}', '30', '0.0']
        L += ['0', 'SEQEND', '8', 'PROFILE']
    L += ['0', 'ENDSEC', '0', 'EOF']
    open(path, 'w', encoding='ascii').write('\n'.join(L) + '\n')


def fix_dae(path, rel):
    s = open(path, encoding='utf-8').read()
    for suf, t in TEX.items():
        s = re.sub(r'<init_from>[^<]*' + re.escape(t['file']) + '</init_from>', f'<init_from>{rel}/{t["file"]}</init_from>', s)
    open(path, 'w', encoding='utf-8').write(s)
    for t in TEX.values():
        p = os.path.join(os.path.dirname(path), t['file'])
        if os.path.exists(p):
            os.remove(p)


def export_all(ob, folder, name):
    os.makedirs(folder, exist_ok=True)
    select_only(ob)
    bpy.ops.wm.obj_export(filepath=f'{folder}/{name}.obj', export_selected_objects=True, export_materials=True,
                          path_mode='RELATIVE', export_uv=True, export_normals=True, global_scale=1.0,
                          forward_axis='NEGATIVE_Z', up_axis='Y', apply_modifiers=True)
    bpy.ops.export_scene.fbx(filepath=f'{folder}/{name}.fbx', use_selection=True, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_NONE', path_mode='RELATIVE', embed_textures=False,
                             mesh_smooth_type='FACE', axis_forward='-Z', axis_up='Y', use_mesh_modifiers=True)
    try:
        bpy.ops.wm.collada_export(filepath=f'{folder}/{name}.dae', selected=True, apply_modifiers=True,
                                  use_texture_copies=True, export_global_forward_selection='Y', export_global_up_selection='Z')
        fix_dae(f'{folder}/{name}.dae', '../../textures')
    except Exception as e:  # noqa
        log('DAE failed', name, repr(e)[:200])
    # GLB — в метрах и с уменьшенной текстурой внутри
    dup = ob.copy()
    dup.data = ob.data.copy()
    scene.collection.objects.link(dup)
    select_only(dup)
    dup.scale = (0.001, 0.001, 0.001)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    swapped = []
    for m in dup.data.materials:
        for n in (m.node_tree.nodes if m and m.use_nodes else []):
            if n.type == 'TEX_IMAGE' and n.image:
                fn = os.path.basename(n.image.filepath)
                swapped.append((n.image, n.image.filepath))
                n.image.filepath = f'{ROOT}/tex_out/small/{fn}'
                n.image.reload()
    bpy.ops.export_scene.gltf(filepath=f'{folder}/{name}.glb', export_format='GLB', use_selection=True, export_apply=True)
    for im, fp in swapped:
        im.filepath = fp
        im.reload()
    bpy.data.objects.remove(dup, do_unlink=True)


# ---------------------------------------------------------------- превью
def setup_preview_scene():
    sc = bpy.data.scenes.new('prev')
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 640, 480
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 88
    try:
        sc.view_settings.view_transform = 'AgX'
    except Exception:
        pass
    sc.unit_settings.system, sc.unit_settings.scale_length = 'METRIC', 0.001
    w = bpy.data.worlds.new('pw')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.69, 0.73, 0.77, 1)   # «Дымка»
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
    sc.world = w
    ld = bpy.data.lights.new('psun', 'SUN')
    ld.energy = 3.5
    ld.angle = R(4)
    so = bpy.data.objects.new('psun', ld)
    sc.collection.objects.link(so)
    so.rotation_euler = (R(50), R(-25), R(-35))
    cd = bpy.data.cameras.new('pcam')
    cd.lens = 50
    cam = bpy.data.objects.new('pcam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def preview(sc, cam, a, it, path):
    c = it['c']
    L = 260.0 if c in ('panel', 'color') else 220.0
    ob, nm, vol, _, kind = build(a + '_p', a, it, L, prev=True)
    scene.collection.objects.unlink(ob)
    sc.collection.objects.link(ob)
    pts = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ctr = (mn + mx) / 2
    rad = (mx - mn).length / 2
    if kind == 'panel':           # лежит лицом вверх, длина по Y, торец к камере
        d = Vector((0.45, -1.0, 0.8)).normalized()
        look = Vector((ctr.x, mn.y + (mx.y - mn.y) * 0.38, ctr.z))
    else:                        # стоит у стены (Y=0), длина по X, торец справа
        d = Vector((0.75, -1.0, 0.45)).normalized()
        look = Vector((mn.x + (mx.x - mn.x) * 0.62, ctr.y, ctr.z))
    dist = rad / math.sin(R(17)) * 0.95
    cam.location = look + d * dist
    cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start, cam.data.clip_end = 1, dist * 10
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    bpy.data.objects.remove(ob, do_unlink=True)


# ---------------------------------------------------------------- главный цикл
def safe(a):
    return a.replace('/', '-').replace(' ', '')


report = []
psc, pcam = setup_preview_scene() if PREV else (None, None)
order = ['panel', 'color', 'plinth', 'cornice', 'mold', 'corner']
items = sorted(C['items'].items(), key=lambda kv: (order.index(kv[1]['c']), kv[0]))
for a, it in items:
    if ONLY and a not in ONLY:
        continue
    if it['c'] == 'panel' and a not in C['prof']:
        report.append((a, 'нет профиля'))
        continue
    if it['c'] not in ('panel', 'color') and not it.get('poly'):
        report.append((a, 'нет профиля'))
        continue
    name = safe(a)
    folder = f'{OUT}/{CAT_DIR[it["c"]]}/{name}'
    L = float(it['l'])
    try:
        ob, nm, vol, polys, kind = build(name, a, it, L)
        export_all(ob, folder, name)
        write_dxf(f'{folder}/{name}_профиль.dxf', polys)
        if PREV:
            preview(psc, pcam, a, it, f'{folder}/{name}.jpg')
        dims = ob.dimensions
        report.append((a, f'ok nonmanifold={nm} vol={vol / 1e6:.3f}dm3 dims={dims.x:.1f}x{dims.y:.1f}x{dims.z:.1f}'))
        log(a, report[-1][1])
        bpy.data.objects.remove(ob, do_unlink=True)
    except Exception as e:  # noqa
        import traceback
        report.append((a, 'ОШИБКА ' + repr(e)[:300]))
        log('FAIL', a, traceback.format_exc()[-1500:])
open(f'{ROOT}/out/report.txt', 'w', encoding='utf-8').write('\n'.join(f'{a}\t{s}' for a, s in report) + '\n')
log('done', len(report), 'items')
