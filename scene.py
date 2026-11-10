# Фотореалистичные интерьеры с панелями «Наш декор» (Blender 4.2, Cycles).
# Запуск: blender -b --factory-startup -P scene.py -- name=<папка> scene=lounge decor=3-7 res=1200x900 samples=160
import bpy, os, sys, math, random, time, json
import numpy as np
from mathutils import Vector

T0 = time.time()


def log(*a):
    print('[scene %5.1fs]' % (time.time() - T0), *a, flush=True)


argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = {k: v.replace('_', ' ') if k in ('look', 'view') else v for k, v in (x.split('=', 1) for x in argv if '=' in x)}
NAME = A.get('name', 'test')
SCENE = A.get('scene', 'lounge')
DECOR = A.get('decor', '3-7')
W_PX, H_PX = [int(v) for v in A.get('res', '1200x900').split('x')]
SAMPLES = int(A.get('samples', 160))
SEED = int(A.get('seed', 7))
EV = float(A.get('ev', 0))
SUN_RATIO = float(A.get('sun', 3.0))
NOISE = float(A.get('noise', 0.03))
ROOT = os.path.abspath('.')
OUT = f'{ROOT}/out/{NAME}'
os.makedirs(OUT, exist_ok=True)
random.seed(SEED)
R = math.radians

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection


# ------------------------------------------------------------------ материалы
def lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(r, g, b):
    return (lin(r), lin(g), lin(b), 1.0)


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return m, nt, out


def principled(nt, out, **kw):
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    for k, v in kw.items():
        if k in b.inputs:
            b.inputs[k].default_value = v
        else:
            log('principled: no input', k)
    return b


def load_img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = 'Non-Color'
    return im


def tex_file(aid, key):
    for ext in ('jpg', 'png'):
        p = f'{ROOT}/assets/textures/{aid}/{key}.{ext}'
        if os.path.exists(p):
            return p
    return None


def uv_mapping(nt, size_m, rot=0.0, uvmap=None):
    if uvmap:
        tc = nt.nodes.new('ShaderNodeUVMap')
        tc.uv_map = uvmap
        src = tc.outputs['UV']
    else:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        src = tc.outputs['UV']
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(src, mp.inputs['Vector'])
    s = 1.0 / size_m
    mp.inputs['Scale'].default_value = (s, s, 1.0)
    mp.inputs['Rotation'].default_value = (0.0, 0.0, rot)
    return mp.outputs['Vector']


def mat_simple(name, color, rough=0.5, metallic=0.0, bump=0.0, bump_scale=400.0, **kw):
    m, nt, out = new_mat(name)
    b = principled(nt, out, **{'Base Color': color, 'Roughness': rough, 'Metallic': metallic}, **kw)
    if bump > 0:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = bump_scale
        nz.inputs['Detail'].default_value = 6.0
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.002
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def mat_pbr(name, aid, size_m, color=None, tint=None, rough_add=0.0, rough=None, nstrength=1.0, rot=0.0, hsv=None, **kw):
    """PBR-материал из набора Poly Haven. color — заменить цвет целиком; tint — умножить."""
    m, nt, out = new_mat(name)
    b = principled(nt, out, **kw)
    vec = uv_mapping(nt, size_m, rot)
    d = tex_file(aid, 'diff')
    if color is not None:
        b.inputs['Base Color'].default_value = color
    elif d:
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = load_img(d)
        nt.links.new(vec, n.inputs['Vector'])
        last = n.outputs['Color']
        if hsv:
            h = nt.nodes.new('ShaderNodeHueSaturation')
            h.inputs['Hue'].default_value, h.inputs['Saturation'].default_value, h.inputs['Value'].default_value = hsv
            nt.links.new(last, h.inputs['Color'])
            last = h.outputs['Color']
        if tint:
            mx = nt.nodes.new('ShaderNodeMixRGB')
            mx.blend_type = 'MULTIPLY'
            mx.inputs['Fac'].default_value = 1.0
            mx.inputs['Color2'].default_value = tint
            nt.links.new(last, mx.inputs['Color1'])
            last = mx.outputs['Color']
        nt.links.new(last, b.inputs['Base Color'])
    else:
        log('mat_pbr: no diff for', aid)
    r = tex_file(aid, 'rough')
    if rough is not None:
        b.inputs['Roughness'].default_value = rough
    elif r:
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = load_img(r, True)
        nt.links.new(vec, n.inputs['Vector'])
        if rough_add:
            ad = nt.nodes.new('ShaderNodeMath')
            ad.operation = 'ADD'
            ad.use_clamp = True
            ad.inputs[1].default_value = rough_add
            nt.links.new(n.outputs['Color'], ad.inputs[0])
            nt.links.new(ad.outputs[0], b.inputs['Roughness'])
        else:
            nt.links.new(n.outputs['Color'], b.inputs['Roughness'])
    nm = tex_file(aid, 'nor_gl')
    if nm and nstrength > 0:
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = load_img(nm, True)
        nt.links.new(vec, n.inputs['Vector'])
        nn = nt.nodes.new('ShaderNodeNormalMap')
        nn.inputs['Strength'].default_value = nstrength
        nt.links.new(n.outputs['Color'], nn.inputs['Color'])
        nt.links.new(nn.outputs['Normal'], b.inputs['Normal'])
    return m


