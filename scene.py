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
SUN_RATIO = float(A.get('sun', 1.8))
NOISE = float(A.get('noise', 0.03))
NEUTRAL = ('wall', 'ceil')        # по каким объектам меряем баланс белого (сцена может сузить список)
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
        # основа (в проёмах дробим, чтобы низ шёл по дуге, а не по хорде)
        nsub = 8 if (zbot and max(za, zc) > 1e-4) else 1
        for q in range(nsub):
            xq0, xq1 = xa + (xb - xa) * q / nsub, xa + (xb - xa) * (q + 1) / nsub
            zq0 = zb(min(max(xq0, xa + 1e-6), xb - 1e-6))
            zq1 = zb(min(max(xq1, xa + 1e-6), xb - 1e-6))
            quad([(xq0, yb, zq0), (xq1, yb, zq1), (xq1, yb, z_top), (xq0, yb, z_top)], 1, [(0, 0)] * 4, 0.5)
        xl, xr = xa + (step - lam_w) / 2, xa + (step + lam_w) / 2
        prof = [(xl, yb), (xl, yf + cham), (xl + cham, yf), (xr - cham, yf), (xr, yf + cham), (xr, yb)]
        u0, v0, j = random.random(), random.random(), random.random()
        zs = [zb(min(max(p[0], xa + 1e-6), xb - 1e-6)) for p in prof]
        for k in range(5):
            (xA, yA), (xB, yB) = prof[k], prof[k + 1]
            wood = k in (1, 2, 3)
            if k == 2 and zbot and max(zs) > 1e-4:
                for q in range(4):
                    xq0, xq1 = xA + (xB - xA) * q / 4, xA + (xB - xA) * (q + 1) / 4
                    zq0, zq1 = zb(xq0), zb(xq1)
                    uv = [(u0 + (xq0 - xl) / tex_m, v0 + zq0 / tex_m), (u0 + (xq1 - xl) / tex_m, v0 + zq1 / tex_m),
                          (u0 + (xq1 - xl) / tex_m, v0 + z_top / tex_m), (u0 + (xq0 - xl) / tex_m, v0 + z_top / tex_m)]
                    quad([(xq0, yA, zq0), (xq1, yA, zq1), (xq1, yA, z_top), (xq0, yA, z_top)], 0, uv, j)
                continue
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


def reeded_wall(name, x0, x1, z_top, y_wall, mat, zbot=None, pitch=0.020, t_min=0.00822, t_max=0.012, seg=16):
    """Панель A910 «волна»: полукруглые валики шагом 20 мм (9 на панели 180 мм), толщина 8,2…12 мм. Лицом к −Y."""
    zb = zbot or (lambda x: 0.0)
    h = t_max - t_min
    rr = ((pitch / 2) ** 2 + h * h) / (2 * h)
    n = int(math.ceil((x1 - x0) / pitch - 1e-6))
    V, F = [], []
    for i in range(n):
        xa = x0 + i * pitch
        xb = min(xa + pitch, x1)
        base = len(V)
        cnt = 0
        for k in range(seg + 1):
            x = xa + pitch * k / seg
            if x > xb + 1e-9:
                break
            t = t_min + math.sqrt(max(0.0, rr * rr - (x - xa - pitch / 2) ** 2)) - (rr - h)
            z0 = zb(min(max(x, xa + 1e-6), xb - 1e-6))
            if z0 >= z_top - 1e-4:
                z0 = z_top
            V.append((x, y_wall - t, z0))
            V.append((x, y_wall - t, z_top))
            cnt += 1
        for k in range(cnt - 1):
            if V[base + 2 * k][2] >= z_top - 1e-4 and V[base + 2 * k + 2][2] >= z_top - 1e-4:
                continue
            F.append((base + 2 * k, base + 2 * k + 2, base + 2 * k + 3, base + 2 * k + 1))
    ob = make_obj(name, V, F, [mat], smooth=[True] * len(F))
    log('reeded wall', name, 'ribs', n, 'faces', len(F))
    return ob


A703 = [[0.0, 6.99], [9.97, 15.0], [80.0, 15.0], [80.0, 9.82], [65.01, 9.82], [65.01, 0.0], [60.92, 0.0], [60.73, 0.57], [60.11, 0.93],
        [59.41, 0.74], [59.17, 0.47], [59.04, 0.0], [54.78, 0.0], [54.78, 9.82], [13.28, 9.79], [12.37, 9.54], [11.57, 9.08],
        [10.66, 8.05], [10.3, 7.2], [10.17, 6.25], [10.17, 0.0], [5.97, 0.0], [5.7, 0.66], [5.16, 0.93], [4.45, 0.74], [4.16, 0.36],
        [4.09, 0.0], [0.0, 0.0]]      # контур сечения плинтуса A703: [от верха вниз, мм; толщина от стены, мм]
