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


def slat_wall(name, x0, x1, z_top, y_wall, m_wood, m_black, zbot=None, step=0.040, lam_w=0.0295, total_t=0.012, base_t=0.006,
              tex_m=1.0, cham=0.0008, strip=None):
    """Реечные панели 120×12 мм: 3 рейки, шаг 40 мм, рейка 29,5 мм, паз 10,5 мм глубиной 6 мм (по живому образцу). Лицом к −Y.
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
        if strip:      # полоска tex3: поперёк рейки 0…1, вдоль — длина рисунка strip (м), сдвиг и зеркало свои у каждой рейки
            WUV = lambda x, z, _xl=xl, _v=int(v0 * 8) + u0: ((x - _xl) / lam_w, _v + z / strip)
        else:
            WUV = lambda x, z, _xl=xl, _u=u0, _v=v0: (_u + (x - _xl) / tex_m, _v + z / tex_m)
        zs = [zb(min(max(p[0], xa + 1e-6), xb - 1e-6)) for p in prof]
        for k in range(5):
            (xA, yA), (xB, yB) = prof[k], prof[k + 1]
            wood = k in (1, 2, 3)
            if k == 2 and zbot and max(zs) > 1e-4:
                for q in range(4):
                    xq0, xq1 = xA + (xB - xA) * q / 4, xA + (xB - xA) * (q + 1) / 4
                    zq0, zq1 = zb(xq0), zb(xq1)
                    uv = [WUV(xq0, zq0), WUV(xq1, zq1), WUV(xq1, z_top), WUV(xq0, z_top)]
                    quad([(xq0, yA, zq0), (xq1, yA, zq1), (xq1, yA, z_top), (xq0, yA, z_top)], 0, uv, j)
                continue
            if wood:
                uv = [WUV(xA, zs[k]), WUV(xB, zs[k + 1]), WUV(xB, z_top), WUV(xA, z_top)]
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


def reeded_wall(name, x0, x1, z_top, y_wall, mat, zbot=None, pitch=0.020, seg=18):
    """Панель A910 «волна» по живому образцу: почти полукруглые валики шагом 20 мм (9 на панели 180 мм), толщина 6,5…12 мм,
    между валиками узкая ровная полоска. Лицом к −Y."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import a910_profile as AP
    zb = zbot or (lambda x: 0.0)
    us = [u / 1000.0 for u in AP.rib_samples(seg)]
    n = int(math.ceil((x1 - x0) / pitch - 1e-6))
    V, F, SM = [], [], []
    for i in range(n):
        xa = x0 + i * pitch
        xb = min(xa + pitch, x1)
        base = len(V)
        cnt = 0
        for u in us:
            x = xa + u
            if x > xb + 1e-9:
                break
            t = AP.t_at(u * 1000.0) / 1000.0
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
            SM.append(0 < k < len(us) - 2)
    ob = make_obj(name, V, F, [mat], smooth=SM)
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