def mat_decor(decor):
    """Плёнка «под дерево» на ламели: текстура декора, лёгкий сатиновый блеск, тиснение."""
    m, nt, out = new_mat('decor_' + decor)
    b = principled(nt, out, Roughness=0.46)
    made = {}
    try:
        made = json.load(open(f'{ROOT}/assets/decor/made.json'))
    except Exception as e:  # noqa
        log('no made.json', e)
    size_m = made.get(decor, {}).get('size_mm', 1000) / 1000.0
    p = f'{ROOT}/assets/decor/{decor}_diff.jpg'
    if not os.path.exists(p):
        log('NO DECOR TEXTURE', p)
        b.inputs['Base Color'].default_value = srgb(188, 146, 119)
        return m
    vec = uv_mapping(nt, size_m)
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = load_img(p)
    nt.links.new(vec, n.inputs['Vector'])
    # небольшая разница оттенка между ламелями (вторая UV-карта хранит случайное число)
    uv2 = nt.nodes.new('ShaderNodeUVMap')
    uv2.uv_map = 'jit'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv2.outputs['UV'], sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.93
    mr.inputs['To Max'].default_value = 1.05
    nt.links.new(sep.outputs['X'], mr.inputs['Value'])
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    nt.links.new(n.outputs['Color'], hs.inputs['Color'])
    nt.links.new(mr.outputs['Result'], hs.inputs['Value'])
    nt.links.new(hs.outputs['Color'], b.inputs['Base Color'])
    bw = nt.nodes.new('ShaderNodeRGBToBW')
    nt.links.new(n.outputs['Color'], bw.inputs['Color'])
    rr = nt.nodes.new('ShaderNodeMapRange')
    rr.inputs['To Min'].default_value = 0.56
    rr.inputs['To Max'].default_value = 0.40
    nt.links.new(bw.outputs['Val'], rr.inputs['Value'])
    nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.10
    bp.inputs['Distance'].default_value = 0.0003
    nt.links.new(bw.outputs['Val'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def mat_sheer(name='sheer', transparent=0.42):
    """Тюль: часть света проходит прямо (между нитями), остальное рассеивается."""
    m, nt, out = new_mat(name)
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
    tl.inputs['Color'].default_value = (0.92, 0.91, 0.88, 1)
    df = nt.nodes.new('ShaderNodeBsdfDiffuse')
    df.inputs['Color'].default_value = (0.86, 0.85, 0.82, 1)
    m1 = nt.nodes.new('ShaderNodeMixShader')
    m1.inputs['Fac'].default_value = 0.45
    nt.links.new(tl.outputs['BSDF'], m1.inputs[1])
    nt.links.new(df.outputs['BSDF'], m1.inputs[2])
    m2 = nt.nodes.new('ShaderNodeMixShader')
    m2.inputs['Fac'].default_value = transparent
    nt.links.new(m1.outputs['Shader'], m2.inputs[1])
    nt.links.new(tr.outputs['BSDF'], m2.inputs[2])
    nt.links.new(m2.outputs['Shader'], out.inputs['Surface'])
    return m


def mat_shade(name='shade'):
    m, nt, out = new_mat(name)
    tl = nt.nodes.new('ShaderNodeBsdfTranslucent')
    tl.inputs['Color'].default_value = (0.9, 0.82, 0.68, 1)
    df = nt.nodes.new('ShaderNodeBsdfDiffuse')
    df.inputs['Color'].default_value = (0.85, 0.8, 0.7, 1)
    mx = nt.nodes.new('ShaderNodeMixShader')
    mx.inputs['Fac'].default_value = 0.5
    nt.links.new(tl.outputs['BSDF'], mx.inputs[1])
    nt.links.new(df.outputs['BSDF'], mx.inputs[2])
    nt.links.new(mx.outputs['Shader'], out.inputs['Surface'])
    return m


# ------------------------------------------------------------------ геометрия
def make_obj(name, verts, faces, mats, face_mats=None, uvs=None, jit=None, smooth=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if uvs is not None:
        ul = me.uv_layers.new(name='UVMap')
        ul.data.foreach_set('uv', [c for f in uvs for uv in f for c in uv])
    if jit is not None:
        u2 = me.uv_layers.new(name='jit')
        u2.data.foreach_set('uv', [c for f, j in zip(faces, jit) for _ in f for c in (j, 0.0)])
    for m in mats:
        me.materials.append(m)
    if face_mats is not None:
        me.polygons.foreach_set('material_index', face_mats)
    if smooth is not None:
        me.polygons.foreach_set('use_smooth', smooth)
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ax = [(0, 1), (0, 1), (0, 2), (1, 2), (0, 2), (1, 2)]
    uvs = [[(v[i][a], v[i][b]) for i in face] for face, (a, b) in zip(f, ax)]
    ob = make_obj(name, v, f, [mat], uvs=uvs)
    if bevel > 0:
        md = ob.modifiers.new('bev', 'BEVEL')
        md.width = bevel
        md.segments = 3
        md.limit_method = 'ANGLE'
    return ob


def cyl(name, x, y, z0, z1, r0, r1, mat, n=48, caps=True, smooth=True):
    v, f = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        v.append((x + r0 * math.cos(a), y + r0 * math.sin(a), z0))
        v.append((x + r1 * math.cos(a), y + r1 * math.sin(a), z1))
    for i in range(n):
        j = (i + 1) % n
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    sm = [smooth] * n
    if caps:
        f.append(tuple(2 * i for i in reversed(range(n))))
        f.append(tuple(2 * i + 1 for i in range(n)))
        sm += [False, False]
    return make_obj(name, v, f, [mat], smooth=sm)


def slat_wall(name, x0, x1, z_top, y_wall, m_wood, m_black, zbot=None, step=0.040, lam_w=0.0248, total_t=0.012, base_t=0.0042,
              tex_m=1.0, cham=0.0007):
    """Реечные панели 120×12 мм: 3 ламели на чёрной основе, шаг 40 мм, ламель 24,8 мм. Лицом к −Y.
    zbot(x) — высота низа (для арок/проёмов), по умолчанию от пола."""
    zb = zbot or (lambda x: 0.0)
    yb, yf = y_wall - base_t, y_wall - total_t
    n = int(round((x1 - x0) / step))
    x0 = (x0 + x1) / 2 - n * step / 2
    V, F, FM, UV, JIT = [], [], [], [], []

    def quad(pts, mat, uv, j):
        k = len(V)
        V.extend(pts)
        F.append((k, k + 1, k + 2, k + 3))
        FM.append(mat)
        UV.append(uv)
        JIT.append(j)

    for i in range(n):
        xa, xb = x0 + i * step, x0 + (i + 1) * step
        za, zc = zb(xa + 1e-6), zb(xb - 1e-6)
        if min(za, zc) >= z_top - 1e-4:
            continue
        # основа
        quad([(xa, yb, za), (xb, yb, zc), (xb, yb, z_top), (xa, yb, z_top)], 1, [(0, 0)] * 4, 0.5)
        xl, xr = xa + (step - lam_w) / 2, xa + (step + lam_w) / 2
        prof = [(xl, yb), (xl, yf + cham), (xl + cham, yf), (xr - cham, yf), (xr, yf + cham), (xr, yb)]
        u0, v0, j = random.random(), random.random(), random.random()
        zs = [zb(min(max(p[0], xa + 1e-6), xb - 1e-6)) for p in prof]
        for k in range(5):
            (xA, yA), (xB, yB) = prof[k], prof[k + 1]
            wood = k in (1, 2, 3)
            if wood:
                uv = [(u0 + (xA - xl) / tex_m, v0 + zs[k] / tex_m), (u0 + (xB - xl) / tex_m, v0 + zs[k + 1] / tex_m),
                      (u0 + (xB - xl) / tex_m, v0 + z_top / tex_m), (u0 + (xA - xl) / tex_m, v0 + z_top / tex_m)]
            else:
                uv = [(0, 0)] * 4
            quad([(xA, yA, zs[k]), (xB, yB, zs[k + 1]), (xB, yB, z_top), (xA, yA, z_top)], 0 if wood else 1, uv, j)
        # торец снизу (виден в проёмах)
        if max(zs) > 1e-4:
            k0 = len(V)
            V.extend([(p[0], p[1], z) for p, z in zip(prof, zs)])
            F.append(tuple(k0 + t for t in (5, 4, 3, 2, 1, 0)))
            FM.append(1)
            UV.append([(0, 0)] * 6)
            JIT.append(j)
    ob = make_obj(name, V, F, [m_wood, m_black], face_mats=FM, uvs=UV, jit=JIT)
    log('slat wall', name, 'lamellas', n, 'faces', len(F))
    return ob


def curtain(name, x, y0, y1, z0, z1, mat, fold=0.115, amp=0.032, seed=1):
    rnd = random.Random(seed)
    ph1, ph2 = rnd.random() * 6.28, rnd.random() * 6.28
    ny, nz = int((y1 - y0) / 0.008), 24
    V, F = [], []
    for j in range(nz + 1):
        t = j / nz
        z = z0 + (z1 - z0) * t
        for i in range(ny + 1):
            y = y0 + (y1 - y0) * i / ny
            w = 2 * math.pi * y / fold
            a = amp * (1.0 + 0.25 * math.sin(2 * math.pi * y / 0.63 + ph1))
            dx = a * math.sin(w + 0.9 * math.sin(2 * math.pi * y / 0.47 + ph2) + 0.35 * (1 - t) * math.sin(3.1 * y + ph1))
            V.append((x + dx * (0.75 + 0.25 * (1 - t)), y, z))
    for j in range(nz):
        for i in range(ny):
            a = j * (ny + 1) + i
            F.append((a, a + 1, a + ny + 2, a + ny + 1))
    return make_obj(name, V, F, [mat], smooth=[True] * len(F))


# ------------------------------------------------------------------ ассеты Poly Haven
def load_asset(aid, loc=(0, 0, 0), rot=0.0, scale=1.0):
    path = f'{ROOT}/assets/models/{aid}/{aid}.blend'
    if not os.path.exists(path):
        log('ASSET MISSING', aid)
        return None
    before = {im.name for im in bpy.data.images}
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None]
    for o in objs:
        col.objects.link(o)
    for im in bpy.data.images:
        if im.name in before or im.source != 'FILE':
            continue
        p = bpy.path.abspath(im.filepath)
        if not os.path.exists(p):
            cand = f'{ROOT}/assets/models/{aid}/textures/{os.path.basename(im.filepath.replace(chr(92), "/"))}'
            if os.path.exists(cand):
                im.filepath = cand
                im.reload()
            else:
                log('MISSING TEXTURE', aid, im.filepath)
    root = bpy.data.objects.new('A_' + aid, None)
    col.objects.link(root)
    tops = [o for o in objs if o.parent is None or o.parent not in objs]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == 'MESH' for c in o.bound_box]
    if not pts:
        log('asset without meshes', aid)
        return root
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    for o in tops:
        o.parent = root
        o.location = o.location - c
    root.location = loc
    root.rotation_euler = (0, 0, R(rot))
    root.scale = (scale, scale, scale)
    log('asset', aid, 'size %.2f x %.2f x %.2f' % tuple(mx - mn), 'objs', len(objs))
    return root


# ------------------------------------------------------------------ свет, камера, рендер
def setup_render():
    scene.render.engine = 'CYCLES'
    c = scene.cycles
    c.device = 'CPU'
    c.samples = SAMPLES
    c.use_adaptive_sampling = True
    c.adaptive_threshold = NOISE
    c.adaptive_min_samples = 24
    c.use_denoising = True
    try:
        c.denoiser = 'OPENIMAGEDENOISE'
        c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        c.denoising_prefilter = 'ACCURATE'
    except Exception as e:  # noqa
        log('denoiser setup', e)
    c.max_bounces = 10
    c.diffuse_bounces = 6
    c.glossy_bounces = 4
    c.transmission_bounces = 8
    c.transparent_max_bounces = 32
    c.volume_bounces = 0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    c.seed = SEED
    try:
        c.use_guiding = A.get('guide', '1') == '1'
    except Exception as e:  # noqa
        log('guiding', e)
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = W_PX, H_PX, 100
    r.use_persistent_data = True
    vs = scene.view_settings
    try:
        vs.view_transform = A.get('view', 'AgX')
    except Exception as e:  # noqa
        log('view transform', e)
    for lk in (A.get('look', 'AgX - Medium High Contrast'), 'Medium High Contrast', 'None'):
        try:
            vs.look = lk
            break
        except Exception:
            continue
    log('view', vs.view_transform, 'look', vs.look)


def setup_world(sun_dir, sun_soft=1.6):
    """Небо Нишиты без диска + отдельное солнце (сила подбирается по замеру неба)."""
    w = bpy.data.worlds.new('W')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'NISHITA'
        sky.sun_disc = False
        el = math.asin(max(0.05, -sun_dir.z))
        sky.sun_elevation = el
        sky.sun_rotation = math.atan2(-sun_dir.x, -sun_dir.y)
        sky.altitude = 100.0
        sky.air_density = 1.0
        sky.dust_density = 2.5
        sky.ozone_density = 1.0
    except Exception as e:  # noqa
        log('sky setup', e)
    wb = nt.nodes.new('ShaderNodeMixRGB')
    wb.name = 'WB'
    wb.blend_type = 'MULTIPLY'
    wb.inputs['Fac'].default_value = 1.0
    wb.inputs['Color2'].default_value = (1, 1, 1, 1)
    bg = nt.nodes.new('ShaderNodeBackground')
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(sky.outputs['Color'], wb.inputs['Color1'])
    nt.links.new(wb.outputs['Color'], bg.inputs['Color'])
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    ld = bpy.data.lights.new('Sun', 'SUN')
    ld.angle = R(sun_soft)
    ld.energy = 1.0
    sun = bpy.data.objects.new('Sun', ld)
    col.objects.link(sun)
    sun.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()
    return w, sun


def camera(loc, look, lens=30.0, fstop=None, focus=None, level=True):
    cd = bpy.data.cameras.new('Cam')
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.05, 300.0
    cam = bpy.data.objects.new('Cam', cd)
    col.objects.link(cam)
    loc, look = Vector(loc), Vector(look)
    d = look - loc
    if level:
        # камера строго по горизонту (вертикали остаются вертикальными), высоту кадра двигаем сдвигом объектива
        flat = Vector((d.x, d.y, 0)).normalized()
        cam.rotation_euler = flat.to_track_quat('-Z', 'Y').to_euler()
        dist = Vector((d.x, d.y, 0)).length
        cd.shift_y = (d.z / dist) * (lens / 36.0) if dist > 0 else 0.0
    else:
        cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.location = loc
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus or d.length
    scene.camera = cam
    return cam


def render_linear(w, h, spp, tag):
    """Быстрый черновой проход в линейном EXR -> массив (h, w, 3), строка 0 — низ кадра."""
    r, c = scene.render, scene.cycles
    keep = (r.resolution_x, r.resolution_y, c.samples, r.filepath, r.image_settings.file_format, c.adaptive_threshold)
    r.resolution_x, r.resolution_y, c.samples = w, h, spp
    c.adaptive_threshold = 0.1
    r.image_settings.file_format = 'OPEN_EXR'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.color_depth = '32'
    r.filepath = f'{OUT}/_{tag}.exr'
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(r.filepath)
    px = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, im.channels)[..., :3]
    bpy.data.images.remove(im)
    try:
        os.remove(r.filepath)
    except OSError:
        pass
    r.resolution_x, r.resolution_y, c.samples, r.filepath, r.image_settings.file_format, c.adaptive_threshold = keep
    return px