PL_FACE = [(0.015, 0.0), (0.015, 0.07003), (0.00699, 0.080), (0.0, 0.080)]   # видимая часть: (вылет от стены, высота)


def plinth_run(name, p0, p1, normal, mat, miter0=False, miter1=False):
    """Плинтус A703 вдоль стены от p0 до p1 (точки на полу у стены), normal — в комнату. miter — запил 45° во внутренний угол."""
    p0, p1, nrm = Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0)), Vector((normal[0], normal[1], 0)).normalized()
    d = (p1 - p0).normalized()
    V, F = [], []
    for (dep, z) in PL_FACE:
        a = p0 + nrm * dep + d * (dep if miter0 else 0.0)
        b = p1 + nrm * dep - d * (dep if miter1 else 0.0)
        V.append((a.x, a.y, z))
        V.append((b.x, b.y, z))
    flip = d.cross(Vector((0, 0, 1))).dot(nrm) < 0
    for k in range(len(PL_FACE) - 1):
        q = (2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2)
        F.append(q if not flip else q[::-1])
    return make_obj(name, V, F, [mat])


def plinth_piece(name, loc, rot, length, mat):
    """Отрезок плинтуса лежит лицом вверх, виден торец с кабель-каналом."""
    pts = [(p[0] / 1000.0, p[1] / 1000.0) for p in A703]
    n = len(pts)
    V = [(0.0, u, t) for (u, t) in pts] + [(length, u, t) for (u, t) in pts]
    F = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for k in range(n):
        j = (k + 1) % n
        F.append((k, n + k, n + j, j))
    ob = make_obj(name, V, F, [mat])
    try:
        ob.data.validate()
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
    except Exception as e:  # noqa
        log('plinth piece normals', e)
    ob.location = loc
    ob.rotation_euler = (0, 0, R(rot))
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
    try:
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        objs = [o for o in dst.objects if o is not None]
        for o in objs:
            col.objects.link(o)
    except Exception as e:  # noqa — файл сохранён более новым Blender: берём glTF
        g = f'{ROOT}/assets/models/{aid}/{aid}.gltf'
        log('blend failed for', aid, '-> gltf', os.path.exists(g), str(e)[:80])
        if not os.path.exists(g):
            return None
        had = {o.name for o in bpy.data.objects}
        bpy.ops.import_scene.gltf(filepath=g)
        objs = [o for o in bpy.data.objects if o.name not in had]
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
    c.transparent_max_bounces = 16
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


def calibrate(world, sun, sun_dir, neutral_prefixes=('wall', 'ceil'), lamps=(), cal_cam=None):
    """1) сила солнца относительно неба, 2) баланс белого по белым стенам, 3) экспозиция.
    cal_cam — общий план сцены: по нему меряем свет, даже если снимаем крупный план."""
    final_cam = scene.camera
    if cal_cam is not None:
        scene.camera = cal_cam
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
    key = float(A.get('key', 1.05))
    ev = math.log2(key / max(y_ref, 1e-6)) + EV
    scene.view_settings.exposure = ev
    log('white pixels', int(mask.sum()), 'illuminant', ill.round(3), 'wb gains', gains.round(3), 'wall Y', round(y_ref, 4), 'exposure', round(ev, 2))
    for ld, k in lamps:
        ld.energy = k * y_ref
    scene.camera = final_cam
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