def plinth_piece(name, loc, rot, length, mat, mode='face'):
    """Отрезок плинтуса: face — лежит лицом вверх (виден торец с кабель-каналом), back — тыльной стороной вверх, stand — стоит как на стене."""
    pts = [(p[0] / 1000.0, p[1] / 1000.0) for p in A703]
    n = len(pts)
    V = [(0.0, u, t) for (u, t) in pts] + [(length, u, t) for (u, t) in pts]
    F = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for k in range(n):
        j = (k + 1) % n
        F.append((k, n + k, n + j, j))
    # срез — белый зернистый, как у живого образца A910 (тот же материал): замечание Михаила 12.11 «гладкий край — переделай»
    ob = make_obj(name, V, F, [mat, mat_foam_white()], face_mats=[1, 1] + [0] * n)
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
    if mode == 'back':
        ob.rotation_euler = (math.pi, 0, R(rot))
        ob.location = (loc[0], loc[1], loc[2] + 0.015)
    elif mode == 'stand':
        ob.rotation_euler = (-math.pi / 2, 0, R(rot))
        ob.location = (loc[0], loc[1], loc[2] + 0.080)
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
    cal_cam — общий план сцены: по нему меряем свет, даже если снимаем крупный план.
    calfile=<файл.json> — взять готовые значения (весь набор кадров с одним светом и экспозицией); значения каждого кадра пишутся в out/<имя>/cal.json."""
    cf = A.get('calfile')
    if cf and os.path.exists(f'{ROOT}/{cf}'):
        c = json.load(open(f'{ROOT}/{cf}'))
        sun.data.energy, sun.data.color = c['sun_energy'], tuple(c['sun_color'])
        world.node_tree.nodes['WB'].inputs['Color2'].default_value = tuple(c['wb']) + (1.0,)
        scene.view_settings.exposure = c['exposure'] + EV
        for ld, k in lamps:
            ld.energy = k * c['y_ref']
        log('calibration from', cf, c)
        return c['y_ref']
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
    json.dump({'sun_energy': float(sun.data.energy), 'sun_color': [float(v) for v in sun.data.color], 'wb': [float(v) for v in gains],
               'exposure': float(ev - EV), 'y_ref': float(y_ref)}, open(f'{OUT}/cal.json', 'w'))
    if 'reexp' in A:      # экспозиция по медиане итогового кадра: нужно, когда свой свет сильнее оконного
        y2 = float(np.median(lum(render_linear(pw, ph, 48, 'pre2'))))
        ev = math.log2(float(A['reexp']) / max(y2, 1e-6)) + EV
        scene.view_settings.exposure = ev
        log('re-exposure: frame median', round(y2, 4), 'exposure', round(ev, 2))
    return y_ref


def render_final():
    r = scene.render
    if r.film_transparent:            # образец на прозрачном фоне — PNG с альфой
        r.image_settings.file_format = 'PNG'
        r.image_settings.color_mode = 'RGBA'
        r.filepath = f'{OUT}/{NAME}.png'
    else:
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


def mat_foam():
    """Срез вспененного полистирола: тёмный графит, поры и светлые крупинки."""
    m = bpy.data.materials.get('pan_foam')
    if m:
        return m
    m, nt, out = new_mat('pan_foam')
    b = principled(nt, out, Roughness=0.6, **{'Specular IOR Level': 0.5})
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.inputs['Scale'].default_value = float(A.get('foam_scale', 1900.0))
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 700.0
    nz.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    cr = nt.nodes.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.40
    cr.color_ramp.elements[0].color = (0.006, 0.006, 0.007, 1)
    cr.color_ramp.elements[1].position = 0.78
    cr.color_ramp.elements[1].color = (0.085, 0.085, 0.09, 1)
    nt.links.new(nz.outputs['Fac'], cr.inputs['Fac'])
    nt.links.new(cr.outputs['Color'], b.inputs['Base Color'])
    ad = nt.nodes.new('ShaderNodeMath')
    ad.operation = 'ADD'
    nt.links.new(vo.outputs['Distance'], ad.inputs[0])
    nt.links.new(nz.outputs['Fac'], ad.inputs[1])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 1.0
    bp.inputs['Distance'].default_value = 0.0005
    nt.links.new(ad.outputs[0], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def panel_piece(name, loc, rot, length, mode='face', n=3):
    """Отрезок реечной панели по живому образцу: профиль «змейкой» с пустотами под рейками, срез вспененный,
    тыльная сторона глянцевая. mode: face — лицом вверх, back — тыльной стороной вверх."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import slat_profile as SP
    prof = SP.rounded(SP.outline(n))
    m_wood = bpy.data.materials.get('decor_' + DECOR) or mat_decor(DECOR)
    m_skin = bpy.data.materials.get('pan_skin') or mat_simple('pan_skin', (0.007, 0.007, 0.008, 1), rough=0.42, **{'Specular IOR Level': 0.4})
    m_back = bpy.data.materials.get('pan_back') or mat_simple('pan_back', (0.006, 0.006, 0.007, 1), rough=0.2)
    N, L = len(prof), length
    V = [(x / 1000.0, 0.0, z / 1000.0) for x, z, _ in prof] + [(x / 1000.0, L, z / 1000.0) for x, z, _ in prof]
    F, FM, UV, JIT = [], [], [], []
    offs = [(random.random(), random.random(), random.random()) for _ in range(n)]
    for k in range(N):
        j = (k + 1) % N
        tag = prof[k][2]
        F.append((k, N + k, N + j, j))
        if tag == 'w':
            u0, v0, jt = offs[min(n - 1, int(((prof[k][0] + prof[j][0]) / 2) // SP.STEP))]
            ua, ub = u0 + prof[k][0] / 1000.0, u0 + prof[j][0] / 1000.0
            UV.append([(ua, v0), (ua, v0 + L), (ub, v0 + L), (ub, v0)])
            FM.append(0)
            JIT.append(jt)
        else:
            UV.append([(0, 0)] * 4)
            FM.append(1 if tag == 's' else 2)
            JIT.append(0.5)
    for cap in (tuple(range(N)), tuple(reversed(range(N, 2 * N)))):
        F.append(cap)
        FM.append(3)
        UV.append([(0, 0)] * N)
        JIT.append(0.5)
    ob = make_obj(name, V, F, [m_wood, m_skin, m_back, mat_foam()], face_mats=FM, uvs=UV, jit=JIT)
    try:
        ob.data.validate()
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
    except Exception as e:  # noqa
        log('panel piece normals', e)
    ob.location = loc
    ob.rotation_euler = (0, 0, R(rot))
    if mode == 'back':
        ob.rotation_euler = (0, math.pi, R(rot))
        ob.location = (loc[0], loc[1], loc[2] + 0.012)
    return ob


def mat_foam_white():
    """Срез белой панели: мелкозернистая плотная пена, чуть серее лица."""
    m = bpy.data.materials.get('foam_white')
    if m:
        return m
    m, nt, out = new_mat('foam_white')
    b = principled(nt, out, Roughness=0.95, **{'Base Color': (0.72, 0.71, 0.68, 1.0), 'Specular IOR Level': 0.2})
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.inputs['Scale'].default_value = float(A.get('foamw_scale', 2600.0))
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 900.0
    nz.inputs['Detail'].default_value = 6.0
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    ad = nt.nodes.new('ShaderNodeMath')
    ad.operation = 'ADD'
    nt.links.new(vo.outputs['Distance'], ad.inputs[0])
    nt.links.new(nz.outputs['Fac'], ad.inputs[1])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.9
    bp.inputs['Distance'].default_value = 0.0004
    nt.links.new(ad.outputs[0], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def reeded_piece(name, loc, rot, length, mat, mode='face', **_old):
    """Отрезок панели A910 по живому образцу: валики, канавки на тыльной стороне, белый зернистый срез.
    mode: face — лицом вверх, back — тыльной стороной вверх."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import a910_profile as AP
    prof = AP.outline()
    m_back = bpy.data.materials.get('a910_back') or mat_simple('a910_back', srgb(236, 235, 231), rough=0.5)
    N, L = len(prof), length
    V = [(x / 1000.0, 0.0, z / 1000.0) for x, z, _ in prof] + [(x / 1000.0, L, z / 1000.0) for x, z, _ in prof]
    F, FM, SM = [], [], []
    for k in range(N):
        j = (k + 1) % N
        F.append((k, N + k, N + j, j))
        FM.append(0 if prof[k][2] == 'f' else 1)
        SM.append(abs(prof[k][0] - prof[j][0]) < 1.4 and abs(prof[k][1] - prof[j][1]) < 2.5)   # дуги — гладко, плоскости — нет
    for cap in (tuple(range(N)), tuple(reversed(range(N, 2 * N)))):
        F.append(cap)
        FM.append(2)
        SM.append(False)
    ob = make_obj(name, V, F, [mat, m_back, mat_foam_white()], face_mats=FM, smooth=SM)
    try:
        ob.data.validate()
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
    except Exception as e:  # noqa
        log('reeded piece normals', e)
    ob.location = loc
    ob.rotation_euler = (0, 0, R(rot))
    if mode == 'back':
        ob.rotation_euler = (0, math.pi, R(rot))
        ob.location = (loc[0], loc[1], loc[2] + 0.012)
    return ob


def hexcol(h):
    h = h.lstrip('#')
    return srgb(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def mat_decor_strip(decor):
    """Плёнка «под дерево» по полоске с сайта (tex3/<артикул>.jpg — настоящий рисунок декора с фото поставщика)."""
    m, nt, out = new_mat('decor_' + decor)
    b = principled(nt, out, Roughness=0.46)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = load_img(f'{ROOT}/tex3/{decor.lower()}.jpg')
    n.extension = 'MIRROR'
    nt.links.new(tc.outputs['UV'], n.inputs['Vector'])
    uv2 = nt.nodes.new('ShaderNodeUVMap')
    uv2.uv_map = 'jit'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv2.outputs['UV'], sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.95
    mr.inputs['To Max'].default_value = 1.04
    nt.links.new(sep.outputs['X'], mr.inputs['Value'])
    hs = nt.nodes.new('ShaderNodeHueSaturation')
    hs.inputs['Saturation'].default_value = float(A.get('dsat', 1.0))
    nt.links.new(n.outputs['Color'], hs.inputs['Color'])
    nt.links.new(mr.outputs['Result'], hs.inputs['Value'])
    gm = nt.nodes.new('ShaderNodeGamma')              # dgam > 1 — темнее (подгонка под фото каталога)
    gm.inputs['Gamma'].default_value = float(A.get('dgam', 1.0))
    nt.links.new(hs.outputs['Color'], gm.inputs['Color'])
    nt.links.new(gm.outputs['Color'], b.inputs['Base Color'])
    bw = nt.nodes.new('ShaderNodeRGBToBW')
    nt.links.new(n.outputs['Color'], bw.inputs['Color'])
    rr = nt.nodes.new('ShaderNodeMapRange')
    rr.inputs['To Min'].default_value = 0.56
    rr.inputs['To Max'].default_value = 0.42
    nt.links.new(bw.outputs['Val'], rr.inputs['Value'])
    nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    return m


def profile_wall(name, pts_mm, x0, x1, z_top, y_wall, mat):
    """Стена из панелей по лицевому контуру (profiles_site.json): панели встык от x0, последняя подрезана по x1. Лицом к −Y."""
    wid = pts_mm[-1][0] / 1000.0
    n = int(math.ceil((x1 - x0) / wid - 1e-6))
    obs = []
    for i in range(n):
        xo, pts = x0 + i * wid, pts_mm
        if xo + wid > x1 + 1e-6:
            lim = (x1 - xo) * 1000.0
            cut = [q for q in pts_mm if q[0] <= lim]
            nxt = next(q for q in pts_mm if q[0] > lim)
            t = (lim - cut[-1][0]) / (nxt[0] - cut[-1][0])
            pts = cut + [(lim, cut[-1][1] + (nxt[1] - cut[-1][1]) * t)]
        ob = profile_panel(f'{name}{i}', pts, xo, z_top, mat)
        ob.location.y = y_wall
        obs.append(ob)
    log('profile wall', name, 'panels', n, 'width', wid)
    return obs


def panel_wall(x0, x1, z_top, y_wall, zbot=None):
    """Стена из панелей выбранного артикула: любая белая под покраску (profiles_site.json; A910 — по живому образцу)
    или реечная «под дерево» серий 2, 3, 5 (decor=3-7 …; tex=strip — рисунок декора с сайта, иначе шпон Poly Haven)."""
    d = DECOR.upper().replace(' ', '').replace('/', '-')
    paint = lambda: mat_simple('panel_paint', hexcol(A.get('paint', 'EFEEEA')), rough=float(A.get('paint_rough', 0.55)), bump=0.02, bump_scale=1500.0)
    if d == 'A910':
        return reeded_wall('panels', x0, x1, z_top, y_wall, paint(), zbot=zbot)
    profs = json.load(open(f'{ROOT}/profiles_site.json', encoding='utf-8'))
    key = next((k for k in profs if k.upper().replace(' ', '').replace('/', '-') == d), None)
    if key:
        return profile_wall('panels', [(float(x), float(h)) for x, h in profs[key]], x0, x1, z_top, y_wall, paint())
    m_black = mat_simple('pan_black', (0.007, 0.007, 0.008, 1), rough=0.8, **{'Specular IOR Level': 0.25})
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import slat_profile
    ser = int(DECOR.split('-')[0]) if DECOR[:1] in '235' and '-' in DECOR else 3
    step, lam = slat_profile.SERIES[ser]
    if A.get('tex') == 'strip':
        ln = json.load(open(f'{ROOT}/tex3/index.json', encoding='utf-8'))[DECOR]['len_mm'] / 1000.0
        return slat_wall('panels', x0, x1, z_top, y_wall, mat_decor_strip(DECOR), m_black, zbot=zbot, step=step / 1000.0, lam_w=lam / 1000.0, strip=ln)
    return slat_wall('panels', x0, x1, z_top, y_wall, mat_decor(DECOR), m_black, zbot=zbot, step=step / 1000.0, lam_w=lam / 1000.0)


def make_mask(world, sun, lamps):
    """mask=1 — маска стены из панелей: панели белые, всё остальное чёрное (для перекраски стены на готовом фото)."""
    def em(name, v):
        m, nt, out = new_mat(name)
        e = nt.nodes.new('ShaderNodeEmission')
        e.inputs['Color'].default_value = (v, v, v, 1)
        nt.links.new(e.outputs['Emission'], out.inputs['Surface'])
        return m
    mw, mk = em('mask_white', 1.0), em('mask_black', 0.0)
    for ob in scene.objects:
        if ob.type != 'MESH':
            continue
        ob.data.materials.clear()
        ob.data.materials.append(mw if ob.name.startswith('panel') else mk)
        ob.data.polygons.foreach_set('material_index', [0] * len(ob.data.polygons))
    wo = bpy.data.worlds.new('mask_world')
    wo.use_nodes = True
    wo.node_tree.nodes['Background'].inputs['Color'].default_value = (0, 0, 0, 1)
    scene.world = wo
    sun.hide_render = True
    for ld, k in lamps:
        ld.energy = 0.0
    vs = scene.view_settings
    vs.view_transform, vs.exposure = 'Standard', 0.0
    try:
        vs.look = 'None'
    except Exception as e:  # noqa
        log('look', e)
    c = scene.cycles
    c.samples, c.use_adaptive_sampling, c.use_denoising = 64, False, False


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
        ms = mat_simple('tv_screen', (0.012, 0.012, 0.014, 1), rough=1.0, **{'Specular IOR Level': 0.0})
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
    FS = lambda d: ((float(A['fs']) or None) if 'fs' in A else d)   # fs=0 — без размытия
    if cm == 'close':
        camera((1.85, 3.95, 1.12), (2.72, D, 0.95), lens=50, fstop=FS(5.6), focus=1.55)
    elif cm == 'macro':
        camera((3.0, 4.55, 1.2), (3.75, D - 0.012, 1.15), lens=60, fstop=FS(8.0), focus=0.98)
    elif cm == 'macro2':        # участок в косом солнце над тумбой
        camera((2.35, 4.62, 1.47), (1.75, D - 0.012, 1.42), lens=60, fstop=FS(8.0), focus=0.83)
    elif cm == 'mid':           # средний план: тумба с вещами, рельеф стены читается
        camera((2.2, 2.6, 1.1), (2.1, D, 0.95), lens=35, fstop=FS(5.6), focus=2.4)
    elif cm == 'angle':         # три четверти от правой стены: стена уходит в перспективу, слева вдали окно
        camera((float(A.get('ax', 3.85)), float(A.get('ay', 3.2)), float(A.get('az', 1.2))), (float(A.get('lx', 1.75)), D, 0.95),
               lens=float(A.get('lens', 38)), fstop=FS(None))
    elif cm == 'diag':          # по диагонали от правой стены: окно, растение, тумба, кресло
        camera((3.95, 1.25, 1.2), (1.5, D, 1.0), lens=30, fstop=FS(5.6), focus=4.2)
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
        camera((1.92, 2.56, 0.95), (1.99, 3.1, 0.735), lens=50, fstop=float(A.get('fstop', 6.3)), focus=0.5, level=False)
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
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=hexcol(A.get('paint', '5E7474')), rough=0.88, nstrength=float(A.get('nstr', 0.6)))
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    surf = A.get('surf', 'wood')      # на чём лежат образцы: wood — ламинат, linen — светлая ткань, plaster — светлая штукатурка
    if surf == 'linen':
        m_floor = mat_pbr('floor', 'rough_linen', float(A.get('surf_m', 0.6)), tint=hexcol(A.get('surfcol', 'F0EBE2')), nstrength=1.0)
    elif surf == 'plaster':
        m_floor = mat_pbr('floor', 'beige_wall_001', float(A.get('surf_m', 1.4)), color=hexcol(A.get('surfcol', 'DDD9D2')), nstrength=0.5)
    else:
        m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(float(A.get('floor_rot', 90))),
                          tint=srgb(232, 222, 210))
    room(W, D, H, win=(2.0, 4.4, 0.06, 2.46), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil, plinth=False)
    cm = A.get('cam', 'close')
    mp = mat_simple('plinth_white', hexcol(A['plcol']) if 'plcol' in A else srgb(242, 242, 239), rough=float(A.get('plrough', 0.38)))
    plinth_run('pl_back', (0.0, D), (W, D), (0, -1), mp, miter1=True)
    plinth_run('pl_right', (W, 0.0), (W, D), (-1, 0), mp, miter1=True)
    # отрезок с торцом: для cam=end — положение задаём, камера смотрит в торец
    pl, pr = (float(A.get('px', 3.0)), float(A.get('py', 4.50))), float(A.get('piece_rot', 68))
    if cm == 'end':
        plinth_piece('pl_piece', (pl[0], pl[1], 0.0), pr, 0.40, mp)
    elif cm in ('top', 'cut'):   # образцы отдельно на полу: top — вид сверху-спереди (в кадре только пол), cut — срез крупно
        tcx, tcy, st, item = float(A.get('cx', 2.55)), float(A.get('cy', 3.0)), A.get('set', 'two'), A.get('item', 'plinth')
        if item == 'plinth':
            ra = float(A.get('rot_a', 66))
            oA, wd = Vector((tcx + 0.02, tcy, 0)), 0.080
            dA, wA = Vector((math.cos(R(ra)), math.sin(R(ra)), 0)), Vector((-math.sin(R(ra)), math.cos(R(ra)), 0))
            plinth_piece('pl_a', (oA.x, oA.y, 0.0), ra, 0.40, mp)
            if cm == 'top' and st == 'two':
                plinth_piece('pl_b', (tcx + 0.10, tcy + 0.03, 0.0), float(A.get('rot_b', 58)), 0.34, mp, mode='back')
            elif cm == 'top' and st == 'stand':
                plinth_piece('pl_c', (tcx + 0.24, tcy + 0.50, 0.0), 200, 0.35, mp, mode='stand')
            grp = None
        else:
            wd = 0.18 if item == 'a910' else 0.12
            ra, rb = float(A.get('rot_a', -24)), float(A.get('rot_b', -34))
            dA, wA = Vector((-math.sin(R(ra)), math.cos(R(ra)), 0)), Vector((math.cos(R(ra)), math.sin(R(ra)), 0))
            dB, wB = Vector((-math.sin(R(rb)), math.cos(R(rb)), 0)), Vector((math.cos(R(rb)), math.sin(R(rb)), 0))
            oA = Vector((tcx - 0.07, tcy + 0.02, 0))
            oB = oA + wA * (wd + 0.05) + wB * wd + dA * 0.08

            def piece(nm, o, r, L, back=False):
                if item == 'a910':
                    mpc = bpy.data.materials.get('a910_paint') or mat_simple('a910_paint', hexcol(A.get('paint910', 'EFEEEA')), rough=0.55,
                                                                             bump=0.02, bump_scale=1500.0)
                    return reeded_piece(nm, (o.x, o.y, 0.0), r, L, mpc, mode='back' if back else 'face')
                return panel_piece(nm, (o.x, o.y, 0.0), r, L, mode='back' if back else 'face')

            LA, LB = 0.42, 0.34
            piece('pc_a', oA, ra, LA)
            pts = [oA, oA + dA * LA, oA + wA * wd, oA + dA * LA + wA * wd]
            if cm == 'top' and st == 'two':        # второй отрезок рядом, тыльной стороной вверх
                oB = oA + wA * (wd + 0.05) + wB * wd + dA * 0.08
                piece('pc_b', oB, rb, LB, back=True)
                pts += [oB, oB + dB * LB, oB - wB * wd, oB + dB * LB - wB * wd]
            elif cm == 'top' and st == 'stack':    # второй отрезок крест-накрест поверх первого, лицом вверх
                rs = float(A.get('rot_s', 30))
                dS, wS = Vector((-math.sin(R(rs)), math.cos(R(rs)), 0)), Vector((math.cos(R(rs)), math.sin(R(rs)), 0))
                LB = 0.36 if item != 'a910' else 0.40
                oS = oA + dA * (LA * 0.64) + wA * (wd / 2) - dS * (LB / 2) - wS * (wd / 2)
                bobj = piece('pc_b', oS, rs, LB)
                bobj.location = (oS.x, oS.y, 0.012)
                pts += [oS, oS + dS * LB, oS + wS * wd, oS + dS * LB + wS * wd]
            xs, ys = [q.x for q in pts], [q.y for q in pts]
            grp = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(max(xs) - min(xs), (max(ys) - min(ys)) * 1.1) + 0.06)
    elif cm not in ('wide', 'corner', 'run', 'wall') and A.get('piece', '1') == '1':
        plinth_piece('pl_piece', (2.88, 4.46, 0.0), float(A.get('piece_rot', 52)), 0.40, mp)
    curtain('sheer', 0.12, 1.8, 4.65, 0.012, 2.64, mat_sheer())
    box('track', 0.07, 0.17, 1.7, 4.75, 2.64, 2.67, mat_simple('track', srgb(240, 240, 238), rough=0.4))
    if A.get('basket') == '1':
        load_asset('wicker_basket_02', loc=(W - float(A.get('bx', 0.32)), float(A.get('by', 4.25)), 0), rot=20)
    if A.get('pot', '0' if cm in ('corner', 'run', 'end', 'top', 'cut', 'wall') else '1') == '1':
        load_asset('potted_plant_02', loc=(float(A.get('potx', 3.66)), D - 0.34, 0), rot=120)
    az, el = float(A.get('sun_az', 40)), float(A.get('sun_el', 24))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    world, sun = setup_world(sun_dir)
    lamps = []
    if 'fill' in A:
        ld = bpy.data.lights.new('fill', 'AREA')
        ld.shape, ld.size, ld.energy = 'SQUARE', float(A.get('fill_size', 1.4)), 0.0
        ld.color = (1.0, 0.966, 0.899)
        lo = bpy.data.objects.new('fill', ld)
        col.objects.link(lo)
        fd, fz = float(A.get('fill_d', 1.7)), float(A.get('fill_z', 1.5))
        lo.location = (W - fd, D - fd, fz)
        lo.rotation_euler = (Vector((W - 0.1, D - 0.1, 0.25)) - Vector(lo.location)).to_track_quat('-Z', 'Y').to_euler()
        try:
            lo.visible_camera = False
        except Exception:
            pass
        lamps.append((ld, float(A['fill'])))
    cal = camera((2.0, 0.8, 1.25), (2.2, D, 1.1), lens=28)
    cz = float(A.get('cam_z', 0.15))
    if cm == 'wide':
        camera((1.6, 2.2, 0.55), (3.2, D, 0.3), lens=30, fstop=8, focus=2.6)
    elif cm == 'corner':   # внутренний угол крупно: плинтус занимает низ кадра, виден запил 45°
        cx, cy = float(A.get('cdx', 0.52)), float(A.get('cdy', 0.40))
        camera((W - cx, D - cy, cz), (W - 0.03, D - 0.03, float(A.get('look_z', 0.04))), lens=float(A.get('lens', 40)),
               fstop=float(A.get('fstop', 11)) or None, focus=float(A.get('focus', math.hypot(cx, cy))))
    elif cm == 'top' and grp is None:
        camera((tcx - 0.02, tcy - float(A.get('back', 0.42)), float(A.get('cam_z', 0.36))),
               (tcx + float(A.get('look_dx', 0.08)), tcy + float(A.get('look_dy', 0.17)), 0.0),
               lens=float(A.get('lens', 50)), fstop=float(A.get('fstop', 0)) or None, focus=float(A.get('focus', 0.65)), level=False)
    elif cm == 'top':
        gx, gy, gw = grp
        gw *= float(A.get('zoom', 1.0))
        camera((gx - 0.03, gy - 1.15 * gw, 0.98 * gw), (gx, gy - 0.02, 0.0), lens=float(A.get('lens', 42)),
               fstop=float(A.get('fstop', 0)) or None, focus=1.5 * gw, level=False)
    elif cm == 'cut':      # срез крупно: торец первого отрезка занимает почти всю ширину кадра
        E = oA + wA * (wd / 2)
        dd = wd / 0.48 * float(A.get('zoom', 1.0))
        cl = E - dA * (dd * 0.92) + wA * (dd * float(A.get('side', 0.10)))
        lk = E + dA * 0.03
        camera((cl.x, cl.y, dd * float(A.get('up', 0.40))), (lk.x, lk.y, 0.005), lens=float(A.get('lens', 60)),
               fstop=float(A.get('fstop', 0)) or None, focus=dd, level=False)
    elif cm == 'wall':     # одна стена под углом: плинтус уходит вдаль, стыков и второй стены в кадре нет
        camera((W - float(A.get('off', 0.45)), float(A.get('wy', 3.3)), float(A.get('cam_z', 0.14))), (W - 0.02, float(A.get('wy', 3.3)) + 0.45, 0.05),
               lens=float(A.get('lens', 40)), fstop=float(A.get('fstop', 0)) or None, focus=0.8)
    elif cm == 'run':      # вдоль стены у самого пола: линия плинтуса уходит в угол
        camera((W - float(A.get('off', 0.17)), D - float(A.get('back', 2.4)), float(A.get('cam_z', 0.09))), (W - 0.03, D - 0.02, 0.05),
               lens=float(A.get('lens', 50)), fstop=float(A.get('fstop', 5.6)), focus=float(A.get('focus', 0.95)))
    elif cm == 'end':      # торец отрезка: профиль и кабель-канал
        dx, dy = math.cos(R(pr)), math.sin(R(pr))
        qx, qy = -dy, dx
        side, back = float(A.get('side', -0.05)), float(A.get('back', 0.30))
        cl = (pl[0] - dx * back + qx * side, pl[1] - dy * back + qy * side, float(A.get('cam_z', 0.075)))
        lk = (pl[0] + dx * 0.10 + qx * 0.04, pl[1] + dy * 0.10 + qy * 0.04, 0.006)
        camera(cl, lk, lens=float(A.get('lens', 50)), fstop=float(A.get('fstop', 11)), focus=float(A.get('focus', back + 0.02)))
    else:
        camera((2.55, 4.0, float(A.get('cam_z', 0.2))), (3.5, D, 0.06), lens=float(A.get('lens', 35)), fstop=float(A.get('fstop', 16)),
               focus=float(A.get('focus', 0.65)))
    return world, sun, sun_dir, lamps, cal



# ------------------------------------------------------------------ студия: фото товара для каталога сайта (16.11.2026)
def prof_points(item):
    """Лицевой контур панели: (x мм поперёк, толщина мм) — по чертежу каталога (сайт, PROF).
    С живым образцом A903/A907 не сверены: тыл и торец в кадр не ставим."""
    if item == 'a903':   # «призма»: 7 треугольных граней, гребень 10 мм, впадина ≈3,4 мм (по чертежу)
        pitch, pts = 180.0 / 7, []
        for k in range(7):
            xm = k * pitch + pitch / 2
            pts += [(k * pitch, 3.43), (xm - 0.5, 9.72), (xm, 10.0), (xm + 0.5, 9.72)]
        pts.append((180.0, 3.43))
        return pts
    data = json.load(open(f'{ROOT}/profiles_site.json', encoding='utf-8'))[item.upper()]
    return [(float(x), float(h)) for x, h in data]


def profile_panel(name, pts_mm, x_off, length, mat, sharp_deg=32.0):
    """Панель по контуру: лицо к −Y, тыл в плоскости y=0, высота по Z от 0 до length."""
    pts = [(x_off + x / 1000.0, -h / 1000.0) for x, h in pts_mm]
    pts += [(x_off + pts_mm[-1][0] / 1000.0, 0.0), (x_off + pts_mm[0][0] / 1000.0, 0.0)]
    n = len(pts)
    V = [(x, y, 0.0) for x, y in pts] + [(x, y, length) for x, y in pts]
    F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    F += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    ob = make_obj(name, V, F, [mat], smooth=[True] * len(F))
    try:
        ob.data.set_sharp_from_angle(angle=R(sharp_deg))
    except Exception as e:  # noqa
        log('sharp edges', e)
    return ob


def area_light(name, loc, look, sx, sy, power, color=(1.0, 1.0, 1.0), spread=180.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y, ld.energy, ld.color = sx, sy, power, color
    try:
        ld.spread = R(spread)   # «сота» на софтбоксе: свет не растекается на фон
    except Exception as e:  # noqa
        log('spread', e)
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def studio_panels(item, x0, x1, z0, z1):
    """Панели артикула на стене y=0 (лицом к −Y) от x0 до x1, от z0 до z1."""
    if item == 'slat':
        m_wood = mat_decor(DECOR)
        m_black = mat_simple('pan_black', (0.007, 0.007, 0.008, 1), rough=0.8, **{'Specular IOR Level': 0.25})
        ob = slat_wall('panels', x0, x1, z1, 0.0, m_wood, m_black, zbot=lambda x: z0)
        return [ob]
    mp = mat_simple('white_paint', hexcol(A.get('paint', 'EFEEEA')), rough=float(A.get('paint_rough', 0.55)),
                    bump=0.02, bump_scale=1500.0)
    pts = prof_points(item)
    n = max(1, int(round((x1 - x0) / 0.18)))
    out = []
    for i in range(n):
        ob = profile_panel(f'panel{i}', pts, x0 + 0.18 * i, z1 - z0, mp)
        ob.location.z = z0
        out.append(ob)
    return out


def scene_studio():
    """Фото каталога. view=wall — участок стены из панелей на тёмной стене «Антрацит» с полом (как будет дома);
    view=close — крупно под углом (рельеф и швы); view=slice — панели отдельно на фоне.
    Концы панелей не видны (низ — на полу, верх — за кадром), тыл не виден.
    item=a907|a903|slat (slat — реечные серии 3, decor=3-7…)."""
    item = A.get('item', 'a907').lower()
    view = A.get('view', 'wall')
    w = float(A.get('w', 1.08 if item != 'slat' else 0.96))
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=hexcol(A.get('wallcol', '3B3F45')), rough=0.9,
                     nstrength=float(A.get('nstr', 0.25)))
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(90),
                      tint=srgb(232, 222, 210))
    box('wall', -5, 5, 0.0, 0.2, -0.1, 3.2, m_wall)
    box('floor', -5, 5, -7, 0.2, -0.1, 0.0, m_floor)
    studio_panels(item, -w / 2, w / 2, 0.0, 2.7)
    # свет: «окно» справа — вертикальный софтбокс скользит вдоль стены (рельеф), мягкая заливка со стороны камеры
    area_light('key', (float(A.get('key_x', 1.8)), -float(A.get('key_off', 0.32)), float(A.get('key_z', 1.35))),
               (0.0, 0.0, 1.0), float(A.get('key_w', 0.45)), float(A.get('key_h', 2.4)), float(A.get('key', 420)),
               (1.0, 0.96, 0.90), spread=float(A.get('key_spread', 75)))
    if view == 'close':
        cam_loc, look, lens = (-0.80, -0.62, 1.02), (0.12, 0.0, 0.92), float(A.get('lens', 45))
    else:
        cam_loc, look, lens = (float(A.get('cx', -1.25)), float(A.get('cy', -2.15)), float(A.get('cz', 1.05))), \
                              (float(A.get('lx', 0.12)), 0.0, float(A.get('lz', 0.78))), float(A.get('lens', 32))
    area_light('fill', (cam_loc[0] * 1.3, cam_loc[1] * 1.3, 1.8), (0.0, 0.0, 0.9), 1.6, 1.6, float(A.get('fill', 30)),
               (0.94, 0.96, 1.0), spread=70)
    wo = bpy.data.worlds.new('W')
    scene.world = wo
    wo.use_nodes = True
    g = float(A.get('amb', 0.02))
    wo.node_tree.nodes['Background'].inputs['Color'].default_value = (g, g, g * 1.05, 1)
    camera(cam_loc, look, lens=lens, fstop=float(A.get('fstop', 0)) or None, level=True)


def scene_sample():
    """Образец-отрезок стоя, лицом к камере, на прозрачном фоне (фон и тень добавляет compose.py, как у фото).
    Нужен вместо фото «стоя» с телефона: там отрезок выходит трапецией и края кривые. Профиль — по чертежу (PROF),
    длина отрезка как у живых образцов ≈ 148 мм. Камера по горизонту: вертикали строго вертикальны."""
    item = A.get('item', 'a902').replace('gs', 'GS ').upper().replace('GS  ', 'GS ')
    if item == 'A910':              # A910 — по живому образцу (валик 6,5…12 мм), каталог врёт
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        import a910_profile as AP
        pts = sorted({(round(x, 3), round(z, 3)) for x, z, t in AP.outline() if t == 'f' and z > 0.01})
    elif item == 'A903':
        pts = prof_points('a903')
    else:
        pts = [(float(x), float(h)) for x, h in json.load(open(f'{ROOT}/profiles_site.json', encoding='utf-8'))[item]]
    W = max(x for x, _ in pts)
    L = float(A.get('len', 0.148))
    mp = mat_simple('white_paint', hexcol(A.get('paint', 'EFEEEA')), rough=float(A.get('paint_rough', 0.6)),
                    bump=0.015, bump_scale=1800.0)
    ob = profile_panel('sample', pts, -W / 2000.0, L, mp)
    try:
        bv = ob.modifiers.new('bevel', 'BEVEL')
        bv.width, bv.segments, bv.limit_method = 0.0004, 2, 'ANGLE'
        bv.angle_limit = R(30)
        bv.harden_normals = False
    except Exception as e:  # noqa
        log('bevel', e)
    scene.render.film_transparent = True
    zc = L * float(A.get('camz', 0.97))
    d = float(A.get('dist', 0.62))
    cam_loc = (float(A.get('camx', 0.0)), -d, zc)
    look = (0.0, 0.0, L * 0.5)
    # свет как на фото у окна: большой мягкий сверху-слева-спереди, слабая заливка справа, контровой сзади-сверху
    kx, ky, kz = (float(v) for v in A.get('keypos', '-0.45,-0.55,0.7').split(','))
    area_light('key', (kx, ky, L * 0.5 + kz), (0.0, -0.01, L * 0.5), float(A.get('ksize', 0.7)), float(A.get('ksize', 0.7)),
               float(A.get('key', 55)), (1.0, 0.98, 0.95), spread=float(A.get('kspread', 120)))
    area_light('fill', (0.55, -0.6, L * 0.6), (0.0, 0.0, L * 0.5), 0.9, 0.9, float(A.get('fill', 14)),
               (0.95, 0.97, 1.0), spread=120)
    area_light('top', (0.0, 0.05, L + 0.5), (0.0, -0.02, L), 0.5, 0.3, float(A.get('top', 20)), spread=90)
    wo = bpy.data.worlds.new('W')
    scene.world = wo
    wo.use_nodes = True
    g = float(A.get('amb', 0.06))
    wo.node_tree.nodes['Background'].inputs['Color'].default_value = (g, g, g, 1)
    camera(cam_loc, look, lens=float(A.get('lens', 60)), level=True)


def scene_piece():
    """Отрезок-образец молдинга, плинтуса, карниза или уголка (≈100 мм) на прозрачном фоне — для позиций,
    которых нет среди живых образцов. Вид и свет — как на фото образцов Михаила: view=a|b — лежит лицом вверх,
    срез к камере (два ракурса), view=c — стоит на торце лицом к камере. Контур — profiles_mold.json
    (x поперёк, y от стены к лицу, мм). Срез — белая зернистая пена. Фон и тень добавляет compose.py."""
    from mathutils import Matrix
    item = A.get('item', 'A157')
    view = A.get('view', 'a')
    if item[:1] in '235' and item[1:2] == '-':
        return scene_slat_piece(item, view)
    P = json.load(open(f'{ROOT}/profiles_mold.json', encoding='utf-8'))[item]
    W, T = float(P['w']) / 1000.0, float(P['t']) / 1000.0
    L = float(A.get('len', 0.10))
    cu = bpy.data.curves.new('prof', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    for loop in [P['outer']] + [h for h in (P.get('holes') or []) if len(h) > 2]:
        sp = cu.splines.new('POLY')
        sp.points.add(len(loop) - 1)
        for pt, (x, y) in zip(sp.points, loop):
            pt.co = (x / 1000.0, y / 1000.0, 0.0, 1.0)
        sp.use_cyclic_u = True
    cu.extrude = L / 2.0
    tmp = bpy.data.objects.new('prof_c', cu)
    col.objects.link(tmp)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    me.transform(Matrix.Translation((-W / 2.0, 0.0, 0.0)))
    mp = mat_simple('white_paint_piece', hexcol(A.get('paint', 'EFEEEA')), rough=float(A.get('paint_rough', 0.7)))
    me.materials.append(mp)
    mf = mat_foam_white()
    for nd in mf.node_tree.nodes:            # срез на фото почти такой же светлый, как лицо
        if nd.type == 'BSDF_PRINCIPLED':
            nd.inputs['Base Color'].default_value = (0.86, 0.86, 0.85, 1.0)
    me.materials.append(mf)
    for poly in me.polygons:
        cap = abs(poly.normal.z) > 0.9
        poly.material_index = 1 if cap else 0
        poly.use_smooth = not cap
    try:
        me.set_sharp_from_angle(angle=R(35))
    except Exception as e:  # noqa
        log('sharp', e)
    ob = bpy.data.objects.new('piece', me)
    col.objects.link(ob)
    _piece_stage(ob, W, T, L, view)

def _piece_stage(ob, W, T, L, view):
    """Постановка отрезка: положение, камера и свет трёх видов (a, b — лёжа, c — стоя)."""
    scene.render.film_transparent = True
    big = max(W, L)
    if view == 'c':                      # стоит на торце, лицом к камере
        ob.rotation_euler = (0.0, 0.0, math.pi)
        ob.location = (0.0, 0.0, L / 2.0)
        cam_loc, look, lens, level = (0.0, -0.42, L * 0.95), (0.0, 0.0, L * 0.5), 60.0, True
        key = (-0.50, -0.30, L * 0.5 + 0.30)
    else:                                # лежит лицом вверх, срез к камере
        yaw = R(float(A.get('yaw', -34 if view == 'a' else 40)))
        ob.rotation_euler = (math.pi / 2.0, 0.0, yaw)
        d = 0.12 + 2.2 * big
        el = R(float(A.get('elev', 36 if view == 'a' else 28)))
        cam_loc, look, lens, level = (0.0, -d * math.cos(el), d * math.sin(el)), (0.0, 0.0, T * 0.4), 70.0, False
        key = (-0.30, -0.10, 0.55)
    if view != 'c':
        key = (-0.25, -0.35, 0.50)
    area_light('key', key, (0.0, 0.0, T * 0.5), 0.6, 0.6, float(A.get('key', 50)), (1.0, 0.98, 0.95), spread=140)
    area_light('front', (0.10, -0.60, 0.16), (0.0, 0.0, T * 0.5), 0.7, 0.5, float(A.get('front', 38)), (1.0, 1.0, 1.0), spread=140)
    area_light('fill', (0.45, -0.30, 0.30), (0.0, 0.0, T * 0.5), 0.8, 0.8, float(A.get('fill', 14)), (0.95, 0.97, 1.0), spread=140)
    area_light('top', (0.05, 0.10, 0.60), (0.0, 0.0, 0.0), 0.5, 0.5, float(A.get('top', 14)), spread=120)
    wo = bpy.data.worlds.new('W')
    scene.world = wo
    wo.use_nodes = True
    g = float(A.get('amb', 0.25))
    wo.node_tree.nodes['Background'].inputs['Color'].default_value = (g, g, g, 1)
    camera(cam_loc, look, lens=lens, level=level)



EXPO_HOOK = None      # своя экспозиция сцены (если задана) вместо auto_expose по светлому месту


def scene_slat_piece(item, view):
    """Отрезок реечной панели «под дерево» (серии 2, 3, 5; 120×12 мм) — карточка товара в стиле фото живых образцов.
    Геометрия — slat_profile.py (сечение по фото торца живого образца 16.11.2026: наклонные стенки пазов, пустоты под
    рейками, свес с ножкой и полка). Серия 3: рейка 29,5 / шаг 40; серия 5: рейка 10,5 / шаг 24, рейки сплошные;
    серия 2: рейка 30 / шаг 60 — по фото каталога, с образцом не сверена. Плёнка-декор только на лице реек: у каждой рейки своя текстура tex_decor/<артикул>_<i>.jpg
    (рейки с фото каталога, выпрямлены tools/decor_tex.py). Бока и пазы чёрные, срез — тёмная пена.
    Цвет: вид Standard, экспозиция по лицу реек (серый шар 0,5 вместо плёнки) — декор выходит как на фото каталога."""
    global EXPO_HOOK
    from mathutils import Matrix
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import slat_profile as SP
    n = int(item[0])
    SP.STEP, SP.LAM = SP.SERIES[n]
    r_top = float(A.get('rtop', 1.4 if n == 5 else 0.8))
    mirror = True                        # полка: лёжа «а» — слева у зрителя (срез справа), стоя — справа, как на фото образцов;
    A.setdefault('yaw', '36' if view == 'a' else '-36')   # вид «б» — с другой стороны: у зрителя край первой рейки с ножкой
    W, T, L = 0.12, 0.012, float(A.get('len', 0.10))
    pts = [(x, z) for x, z, _ in SP.rounded(SP.outline(n), r_top=r_top, r=0.4, seg=5)]
    if mirror:
        pts = [(120.0 - x, z) for x, z in reversed(pts)]
    cu = bpy.data.curves.new('slat', 'CURVE')
    cu.dimensions = '2D'
    cu.fill_mode = 'BOTH'
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for pt, (x, y) in zip(sp.points, pts):
        pt.co = (x / 1000.0, y / 1000.0, 0.0, 1.0)
    sp.use_cyclic_u = True
    cu.extrude = L / 2.0
    tmp = bpy.data.objects.new('slat_c', cu)
    col.objects.link(tmp)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp)
    me.transform(Matrix.Translation((-W / 2.0, 0.0, 0.0)))
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name='decor')
    bk = float(A.get('black', 0.006))
    m_black = mat_simple('pan_black_piece', (bk, bk, bk * 1.08, 1), rough=float(A.get('brough', 0.3)))
    me.materials.append(m_black)
    me.materials.append(mat_foam())
    info = json.load(open(f'{ROOT}/tex_decor/index.json', encoding='utf-8'))[item]
    woods = []
    for i in range(n):
        m, nt, out = new_mat(f'wood_piece_{i}')
        bs = principled(nt, out, Roughness=float(A.get('wrough', 0.6)), **{'Specular IOR Level': float(A.get('wspec', 0.35))})
        tx = nt.nodes.new('ShaderNodeTexImage')
        tx.image = bpy.data.images.load(f'{ROOT}/tex_decor/{item}_{i}.jpg')
        tx.interpolation = 'Cubic'
        tx.extension = 'MIRROR'
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'decor'
        nt.links.new(uvn.outputs['UV'], tx.inputs['Vector'])
        nt.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
        me.materials.append(m)
        woods.append(m)
    step, lam = SP.STEP / 1000.0, SP.LAM / 1000.0
    nw = 0
    for poly in me.polygons:
        if abs(poly.normal.z) > 0.9:
            poly.material_index = 1
            continue
        xo = poly.center.x + W / 2.0
        if mirror:
            xo = W - xo
        i = min(n - 1, max(0, int((xo + 1e-6) // step)))
        if poly.center.y > T - (0.9 * r_top + 0.05) / 1000.0 and xo - i * step < lam + 0.001:
            poly.material_index = 2 + i
            nw += 1
            ratio = info['ratio'][min(i, len(info['ratio']) - 1)]
            for li in poly.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                x = co.x + W / 2.0
                if mirror:
                    x = W - x
                uv.data[li].uv = ((x - i * step) / lam, 1.0 - (co.z + L / 2.0) / (lam * ratio))
        else:
            poly.material_index = 0
    log('slat piece', item, 'wood faces', nw, 'mirror', mirror)
    ob = bpy.data.objects.new('piece', me)
    col.objects.link(ob)
    _piece_stage(ob, W, T, L, view)
    vs = scene.view_settings
    try:
        vs.view_transform = A.get('vt', 'Standard')
        vs.look = 'None'
    except Exception as e:  # noqa
        log('view', e)

    def expose_face():
        gray = mat_simple('cal_gray', (0.5, 0.5, 0.5, 1), rough=1.0, **{'Specular IOR Level': 0.0})
        for i in range(n):
            me.materials[2 + i] = gray
        rw = 280
        rh = max(2, int(round(rw * H_PX / W_PX)))
        lu = lum(render_linear(rw, rh, 48, 'ae').astype(np.float64))
        for i in range(n):
            me.materials[2 + i] = woods[i]
        sel = lu[lu > 0.3 * float(np.percentile(lu, 99.5))]
        face = float(np.median(sel)) if sel.size else 0.25
        ev = math.log2(0.5 * float(A.get('gain', 0.92)) / max(face, 1e-6)) + EV
        scene.view_settings.exposure = ev
        log('face exposure: gray face %.4f -> exposure %.2f' % (face, ev))
    EXPO_HOOK = expose_face


def auto_expose():
    """Экспозиция по самому светлому месту кадра (белое изделие не выгорает, фон остаётся тёмным)."""
    if EXPO_HOOK:
        return EXPO_HOOK()
    rw = 240
    rh = max(2, int(round(rw * H_PX / W_PX)))
    px = render_linear(rw, rh, 32, 'ae')
    hi = float(np.percentile(lum(px.astype(np.float64)), float(A.get('pct', 99.3))))
    target = float(A.get('target', 0.9 if A.get('item', '') == 'slat' else 2.0))
    ev = math.log2(target / max(hi, 1e-6)) + EV
    scene.view_settings.exposure = ev
    log('auto exposure: p%.1f=%.4f -> exposure %.2f' % (float(A.get('pct', 99.3)), hi, ev))


# ------------------------------------------------------------------ галерея применений для сайта (use=tv|tv1|tv2|sofa|bed|hall|cor|cl)
def pillow(name, loc, w, d, h, mat, rot=0.0, tilt=0.0, n=20):
    """Подушка: w × d в плане, толщина h в середине, к краям сходит на нет. tilt — наклон вокруг оси X (градусы), rot — поворот вокруг Z."""
    V, F, UV = [], [], []
    for sgn in (1, -1):
        base = len(V)
        for j in range(n + 1):
            for i in range(n + 1):
                u, v = -1 + 2 * i / n, -1 + 2 * j / n
                t = h * 0.5 * max(0.0, (1 - u ** 4) * (1 - v ** 4)) ** 0.6
                V.append((u * w / 2 * (1 - 0.05 * v * v), v * d / 2 * (1 - 0.05 * u * u), sgn * t))
        for j in range(n):
            for i in range(n):
                q = base + j * (n + 1) + i
                f = (q, q + 1, q + n + 2, q + n + 1)
                F.append(f if sgn > 0 else tuple(reversed(f)))
                UV.append([(V[k][0], V[k][1]) for k in F[-1]])
    ob = make_obj(name, V, F, [mat], uvs=UV, smooth=[True] * len(F))
    ob.location = loc
    ob.rotation_euler = (R(tilt), 0.0, R(rot))
    return ob


def disc_y(name, x, y, z, r, mat, n=72):
    """Круг в плоскости стены (лицом к −Y)."""
    V = [(x + r * math.cos(2 * math.pi * i / n), y, z + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return make_obj(name, V, [tuple(range(n))], [mat])


def sofa(xc, yb, length=2.3, depth=0.95):
    """Прямой диван у стены: основание, спинка, подлокотники, подушки сиденья и спинки, две декоративные подушки, плед."""
    mf = mat_pbr('sofa_fabric', 'rough_linen', 0.5, tint=srgb(196, 190, 180), nstrength=1.3)
    x0, x1, yf, arm = xc - length / 2, xc + length / 2, yb - depth, 0.17
    box('sofa_base', x0, x1, yf + 0.03, yb, 0.11, 0.30, mf, bevel=0.03)
    box('sofa_back', x0, x1, yb - 0.19, yb, 0.30, 0.76, mf, bevel=0.05)
    box('sofa_arm_l', x0, x0 + arm, yf + 0.03, yb, 0.30, 0.62, mf, bevel=0.05)
    box('sofa_arm_r', x1 - arm, x1, yf + 0.03, yb, 0.30, 0.62, mf, bevel=0.05)
    ml = mat_simple('sofa_legs', srgb(52, 40, 30), rough=0.5)
    for k, (lx, ly) in enumerate(((x0 + 0.08, yf + 0.10), (x1 - 0.08, yf + 0.10), (x0 + 0.08, yb - 0.08), (x1 - 0.08, yb - 0.08))):
        cyl(f'sofa_leg{k}', lx, ly, 0.0, 0.11, 0.018, 0.025, ml)
    n = 3
    sw = (length - 2 * arm) / n
    for i in range(n):
        xa = x0 + arm + i * sw
        box(f'sofa_seat{i}', xa + 0.005, xa + sw - 0.005, yf, yb - 0.19, 0.30, 0.46, mf, bevel=0.045)
        pillow(f'sofa_bk{i}', (xa + sw / 2, yb - 0.27, 0.69), sw - 0.03, 0.50, 0.20, mf, tilt=78)
    pillow('sofa_p1', (x0 + arm + 0.26, yb - 0.40, 0.66), 0.46, 0.46, 0.15, mat_pbr('pil_sage', 'rough_linen', 0.4, tint=srgb(132, 150, 138), nstrength=1.3), rot=-14, tilt=64)
    pillow('sofa_p2', (x1 - arm - 0.30, yb - 0.41, 0.65), 0.50, 0.42, 0.14, mat_pbr('pil_sand', 'rough_linen', 0.4, tint=srgb(222, 208, 186), nstrength=1.3), rot=12, tilt=62)
    box('sofa_throw', x1 - arm - 0.02, x1 + 0.012, yf - 0.012, yb - 0.30, 0.20, 0.625, mat_pbr('throw', 'rough_linen', 0.35, tint=srgb(186, 128, 98), nstrength=1.5), bevel=0.012)


def bed(xc, yb, width=1.8, length=2.06, wood=True):
    """Кровать у стены без своего изголовья (изголовье — стена из панелей): основание, матрас, одеяло с отворотом, подушки, плед."""
    mb = mat_pbr('bed_frame', 'rough_linen', 0.5, tint=srgb(170, 162, 150), nstrength=1.3)
    mwh = mat_pbr('bed_white', 'rough_linen', 0.45, tint=srgb(244, 241, 235), nstrength=0.9)
    mln = mat_pbr('bed_linen', 'rough_linen', 0.45, tint=srgb(226, 219, 206), nstrength=1.2)
    x0, x1, yf = xc - width / 2, xc + width / 2, yb - length
    box('bed_base', x0 - 0.03, x1 + 0.03, yf - 0.03, yb, 0.10, 0.32, mb, bevel=0.025)
    ml = mat_simple('bed_legs', srgb(52, 40, 30), rough=0.5)
    for k, (lx, ly) in enumerate(((x0 + 0.06, yf + 0.06), (x1 - 0.06, yf + 0.06))):
        cyl(f'bed_leg{k}', lx, ly, 0.0, 0.10, 0.02, 0.028, ml)
    box('bed_matt', x0, x1, yf, yb - 0.01, 0.32, 0.54, mwh, bevel=0.05)
    box('bed_duvet', x0 - 0.035, x1 + 0.035, yf - 0.02, yb - 0.74, 0.47, 0.615, mln, bevel=0.055)
    box('bed_fold', x0 - 0.03, x1 + 0.03, yb - 0.93, yb - 0.70, 0.565, 0.655, mwh, bevel=0.04)
    pw = width / 2 - 0.07
    for i, sx in enumerate((-1, 1)):
        pillow(f'bed_pil{i}', (xc + sx * (pw / 2 + 0.025), yb - 0.20, 0.76), pw, 0.50, 0.19, mwh, tilt=72)
    pillow('bed_p1', (xc - 0.33, yb - 0.44, 0.71), 0.48, 0.40, 0.15, mat_pbr('pil_sage', 'rough_linen', 0.4, tint=srgb(132, 150, 138), nstrength=1.3), rot=-8, tilt=60)
    pillow('bed_p2', (xc + 0.30, yb - 0.46, 0.69), 0.55, 0.32, 0.13, mat_pbr('pil_sand', 'rough_linen', 0.4, tint=srgb(214, 196, 170), nstrength=1.3), rot=6, tilt=58)
    box('bed_throw', x0 - 0.045, x1 + 0.045, yf + 0.10, yf + 0.62, 0.60, 0.635, mat_pbr('throw', 'rough_linen', 0.35, tint=srgb(186, 128, 98), nstrength=1.5), bevel=0.012)


def door_x(name, xw, y0, y1, mat):
    """Дверь в правой стене (x = xw): полотно, наличники, ручка."""
    box(name + '_leaf', xw - 0.036, xw - 0.006, y0, y1, 0.0, 2.05, mat, bevel=0.002)
    for k, (a, b, z0, z1) in enumerate(((y0 - 0.07, y0, 0.0, 2.12), (y1, y1 + 0.07, 0.0, 2.12), (y0 - 0.07, y1 + 0.07, 2.05, 2.12))):
        box(f'{name}_cas{k}', xw - 0.046, xw, a, b, z0, z1, mat, bevel=0.003)
    mh = mat_simple('handle', (0.02, 0.02, 0.022, 1), rough=0.35, metallic=1.0)
    box(name + '_h1', xw - 0.085, xw - 0.036, y0 + 0.075, y0 + 0.095, 1.0, 1.02, mh)
    box(name + '_h2', xw - 0.085, xw - 0.067, y0 + 0.075, y0 + 0.20, 1.0, 1.02, mh, bevel=0.002)


def door_y(name, x0, x1, mat):
    """Дверь в стене y = 0 (напротив панелей)."""
    box(name + '_leaf', x0, x1, 0.006, 0.036, 0.0, 2.05, mat, bevel=0.002)
    for k, (a, b, z0, z1) in enumerate(((x0 - 0.07, x0, 0.0, 2.12), (x1, x1 + 0.07, 0.0, 2.12), (x0 - 0.07, x1 + 0.07, 2.05, 2.12))):
        box(f'{name}_cas{k}', a, b, 0.0, 0.046, z0, z1, mat, bevel=0.003)
    mh = mat_simple('handle', (0.02, 0.02, 0.022, 1), rough=0.35, metallic=1.0)
    box(name + '_h1', x0 + 0.075, x0 + 0.095, 0.036, 0.085, 1.0, 1.02, mh)
    box(name + '_h2', x0 + 0.075, x0 + 0.20, 0.067, 0.085, 1.0, 1.02, mh, bevel=0.002)


def scene_use():
    """Галерея «где и как применяют» для сайта. use: tv — ТВ-зона, вся стена; tv1 — одна полоса за экраном; tv2 — две полосы, экран между ними;
    sofa — за диваном; bed — спальня; hall — прихожая; cor — коридор; cl — крупно. Панель — decor=…, как в lounge."""
    use = A.get('use', 'tv')
    lamps = []
    az, el = float(A.get('sun_az', 32)), float(A.get('sun_el', 52))
    sun_dir = Vector((math.cos(R(el)) * math.cos(R(az)), math.cos(R(el)) * math.sin(R(az)), -math.sin(R(el))))
    m_wall = mat_pbr('wall_paint', 'beige_wall_001', 3.0, color=srgb(236, 232, 224), rough=0.9, nstrength=0.6)
    m_ceil = mat_simple('ceil_paint', srgb(244, 243, 240), rough=0.95)
    m_floor = mat_pbr('floor', 'laminate_floor_02', 1.7, rough_add=-0.05, nstrength=0.8, rot=R(90), tint=srgb(232, 222, 210))
    m_rug = mat_pbr('rug', 'hessian_230', 0.55, tint=srgb(240, 232, 218), nstrength=1.5)
    cabcol = hexcol(A.get('cabcol', 'C9B8A0'))
    m_door = mat_simple('door_white', srgb(240, 239, 235), rough=0.4)
    if use == 'cor':
        W, D, H = 6.2, 1.5, 2.7
        room(W, D, H, win=(0.2, 1.3, 0.06, 2.4), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil)
        panel_wall(0.0, W, H, D)
        for k, x0 in enumerate((1.75, 4.05)):
            door_y(f'door{k}', x0, x0 + 0.82, m_door)
        door_x('door_end', W, 0.34, 1.16, m_door)
        mp = mat_simple('plinth2', srgb(240, 240, 238), rough=0.4)
        for k, (a, b) in enumerate(((0.0, 1.68), (2.64, 3.98), (4.94, W))):
            box(f'plinth_f{k}', a, b, 0.0, 0.013, 0.0, 0.08, mp, bevel=0.002)
        box('runner', 0.6, 5.7, 0.40, 1.10, 0.0, 0.01, m_rug, bevel=0.003)
        load_asset('potted_plant_02', loc=(5.9, 0.30, 0), rot=20)
        world, sun = setup_world(sun_dir)
        cal = camera((0.85, 0.45, 1.42), (5.4, 1.32, 1.15), lens=float(A.get('lens', 21)))
        return world, sun, sun_dir, lamps, cal
    W, D, H = 4.4, 5.2, 2.7
    room(W, D, H, win=(2.3, 4.7, 0.06, 2.46), m_wall=m_wall, m_floor=m_floor, m_ceil=m_ceil)
    for a, b in {'tv1': [(1.2, 3.1)], 'tv2': [(0.38, 1.10), (3.20, 3.92)]}.get(use, [(0.0, W)]):
        panel_wall(a, b, H, D)
    curtain('sheer', 0.12, 2.1, 4.95, 0.012, 2.64, mat_sheer())
    box('track', 0.07, 0.17, 2.0, 5.05, 2.64, 2.67, mat_simple('track', srgb(240, 240, 238), rough=0.4))
    yw = D - 0.012 - 0.015
    world, sun = setup_world(sun_dir)
    cal = camera((2.55, 0.75, 1.22), (2.15, D, 1.02), lens=30, fstop=5.6, focus=4.3)
    if use in ('tv', 'tv1', 'tv2', 'cl'):
        yc = yw - 0.21
        top = credenza(1.2, 3.1, yw, color=cabcol)
        ms = mat_simple('tv_screen', (0.012, 0.012, 0.014, 1), rough=1.0, **{'Specular IOR Level': 0.0})
        mb = mat_simple('tv_body', (0.01, 0.01, 0.011, 1), rough=0.4)
        tw, th, tz = 1.45, 0.83, 1.32
        box('tv_body', 2.15 - tw / 2, 2.15 + tw / 2, D - 0.012 - 0.045, D - 0.012 - 0.012, tz - th / 2, tz + th / 2, mb, bevel=0.002)
        box('tv_screen', 2.15 - tw / 2 + 0.008, 2.15 + tw / 2 - 0.008, D - 0.012 - 0.0465, D - 0.012 - 0.045, tz - th / 2 + 0.008, tz + th / 2 - 0.012, ms)
        zz = books(1.55, yc - 0.02, top, 3, seed=4)
        load_asset('ceramic_vase_02', loc=(1.55, yc - 0.02, zz), rot=20)
        load_asset('ceramic_vase_03', loc=(2.85, yc - 0.03, top), rot=10)
        load_asset('potted_plant_04', loc=(2.62, yc + 0.02, top), rot=40)
        load_asset('potted_plant_01', loc=(0.62, 3.75, 0) if use == 'tv2' else (0.72, D - 0.55, 0), rot=35)
        box('rug', 1.5, 4.15, 2.6, 4.45, 0.0, 0.012, m_rug, bevel=0.004)
        if use == 'cl':
            camera((3.0, 4.55, 1.2), (3.75, D - 0.012, 1.15), lens=60)
        else:
            camera((3.7, 1.9, 1.25), (1.9, D, 0.95), lens=26)
    elif use == 'sofa':
        sofa(2.2, yw, 2.3)
        mw = mat_pbr('tbl_wood', 'oak_veneer_01', 1.83, rough=0.45, tint=srgb(206, 180, 150))
        mk = mat_simple('tbl_legs', (0.012, 0.012, 0.013, 1), rough=0.42, metallic=1.0)
        cyl('st_top', 3.75, yw - 0.34, 0.50, 0.522, 0.23, 0.23, mw)                    # столик с лампой
        cyl('st_stem', 3.75, yw - 0.34, 0.012, 0.50, 0.016, 0.016, mk)
        cyl('st_base', 3.75, yw - 0.34, 0.0, 0.012, 0.15, 0.15, mk)
        table_lamp(3.75, yw - 0.34, 0.522, lamps)
        cyl('ct_top', 2.3, 3.55, 0.33, 0.355, 0.45, 0.45, mw)                           # журнальный стол
        for k in range(3):
            a = 2 * math.pi * k / 3 + 0.5
            cyl(f'ct_leg{k}', 2.3 + 0.33 * math.cos(a), 3.55 + 0.33 * math.sin(a), 0.0, 0.33, 0.012, 0.014, mk)
        zz = books(2.2, 3.5, 0.355, 2, seed=6)
        load_asset('ceramic_vase_03', loc=(2.46, 3.62, 0.355), rot=30)
        load_asset('potted_plant_01', loc=(0.72, D - 0.55, 0), rot=35)
        box('rug', 0.95, 3.75, 2.7, 4.75, 0.0, 0.012, m_rug, bevel=0.004)
        camera((3.7, 1.9, 1.25), (1.9, D, 0.95), lens=26)
    elif use == 'bed':
        bed(2.2, yw, 1.8)
        mw = mat_pbr('tbl_wood', 'oak_veneer_01', 1.83, rough=0.45, tint=srgb(206, 180, 150))
        ml = mat_simple('ns_legs', srgb(52, 40, 30), rough=0.5)
        for k, xn in enumerate((0.96, 3.44)):
            box(f'ns{k}', xn - 0.24, xn + 0.24, yw - 0.40, yw, 0.14, 0.50, mw, bevel=0.006)
            for q, (lx, ly) in enumerate(((xn - 0.2, yw - 0.36), (xn + 0.2, yw - 0.36), (xn - 0.2, yw - 0.04), (xn + 0.2, yw - 0.04))):
                cyl(f'ns{k}leg{q}', lx, ly, 0.0, 0.14, 0.012, 0.016, ml)
            table_lamp(xn, yw - 0.2, 0.50, lamps)
        zz = books(3.44 + 0.02, yw - 0.33, 0.50, 2, seed=8)
        load_asset('potted_plant_01', loc=(0.6, 3.3, 0), rot=35)
        box('rug', 0.75, 3.65, 2.35, 4.35, 0.0, 0.012, m_rug, bevel=0.004)
        camera((3.85, 1.6, 1.4), (1.9, D, 0.9), lens=26)
    elif use == 'hall':
        top = credenza(1.42, 2.32, yw, z0=0.12, h=0.70, depth=0.32, n_doors=2, color=cabcol)       # обувница и круглое зеркало над ней
        disc_y('mirror_frame', 1.87, yw - 0.004, 1.52, 0.385, mat_simple('mir_fr', (0.015, 0.015, 0.016, 1), rough=0.4))
        disc_y('mirror', 1.87, yw - 0.008, 1.52, 0.37, mat_simple('mirror', (0.92, 0.92, 0.92, 1), rough=0.02, metallic=1.0))
        load_asset('ceramic_vase_02', loc=(1.62, yw - 0.16, top), rot=20)
        books(2.08, yw - 0.16, top, 2, seed=5)
        bench(2.62, 3.72, yw)                                                                   # скамья, подушка, вешалка с сумкой
        box('bench_pad', 2.66, 3.30, yw - 0.345, yw - 0.02, 0.44, 0.50, mat_pbr('pad', 'rough_linen', 0.4, tint=srgb(196, 190, 180), nstrength=1.3), bevel=0.022)
        mw = mat_pbr('rail_wood', 'oak_veneer_01', 1.83, rough=0.45, tint=srgb(206, 180, 150))
        box('rail', 2.62, 3.72, yw - 0.022, yw, 1.62, 1.70, mw, bevel=0.003)
        for k in range(5):
            xk = 2.74 + k * 0.215
            box(f'peg{k}', xk - 0.012, xk + 0.012, yw - 0.085, yw - 0.02, 1.648, 1.672, mw, bevel=0.003)
        mbag = mat_pbr('bag', 'rough_linen', 0.35, tint=srgb(132, 150, 138), nstrength=1.4)
        box('bag', 3.385 - 0.17, 3.385 + 0.17, yw - 0.105, yw - 0.035, 1.0, 1.36, mbag, bevel=0.02)
        for k, dx in enumerate((-0.085, 0.07)):
            box(f'bag_strap{k}', 3.385 + dx, 3.385 + dx + 0.015, yw - 0.075, yw - 0.068, 1.35, 1.66, mbag)
        door_x('door_in', W, 3.45, 4.33, m_door)
        load_asset('potted_plant_02', loc=(4.05, yw - 0.28, 0), rot=10)
        box('rug', 2.2, 4.05, 3.1, 4.55, 0.0, 0.012, m_rug, bevel=0.004)
        camera((2.5, 2.3, 1.35), (3.0, D, 1.05), lens=float(A.get('lens', 27)))
    return world, sun, sun_dir, lamps, cal


SCENES = {'use': scene_use, 'lounge': scene_lounge, 'arch': scene_arch, 'plinth': scene_plinth, 'studio': scene_studio, 'sample': scene_sample, 'piece': scene_piece}

setup_render()
if SCENE in ('studio', 'sample', 'piece'):
    SCENES[SCENE]()
    bpy.context.view_layer.update()
    log('objects', len(scene.objects), 'studio built')
    auto_expose()
else:
    world, sun, sun_dir, lamps, cal_cam = SCENES[SCENE]()
    bpy.context.view_layer.update()
    log('objects', len(scene.objects), 'scene built')
    if A.get('mask') == '1':
        make_mask(world, sun, lamps)
    else:
        calibrate(world, sun, sun_dir, neutral_prefixes=NEUTRAL, lamps=lamps, cal_cam=cal_cam)
render_final()
log('done')