def lum(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def calibrate(world, sun, sun_dir, neutral_prefixes=('wall', 'ceil'), lamps=()):
    """1) сила солнца относительно неба, 2) баланс белого по белым стенам, 3) экспозиция."""
    cam_keep = scene.camera
    # --- замер освещённости от неба на открытой горизонтальной площадке
    pm = mat_simple('probe', (1, 1, 1, 1), rough=1.0)
    probe = box('probe', -1, 1, -1, 1, 499.9, 500.0, pm)
    cd = bpy.data.cameras.new('pc')
    cd.type = 'ORTHO'
    cd.ortho_scale = 1.0
    pc = bpy.data.objects.new('pc', cd)
    col.objects.link(pc)
    pc.location = (0, 0, 505)
    scene.camera = pc
    sun.hide_render = True
    e_sky = render_linear(16, 16, 96, 'sky').reshape(-1, 3).mean(0) * math.pi
    sun.hide_render = False
    bpy.data.objects.remove(probe)
    bpy.data.objects.remove(pc)
    scene.camera = cam_keep
    sc = np.array([1.0, 0.86, 0.70])
    sc = sc / lum(sc)
    s = SUN_RATIO * float(lum(e_sky)) / max(0.1, -sun_dir.z)
    sun.data.energy = s
    sun.data.color = tuple(float(v) for v in sc / sc.max())
    sun.data.energy = s * float(sc.max())
    log('sky irradiance', e_sky.round(3), 'sun strength', round(sun.data.energy, 3))
    # --- черновой проход: белые стены -> баланс белого и экспозиция
    pw, ph = 240, int(240 * H_PX / W_PX)
    px = render_linear(pw, ph, 48, 'pre')
    deps = bpy.context.evaluated_depsgraph_get()
    cam = scene.camera
    vf = list(cam.data.view_frame(scene=scene))

    def corner(sx, sy):
        return cam.matrix_world @ max(vf, key=lambda v: sx * v.x + sy * v.y)

    bl, br, tl = corner(-1, -1), corner(1, -1), corner(-1, 1)
    org = cam.matrix_world.translation
    mask = np.zeros((ph, pw), bool)
    for j in range(ph):
        for i in range(pw):
            p = bl + (br - bl) * ((i + 0.5) / pw) + (tl - bl) * ((j + 0.5) / ph)
            hit, loc, nor, idx, ob, mw = scene.ray_cast(deps, org, (p - org).normalized())
            if hit and ob.name.startswith(neutral_prefixes):
                mask[j, i] = True
    Y = lum(px)
    if mask.sum() > 80:
        wp = px[mask]
        yy = Y[mask]
        sel = (yy > np.percentile(yy, 25)) & (yy < np.percentile(yy, 85))
        ill = wp[sel].mean(0)
        y_ref = float(np.median(yy))
    else:
        ill = px.reshape(-1, 3).mean(0)
        y_ref = float(np.median(Y)) * 1.8
    ill = ill / lum(ill)
    target = np.array([1.035, 1.0, 0.93])           # чуть тёплый белый
    target = target / lum(target)
    gains = (target / ill) ** float(A.get('wbk', 0.85))
    gains = gains / lum(gains)
    wbn = world.node_tree.nodes['WB']
    wbn.inputs['Color2'].default_value = (float(gains[0]), float(gains[1]), float(gains[2]), 1.0)
    c0 = np.array(sun.data.color[:]) * gains
    sun.data.energy = sun.data.energy * float(c0.max())
    sun.data.color = tuple(float(v) for v in c0 / c0.max())
    key = float(A.get('key', 0.95))
    ev = math.log2(key / max(y_ref, 1e-6)) + EV
    scene.view_settings.exposure = ev
    log('white pixels', int(mask.sum()), 'illuminant', ill.round(3), 'wb gains', gains.round(3), 'wall Y', round(y_ref, 4), 'exposure', round(ev, 2))
    for ld, k in lamps:
        ld.energy = k * y_ref
    return y_ref


def render_final():
    r = scene.render
    r.image_settings.file_format = 'JPEG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.quality = 97
    r.filepath = f'{OUT}/{NAME}.jpg'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    log('final render %.1fs' % (time.time() - t), r.filepath)


# ------------------------------------------------------------------ общие детали комнаты
def room(W, D, H, win=None, m_wall=None, m_floor=None, m_ceil=None, wall_t=0.3, plinth=True):
    """Комната x 0..W, y 0..D, z 0..H. Акцентная стена — y=D. Окно — в левой стене (x=0): win=(y0, y1, z0, z1)."""
    fl = box('floor', -wall_t, W + wall_t, -wall_t, D + wall_t, -0.1, 0.0, m_floor)
    box('ceil', -wall_t, W + wall_t, -wall_t, D + wall_t, H, H + 0.1, m_ceil)
    box('wall_back', -wall_t, W + wall_t, D, D + wall_t, 0, H, m_wall)
    box('wall_front', -wall_t, W + wall_t, -wall_t, 0, 0, H, m_wall)
    box('wall_right', W, W + wall_t, 0, D, 0, H, m_wall)
    if win:
        y0, y1, z0, z1 = win
        box('wall_left_a', -wall_t, 0, 0, y0, 0, H, m_wall)
        box('wall_left_b', -wall_t, 0, y1, D, 0, H, m_wall)
        box('wall_left_top', -wall_t, 0, y0, y1, z1, H, m_wall)
        if z0 > 0:
            box('wall_left_bot', -wall_t, 0, y0, y1, 0, z0, m_wall)
        mf = mat_simple('frame', srgb(238, 238, 236), rough=0.35)
        fx0, fx1, fw = -wall_t + 0.08, -wall_t + 0.15, 0.055
        box('frame_b', fx0, fx1, y0, y1, z0, z0 + fw, mf)
        box('frame_t', fx0, fx1, y0, y1, z1 - fw, z1, mf)
        n = max(1, int(round((y1 - y0) / 0.9)))
        for i in range(n + 1):
            yy = y0 + (y1 - y0) * i / n
            box(f'frame_v{i}', fx0, fx1, max(y0, yy - fw / 2) if 0 < i < n else (yy if i == 0 else yy - fw),
                min(y1, yy + fw / 2) if 0 < i < n else (yy + fw if i == 0 else yy), z0, z1, mf)
        # подоконная плита-откос и земля за окном (чтобы снизу тоже шёл отражённый свет)
        box('outside_ground', -400, 400, -400, 400, -12.1, -12.0, mat_simple('ground', (0.16, 0.17, 0.13, 1), rough=1.0))
    else:
        box('wall_left', -wall_t, 0, 0, D, 0, H, m_wall)
    if plinth:
        mp = mat_simple('plinth', srgb(240, 240, 238), rough=0.4)
        box('plinth_r', W - 0.013, W, 0, D - 0.012, 0, 0.08, mp, bevel=0.002)
        if win:
            box('plinth_la', 0, 0.013, 0, win[0], 0, 0.08, mp, bevel=0.002)
            box('plinth_lb', 0, 0.013, win[1], D - 0.012, 0, 0.08, mp, bevel=0.002)
        else:
            box('plinth_l', 0, 0.013, 0, D - 0.012, 0, 0.08, mp, bevel=0.002)
    return fl


def books(x, y, z, n=3, rot=0.0, seed=3):
    rnd = random.Random(seed)
    cols = [srgb(52, 60, 70), srgb(196, 178, 150), srgb(120, 74, 52), srgb(225, 220, 208), srgb(72, 88, 76)]
    mp = mat_simple('pages', srgb(232, 226, 210), rough=0.9)
    zz = z
    for i in range(n):
        w, d, h = 0.20 + rnd.random() * 0.06, 0.27 + rnd.random() * 0.05, 0.022 + rnd.random() * 0.02
        ox, oy = (rnd.random() - 0.5) * 0.03, (rnd.random() - 0.5) * 0.03
        mc = mat_simple(f'book{seed}_{i}', cols[(i + seed) % len(cols)], rough=0.6)
        b = box(f'book{seed}_{i}', x - w / 2 + ox, x + w / 2 + ox, y - d / 2 + oy, y + d / 2 + oy, zz, zz + h, mc, bevel=0.0015)
        box(f'bookp{seed}_{i}', x - w / 2 + ox + 0.004, x + w / 2 + ox + 0.002, y - d / 2 + oy - 0.001, y + d / 2 + oy + 0.001, zz + 0.003,
            zz + h - 0.003, mp)
        zz += h
    return zz


def table_lamp(x, y, z, lamps):
    mb = mat_simple('lamp_base', srgb(46, 52, 48), rough=0.35)
    cyl('lamp_base', x, y, z, z + 0.03, 0.075, 0.075, mb)
    cyl('lamp_body', x, y, z + 0.03, z + 0.22, 0.06, 0.035, mb)
    cyl('lamp_stem', x, y, z + 0.22, z + 0.30, 0.008, 0.008, mat_simple('brass', srgb(170, 140, 80), rough=0.3, metallic=1.0), caps=False)
    cyl('lamp_shade', x, y, z + 0.27, z + 0.47, 0.15, 0.11, mat_shade(), caps=False)
    ld = bpy.data.lights.new('lampL', 'POINT')
    ld.shadow_soft_size = 0.03
    ld.color = (1.0, 0.72, 0.42)
    ld.energy = 5.0
    lo = bpy.data.objects.new('lampL', ld)
    col.objects.link(lo)
    lo.location = (x, y, z + 0.36)
    lamps.append((ld, float(A.get('lamp', 5.0))))


# ------------------------------------------------------------------ сцены
def scene_lounge():
    W, D, H = 4.4, 5.2, 2.7
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=srgb(236, 232, 224), rough=0.9, nstrength=0.6)
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(float(A.get('floor_rot', 90))),
                      tint=srgb(232, 222, 210))
    room(W, D, H, win=(2.3, 4.7, 0.06, 2.46), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil)
    m_wood, m_black = mat_decor(DECOR), mat_simple('pan_black', (0.007, 0.007, 0.008, 1), rough=0.8, **{'Specular IOR Level': 0.25})
    slat_wall('panels', 0.0, W, H, D, m_wood, m_black)
    # тюль и карниз
    curtain('sheer', 0.12, 2.1, 4.95, 0.012, 2.64, mat_sheer())
    box('track', 0.07, 0.17, 2.0, 5.05, 2.64, 2.67, mat_simple('track', srgb(240, 240, 238), rough=0.4))
    lamps = []
    # тумба у стены
    cab = load_asset('modern_wooden_cabinet', loc=(2.15, D - 0.012 - 0.28, 0), rot=float(A.get('cab_rot', 180)))
    top = 0.68
    yc = D - 0.012 - 0.28
    if cab is None:
        box('cab', 1.2, 3.1, D - 0.45, D - 0.012, 0.15, 0.6, mat_simple('cabm', srgb(232, 228, 220), rough=0.4), bevel=0.003)
        top = 0.6
    table_lamp(1.45, yc, top, lamps)
    zz = books(2.25, yc - 0.02, top, 3, seed=4)
    load_asset('ceramic_vase_02', loc=(2.25, yc - 0.02, zz), rot=20)
    load_asset('ceramic_vase_04', loc=(2.82, yc + 0.03, top), rot=70)
    load_asset('ceramic_vase_03', loc=(3.0, yc - 0.06, top), rot=10)
    load_asset('standing_picture_frame_02', loc=(1.85, yc + 0.04, top), rot=float(A.get('pic_rot', 12)))
    # растение у окна, кресло, столик, ковёр
    load_asset('potted_plant_01', loc=(0.72, D - 0.55, 0), rot=35)
    load_asset('mid_century_lounge_chair', loc=(3.3, 3.75, 0.012), rot=float(A.get('chair_rot', -35)))
    m_rug = mat_pbr('rug', 'hessian_230', 0.55, tint=srgb(240, 232, 218), nstrength=1.5)
    box('rug', 1.5, 4.15, 2.6, 4.45, 0.0, 0.012, m_rug, bevel=0.004)
    # свет и камера
    sun_dir = Vector((math.cos(R(30)) * math.cos(R(40)), math.cos(R(30)) * math.sin(R(40)), -math.sin(R(30))))
    az, el = float(A.get('sun_az', 40)), float(A.get('sun_el', 30))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    world, sun = setup_world(sun_dir)
    camera((2.55, 0.75, 1.22), (2.15, D, 1.02), lens=float(A.get('lens', 30)), fstop=float(A.get('fstop', 5.6)), focus=4.3)
    return world, sun, sun_dir, lamps


SCENES = {'lounge': scene_lounge}

setup_render()
world, sun, sun_dir, lamps = SCENES[SCENE]()
bpy.context.view_layer.update()
log('objects', len(scene.objects), 'scene built')
calibrate(world, sun, sun_dir, lamps=lamps)
render_final()
log('done')