def credenza(x0, x1, y_back, z0=0.17, h=0.46, depth=0.42, n_doors=4, color=None):
    """Тумба: матовая эмаль, фасады без ручек с тонкими зазорами, чёрные металлические опоры. Возвращает высоту столешницы."""
    mc = mat_simple('cab_lacquer', color or srgb(232, 228, 219), rough=0.36, bump=0.015, bump_scale=900.0)
    yf, dt, gap, top_t = y_back - depth, 0.019, 0.003, 0.022
    box('cab_body', x0, x1, yf + dt + 0.002, y_back, z0, z0 + h, mc, bevel=0.0015)
    box('cab_top', x0 - 0.004, x1 + 0.004, yf - 0.004, y_back, z0 + h, z0 + h + top_t, mc, bevel=0.002)
    dw = (x1 - x0 - gap * (n_doors - 1)) / n_doors
    for i in range(n_doors):
        xa = x0 + i * (dw + gap)
        box(f'cab_door{i}', xa, xa + dw, yf, yf + dt, z0 + 0.002, z0 + h - 0.003, mc, bevel=0.0015)
    ml = mat_simple('cab_legs', (0.012, 0.012, 0.013, 1), rough=0.42, metallic=1.0)
    for k, xx in enumerate((x0 + 0.20, x1 - 0.20 - 0.018)):
        box(f'cab_leg{k}a', xx, xx + 0.018, yf + 0.05, yf + 0.068, 0.018, z0, ml)
        box(f'cab_leg{k}b', xx, xx + 0.018, y_back - 0.068, y_back - 0.05, 0.018, z0, ml)
        box(f'cab_leg{k}c', xx, xx + 0.018, yf + 0.05, y_back - 0.05, 0.0, 0.018, ml)
    return z0 + h + top_t


def bench(x0, x1, y_back, depth=0.36, z=0.44, wood_id='oak_veneer_01'):
    mw = mat_pbr('bench_wood', wood_id, 1.83, rough=0.45, tint=srgb(214, 190, 160))
    box('bench_seat', x0, x1, y_back - depth, y_back, z - 0.04, z, mw, bevel=0.003)
    ml = mat_simple('bench_legs', (0.012, 0.012, 0.013, 1), rough=0.42, metallic=1.0)
    for k, xx in enumerate((x0 + 0.10, x1 - 0.10 - 0.02)):
        box(f'bn{k}a', xx, xx + 0.02, y_back - depth + 0.03, y_back - depth + 0.05, 0.02, z - 0.04, ml)
        box(f'bn{k}b', xx, xx + 0.02, y_back - 0.05, y_back - 0.03, 0.02, z - 0.04, ml)
        box(f'bn{k}c', xx, xx + 0.02, y_back - depth + 0.03, y_back - 0.03, 0.0, 0.02, ml)
    return z


def arch_wall(name, x_from, x_to, a, b, hj, y0, T, H, mat, seg=0.01):
    """Стена толщиной T (y0..y0+T) с арочным проёмом a..b: прямые откосы до hj, выше — полукруг."""
    c, rr = (a + b) / 2, (b - a) / 2

    def zb(x):
        return hj + math.sqrt(max(0.0, rr * rr - (x - c) ** 2)) if a - 1e-9 <= x <= b + 1e-9 else 0.0

    V, F, SM, UV = [], [], [], []

    def quad(pts, uv, sm=False):
        k = len(V)
        V.extend(pts)
        F.append((k, k + 1, k + 2, k + 3))
        SM.append(sm)
        UV.append(uv)

    def colm(xa, xb, za, zc):
        quad([(xa, y0, za), (xb, y0, zc), (xb, y0, H), (xa, y0, H)], [(xa, za), (xb, zc), (xb, H), (xa, H)])
        quad([(xb, y0 + T, zc), (xa, y0 + T, za), (xa, y0 + T, H), (xb, y0 + T, H)], [(xb, zc), (xa, za), (xa, H), (xb, H)])

    colm(x_from, a, 0.0, 0.0)
    colm(b, x_to, 0.0, 0.0)
    n = int(round((b - a) / seg))
    xi = [a + (b - a) * k / n for k in range(n + 1)]
    for k in range(n):
        colm(xi[k], xi[k + 1], zb(xi[k]), zb(xi[k + 1]))
    strip = [(a, 0.0)] + [(x, zb(x)) for x in xi] + [(b, 0.0)]
    base = len(V)
    s_len = 0.0
    lens = [0.0]
    for j in range(1, len(strip)):
        s_len += math.hypot(strip[j][0] - strip[j - 1][0], strip[j][1] - strip[j - 1][1])
        lens.append(s_len)
    for (x, z) in strip:
        V.append((x, y0, z))
        V.append((x, y0 + T, z))
    for j in range(len(strip) - 1):
        F.append((base + 2 * j, base + 2 * j + 1, base + 2 * j + 3, base + 2 * j + 2))
        SM.append(True)
        UV.append([(lens[j], 0.0), (lens[j], T), (lens[j + 1], T), (lens[j + 1], 0.0)])
    ob = make_obj(name, V, F, [mat], uvs=UV, smooth=SM)
    return ob, zb


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


def panel_piece(name, loc, rot, length, step=0.040, lam_w=0.0248, total_t=0.012, base_t=0.0042, n=3):
    """Отрезок реечной панели (3 ламели на чёрной основе) лежит лицом вверх: виден торец."""
    m_wood = bpy.data.materials.get('decor_' + DECOR) or mat_decor(DECOR)
    m_black = bpy.data.materials.get('pan_black') or mat_simple('pan_black', (0.007, 0.007, 0.008, 1), rough=0.8,
                                                                **{'Specular IOR Level': 0.25})
    w = n * step
    V, F, FM, UV, JIT = [], [], [], [], []

    def face(pts, mat, uv=None, j=0.5):
        k = len(V)
        V.extend(pts)
        F.append(tuple(range(k, k + len(pts))))
        FM.append(mat)
        UV.append(uv or [(0, 0)] * len(pts))
        JIT.append(j)

    L = length
    # основа: коробка 0..w × 0..L × 0..base_t (ось X — поперёк, Y — вдоль)
    face([(0, 0, 0), (0, L, 0), (w, L, 0), (w, 0, 0)], 1)
    face([(0, 0, base_t), (w, 0, base_t), (w, L, base_t), (0, L, base_t)], 1)
    face([(0, 0, 0), (w, 0, 0), (w, 0, base_t), (0, 0, base_t)], 1)
    face([(w, L, 0), (0, L, 0), (0, L, base_t), (w, L, base_t)], 1)
    face([(0, L, 0), (0, 0, 0), (0, 0, base_t), (0, L, base_t)], 1)
    face([(w, 0, 0), (w, L, 0), (w, L, base_t), (w, 0, base_t)], 1)
    for i in range(n):
        xl = i * step + (step - lam_w)
        xr = xl + lam_w
        u0, v0, j = random.random(), random.random(), random.random()
        uv = [(u0, v0), (u0 + lam_w, v0), (u0 + lam_w, v0 + L), (u0, v0 + L)]
        face([(xl, 0, total_t), (xr, 0, total_t), (xr, L, total_t), (xl, L, total_t)], 0, uv, j)
        face([(xl, 0, base_t), (xr, 0, base_t), (xr, 0, total_t), (xl, 0, total_t)], 1)
        face([(xr, L, base_t), (xl, L, base_t), (xl, L, total_t), (xr, L, total_t)], 1)
        face([(xl, L, base_t), (xl, 0, base_t), (xl, 0, total_t), (xl, L, total_t)], 1)
        face([(xr, 0, base_t), (xr, L, base_t), (xr, L, total_t), (xr, 0, total_t)], 1)
    ob = make_obj(name, V, F, [m_wood, m_black], face_mats=FM, uvs=UV, jit=JIT)
    try:
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.to_mesh(ob.data)
        bm.free()
    except Exception as e:  # noqa
        log('piece weld', e)
    md = ob.modifiers.new('bev', 'BEVEL')
    md.width = 0.0005
    md.segments = 2
    md.limit_method = 'ANGLE'
    ob.location = loc
    ob.rotation_euler = (0, 0, R(rot))
    return ob


def reeded_piece(name, loc, rot, length, mat, pitch=0.020, t_min=0.00822, t_max=0.012, n=9, seg=12):
    """Отрезок панели A910 лежит лицом вверх: виден торец с валиками."""
    h = t_max - t_min
    rr = ((pitch / 2) ** 2 + h * h) / (2 * h)
    w, L = n * pitch, length
    V, F, SM = [], [], []
    prof = []
    for i in range(n):
        base = len(V)
        for k in range(seg + 1):
            x = i * pitch + pitch * k / seg
            t = t_min + math.sqrt(max(0.0, rr * rr - (x - i * pitch - pitch / 2) ** 2)) - (rr - h)
            V.append((x, 0.0, t))
            V.append((x, L, t))
            prof.append((x, t))
        for k in range(seg):
            F.append((base + 2 * k, base + 2 * k + 2, base + 2 * k + 3, base + 2 * k + 1))
            SM.append(True)

    def flat(pts):
        k = len(V)
        V.extend(pts)
        F.append(tuple(range(k, k + len(pts))))
        SM.append(False)

    flat([(0, 0, 0), (0, L, 0), (w, L, 0), (w, 0, 0)])
    flat([(0, L, 0), (0, 0, 0), (0, 0, t_min), (0, L, t_min)])
    flat([(w, 0, 0), (w, L, 0), (w, L, t_min), (w, 0, t_min)])
    flat([(0, 0, 0), (w, 0, 0)] + [(x, 0.0, t) for x, t in reversed(prof)])
    flat([(w, L, 0), (0, L, 0)] + [(x, L, t) for x, t in prof])
    ob = make_obj(name, V, F, [mat], smooth=SM)
    ob.location = loc
    ob.rotation_euler = (0, 0, R(rot))
    return ob


def hexcol(h):
    h = h.lstrip('#')
    return srgb(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def panel_wall(x0, x1, z_top, y_wall, zbot=None):
    """Стена из панелей выбранного артикула: реечные «под дерево» (3-7, 3-15, 3-9) или A910 под покраску."""
    if DECOR.upper() == 'A910':
        mp = mat_simple('a910_paint', hexcol(A.get('paint', 'EFEEEA')), rough=float(A.get('paint_rough', 0.55)), bump=0.02, bump_scale=1500.0)
        return reeded_wall('panels', x0, x1, z_top, y_wall, mp, zbot=zbot)
    m_wood = mat_decor(DECOR)
    m_black = mat_simple('pan_black', (0.007, 0.007, 0.008, 1), rough=0.8, **{'Specular IOR Level': 0.25})
    return slat_wall('panels', x0, x1, z_top, y_wall, m_wood, m_black, zbot=zbot)


# ------------------------------------------------------------------ сцены
def scene_lounge():
    W, D, H = 4.4, 5.2, 2.7
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=srgb(236, 232, 224), rough=0.9, nstrength=0.6)
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(float(A.get('floor_rot', 90))),
                      tint=srgb(232, 222, 210))
    room(W, D, H, win=(2.3, 4.7, 0.06, 2.46), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil)
    panel_wall(0.0, W, H, D)
    # тюль и карниз
    curtain('sheer', 0.12, 2.1, 4.95, 0.012, 2.64, mat_sheer())
    box('track', 0.07, 0.17, 2.0, 5.05, 2.64, 2.67, mat_simple('track', srgb(240, 240, 238), rough=0.4))
    lamps = []
    # тумба у стены
    yc = D - 0.012 - 0.015 - 0.21
    if A.get('cab', 'proc') == 'asset':
        load_asset('modern_wooden_cabinet', loc=(2.15, D - 0.012 - 0.28, 0), rot=float(A.get('cab_rot', 180)))
        top = 0.68
    else:
        top = credenza(1.2, 3.1, D - 0.012 - 0.015, color=hexcol(A['cabcol']) if 'cabcol' in A else None)
    if A.get('tv') == '1':
        # ТВ-зона: телевизор на стене, на тумбе минимум вещей
        ms = mat_simple('tv_screen', (0.006, 0.006, 0.007, 1), rough=0.42, **{'Specular IOR Level': 0.35})
        mb = mat_simple('tv_body', (0.01, 0.01, 0.011, 1), rough=0.4)
        tw, th, tz = 1.45, 0.83, 1.32
        box('tv_body', 2.15 - tw / 2, 2.15 + tw / 2, D - 0.012 - 0.045, D - 0.012 - 0.012, tz - th / 2, tz + th / 2, mb, bevel=0.002)
        box('tv_screen', 2.15 - tw / 2 + 0.008, 2.15 + tw / 2 - 0.008, D - 0.012 - 0.0465, D - 0.012 - 0.045, tz - th / 2 + 0.008, tz + th / 2 - 0.012, ms)
        zz = books(1.55, yc - 0.02, top, 3, seed=4)
        load_asset('ceramic_vase_02', loc=(1.55, yc - 0.02, zz), rot=20)
        load_asset('ceramic_vase_03', loc=(2.85, yc - 0.03, top), rot=10)
        load_asset('potted_plant_04', loc=(2.62, yc + 0.02, top), rot=40)
    else:
        table_lamp(1.45, yc, top, lamps)
        zz = books(2.25, yc - 0.02, top, 3, seed=4)
        load_asset('ceramic_vase_02', loc=(2.25, yc - 0.02, zz), rot=20)
        load_asset('ceramic_vase_04', loc=(2.82, yc + 0.03, top), rot=70)
        load_asset('ceramic_vase_03', loc=(3.0, yc - 0.06, top), rot=10)
        load_asset('standing_picture_frame_02', loc=(1.85, yc + 0.04, top), rot=float(A.get('pic_rot', 12)))
    # растение у окна, кресло, ковёр
    load_asset('potted_plant_01', loc=(0.72, D - 0.55, 0), rot=35)
    chair = A.get('chair', 'mid_century_lounge_chair')
    cx, cy = [float(v) for v in A.get('chair_at', '3.22,3.75').split(',')]
    load_asset(chair, loc=(cx, cy, 0.012), rot=float(A.get('chair_rot', -35 if chair.startswith('mid') else 150)))
    m_rug = mat_pbr('rug', 'hessian_230', 0.55, tint=srgb(240, 232, 218), nstrength=1.5)
    box('rug', 1.5, 4.15, 2.6, 4.45, 0.0, 0.012, m_rug, bevel=0.004)
    # свет и камера
    sun_dir = Vector((math.cos(R(30)) * math.cos(R(40)), math.cos(R(30)) * math.sin(R(40)), -math.sin(R(30))))
    az, el = float(A.get('sun_az', 40)), float(A.get('sun_el', 30))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    world, sun = setup_world(sun_dir)
    cal = camera((2.55, 0.75, 1.22), (2.15, D, 1.02), lens=float(A.get('lens', 30)), fstop=float(A.get('fstop', 5.6)), focus=4.3)
    cm = A.get('cam', 'main')
    if cm == 'close':
        camera((1.85, 3.95, 1.12), (2.72, D, 0.95), lens=50, fstop=5.6, focus=1.55)
    elif cm == 'macro':
        camera((3.0, 4.55, 1.2), (3.75, D - 0.012, 1.15), lens=60, fstop=8.0, focus=0.98)
    elif cm == 'macro2':        # участок в косом солнце над тумбой
        camera((2.35, 4.62, 1.47), (1.75, D - 0.012, 1.42), lens=60, fstop=8.0, focus=0.83)
    elif cm == 'mid':           # средний план: тумба с вещами, рельеф стены читается
        camera((2.2, 2.6, 1.1), (2.1, D, 0.95), lens=35, fstop=5.6, focus=2.4)
    elif cm == 'diag':          # по диагонали от правой стены: окно, растение, тумба, кресло
        camera((3.95, 1.25, 1.2), (1.5, D, 1.0), lens=30, fstop=5.6, focus=4.2)
    elif cm == 'sample':
        # образец панели на светлом столике, стена с тумбой — фоном
        mt = mat_simple('tbl', hexcol(A['tblcol']) if 'tblcol' in A else srgb(236, 233, 226), rough=0.5, bump=0.01, bump_scale=700.0)
        box('tbl_top', 1.55, 2.75, 2.75, 3.45, 0.70, 0.73, mt, bevel=0.003)
        ml = mat_simple('tbl_legs', (0.012, 0.012, 0.013, 1), rough=0.42, metallic=1.0)
        for k, (lx, ly) in enumerate(((1.6, 2.8), (2.68, 2.8), (1.6, 3.38), (2.68, 3.38))):
            box(f'tbl_leg{k}', lx, lx + 0.02, ly, ly + 0.02, 0, 0.70, ml)
        pr = float(A.get('piece_rot', 30))
        if DECOR.upper() == 'A910':
            mpc = bpy.data.materials.get('a910_paint')
            reeded_piece('piece_a', (1.93, 2.95, 0.73), pr, 0.46, mpc)
            reeded_piece('piece_b', (1.93 + 0.21 * math.cos(R(pr)) + 0.07 * math.sin(R(pr)), 2.95 + 0.21 * math.sin(R(pr)) - 0.07 * math.cos(R(pr)), 0.73),
                         pr, 0.38, mpc)
        else:
            panel_piece('piece_a', (2.0, 2.95, 0.73), pr, 0.46)
            panel_piece('piece_b', (2.0 + 0.145 * math.cos(R(pr)) + 0.07 * math.sin(R(pr)), 2.95 + 0.145 * math.sin(R(pr)) - 0.07 * math.cos(R(pr)), 0.73),
                        pr, 0.38)
        load_asset('potted_plant_04', loc=(1.72, 3.3, 0.73), rot=20)
        camera((2.04, 2.5, 0.95), (2.1, 3.02, 0.735), lens=50, fstop=float(A.get('fstop', 5.6)), focus=0.52, level=False)
    return world, sun, sun_dir, lamps, cal


def left_wall_with_windows(D, H, wins, m_wall, wall_t=0.3):
    mf = mat_simple('frame', srgb(238, 238, 236), rough=0.35)
    y = 0.0
    for k, (y0, y1, z0, z1) in enumerate(wins):
        box(f'wall_left_{k}', -wall_t, 0, y, y0, 0, H, m_wall)
        box(f'wall_left_top{k}', -wall_t, 0, y0, y1, z1, H, m_wall)
        if z0 > 0:
            box(f'wall_left_bot{k}', -wall_t, 0, y0, y1, 0, z0, m_wall)
        fx0, fx1, fw = -wall_t + 0.08, -wall_t + 0.15, 0.055
        box(f'frame_b{k}', fx0, fx1, y0, y1, z0, z0 + fw, mf)
        box(f'frame_t{k}', fx0, fx1, y0, y1, z1 - fw, z1, mf)
        n = max(1, int(round((y1 - y0) / 0.9)))
        for i in range(n + 1):
            yy = y0 + (y1 - y0) * i / n
            ya = yy if i == 0 else (yy - fw if i == n else yy - fw / 2)
            box(f'frame_v{k}_{i}', fx0, fx1, ya, ya + fw, z0, z1, mf)
        y = y1
    box('wall_left_end', -wall_t, 0, y, D, 0, H, m_wall)


def scene_arch():
    W, Y0, T, D2, H = 4.0, 4.2, 0.16, 8.2, 2.7
    wt = 0.3
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=srgb(236, 232, 224), rough=0.9, nstrength=0.6)
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(float(A.get('floor_rot', 90))),
                      tint=srgb(232, 222, 210))
    box('floor', -wt, W + wt, -wt, D2 + wt, -0.1, 0.0, m_floor)
    box('ceil', -wt, W + wt, -wt, D2 + wt, H, H + 0.1, m_ceil)
    box('wall_front', -wt, W + wt, -wt, 0, 0, H, m_wall)
    box('wall_far', -wt, W + wt, D2, D2 + wt, 0, H, m_wall)
    box('wall_right', W, W + wt, 0, D2, 0, H, m_wall)
    left_wall_with_windows(D2, H, [(1.3, 3.5, 0.06, 2.46), (Y0 + T + 0.9, D2 - 0.9, 0.06, 2.46)], m_wall, wt)
    box('outside_ground', -400, 400, -400, 400, -12.1, -12.0, mat_simple('ground', (0.16, 0.17, 0.13, 1), rough=1.0))
    a, b, hj = 2.0, 3.0, float(A.get('hj', 1.62))
    ob, zb = arch_wall('wall_arch', -wt, W + wt, a, b, hj, Y0, T, H, m_wall)
    panel_wall(0.0, W, H, Y0, zbot=lambda x: zb(x) if a < x < b else 0.0)
    mp = mat_simple('plinth', srgb(240, 240, 238), rough=0.4)
    box('plinth_r', W - 0.013, W, 0, Y0 - 0.012, 0, 0.08, mp, bevel=0.002)
    box('plinth_r2', W - 0.013, W, Y0 + T, D2, 0, 0.08, mp, bevel=0.002)
    box('plinth_far', 0, W, D2 - 0.013, D2, 0, 0.08, mp, bevel=0.002)
    box('plinth_b1', 0, a, Y0 + T, Y0 + T + 0.013, 0, 0.08, mp, bevel=0.002)
    box('plinth_b2', b, W, Y0 + T, Y0 + T + 0.013, 0, 0.08, mp, bevel=0.002)
    sh = mat_sheer()
    curtain('sheer1', 0.12, 1.1, 3.75, 0.012, 2.64, sh, seed=1)
    curtain('sheer2', 0.12, Y0 + T + 0.7, D2 - 0.7, 0.012, 2.64, sh, seed=2)
    mt = mat_simple('track', srgb(240, 240, 238), rough=0.4)
    box('track1', 0.07, 0.17, 1.0, 3.85, 2.64, 2.67, mt)
    box('track2', 0.07, 0.17, Y0 + T + 0.6, D2 - 0.6, 2.64, 2.67, mt)
    lamps = []
    # перед стеной: скамья, корзина, книги, ваза; растение справа от арки
    yb = Y0 - 0.012 - 0.01
    zs = bench(0.55, 1.75, yb)
    load_asset('wicker_basket_02', loc=(0.95, yb - 0.2, 0), rot=10, scale=1.25)
    zt = books(1.45, yb - 0.17, zs, 2, seed=5)
    load_asset('ceramic_vase_01', loc=(0.8, yb - 0.17, zs), rot=30)
    load_asset('potted_plant_02', loc=(3.5, Y0 - 0.5, 0), rot=120)
    # за аркой: кресло, столик с вазой, картина, подвес
    load_asset('modern_arm_chair_01', loc=(3.15, Y0 + T + 2.2, 0), rot=float(A.get('chair_rot', -25)))
    load_asset('side_table_tall_01', loc=(2.8, Y0 + T + 2.9, 0), rot=0)
    load_asset('ceramic_vase_04', loc=(2.8, Y0 + T + 2.9, 0.761), rot=40)
    load_asset('hanging_picture_frame_01', loc=(3.2, D2 - 0.012, 1.05), rot=float(A.get('pic_rot', 0)))
    load_asset('modern_ceiling_lamp_01', loc=(2.75, Y0 + T + 1.5, H - 0.9515), rot=0)
    m_rug = mat_pbr('rug', 'hessian_230', 0.55, tint=srgb(240, 232, 218), nstrength=1.5)
    box('rug', 1.9, 3.8, Y0 + T + 1.2, Y0 + T + 3.4, 0.0, 0.012, m_rug, bevel=0.004)
    az, el = float(A.get('sun_az', 38)), float(A.get('sun_el', 32))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    world, sun = setup_world(sun_dir)
    load_asset('potted_plant_01', loc=(1.7, D2 - 0.6, 0), rot=80)
    cal = camera((1.5, 0.5, 1.25), (2.05, Y0, 1.08), lens=float(A.get('lens', 28)), fstop=float(A.get('fstop', 8)), focus=4.0)
    if A.get('cam') == 'b':     # с другой стороны: виден откос арки и дальняя комната с окном
        camera((3.05, 0.6, 1.25), (1.9, Y0, 1.05), lens=28, fstop=8, focus=4.0)
    elif A.get('cam') == 'c':   # ближе и почти в лоб: арка крупно
        camera((2.2, 1.35, 1.25), (2.35, Y0, 1.12), lens=30, fstop=8, focus=3.0)
    return world, sun, sun_dir, lamps, cal


def scene_plinth():
    """Плинтус A703: угол комнаты, низкая камера, отрезок с торцом на полу."""
    global NEUTRAL
    NEUTRAL = ('ceil',)
    W, D, H = 4.0, 5.0, 2.7
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=hexcol(A.get('paint', '5E7474')), rough=0.88, nstrength=0.6)
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(float(A.get('floor_rot', 90))),
                      tint=srgb(232, 222, 210))
    room(W, D, H, win=(2.0, 4.4, 0.06, 2.46), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil, plinth=False)
    mp = mat_simple('plinth_white', srgb(242, 242, 239), rough=0.38)
    plinth_run('pl_back', (0.0, D), (W, D), (0, -1), mp, miter1=True)
    plinth_run('pl_right', (W, 0.0), (W, D), (-1, 0), mp, miter1=True)
    if A.get('cam') != 'wide':
        plinth_piece('pl_piece', (2.88, 4.46, 0.0), float(A.get('piece_rot', 52)), 0.40, mp)
    curtain('sheer', 0.12, 1.8, 4.65, 0.012, 2.64, mat_sheer())
    box('track', 0.07, 0.17, 1.7, 4.75, 2.64, 2.67, mat_simple('track', srgb(240, 240, 238), rough=0.4))
    load_asset('potted_plant_02', loc=(3.66, D - 0.34, 0), rot=120)
    az, el = float(A.get('sun_az', 40)), float(A.get('sun_el', 24))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    world, sun = setup_world(sun_dir)
    cal = camera((2.0, 0.8, 1.25), (2.2, D, 1.1), lens=28)
    if A.get('cam') == 'wide':
        camera((1.6, 2.2, 0.55), (3.2, D, 0.3), lens=30, fstop=8, focus=2.6)
    else:
        camera((2.55, 4.0, float(A.get('cam_z', 0.2))), (3.5, D, 0.06), lens=float(A.get('lens', 35)), fstop=float(A.get('fstop', 16)),
               focus=float(A.get('focus', 0.65)))
    return world, sun, sun_dir, [], cal


SCENES = {'lounge': scene_lounge, 'arch': scene_arch, 'plinth': scene_plinth}

setup_render()
world, sun, sun_dir, lamps, cal_cam = SCENES[SCENE]()
bpy.context.view_layer.update()
log('objects', len(scene.objects), 'scene built')
calibrate(world, sun, sun_dir, neutral_prefixes=NEUTRAL, lamps=lamps, cal_cam=cal_cam)
render_final()
log('done')
