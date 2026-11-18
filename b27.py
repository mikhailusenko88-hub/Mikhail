# Blender: кадры плана из движка «Мультиков» → свет и рендер Cycles.
#   blender -b --factory-startup -P b27.py -- --in папка --frames 0-4 --out рендеры [--w 1280] [--samples 96] [--test]
# Геометрия героев, поз, шерсти и комнаты — из движка (f_NNN.json/.bin), здесь только материалы, свет, камера и рендер.
import bpy, sys, os, json, math, time
import numpy as np
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def opt(k, d=None):
    return argv[argv.index('--' + k) + 1] if '--' + k in argv else d
IN = opt('in', 'fr'); OUT = opt('out', 'out'); W = int(opt('w', '1280')); H = W * 9 // 16
SPP = int(opt('samples', '96')); FR = opt('frames', '0-0'); TEST = '--test' in argv
a, b = (FR.split('-') + [FR])[:2]; FRAMES = list(range(int(a), int(b) + 1))
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
def log(*x): print('[%6.1fs]' % (time.time() - T0), *x, flush=True)

# ---------- сцена ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
S.render.engine = 'CYCLES'; S.cycles.device = 'CPU'
S.cycles.samples = SPP; S.cycles.use_adaptive_sampling = True; S.cycles.adaptive_threshold = 0.02
S.cycles.use_denoising = True; S.cycles.denoiser = 'OPENIMAGEDENOISE'
try: S.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
except Exception: pass
S.cycles.max_bounces = 6; S.cycles.diffuse_bounces = 3; S.cycles.glossy_bounces = 3; S.cycles.transmission_bounces = 4; S.cycles.transparent_max_bounces = 8
S.cycles.sample_clamp_indirect = 8.0; S.cycles.caustics_reflective = False; S.cycles.caustics_refractive = False
S.render.resolution_x = W; S.render.resolution_y = H; S.render.resolution_percentage = 100
S.render.image_settings.file_format = 'PNG'; S.render.image_settings.color_mode = 'RGB'
S.view_settings.view_transform = opt('view', 'Khronos PBR Neutral')
try: S.view_settings.look = opt('look', 'None')
except Exception: pass
S.view_settings.exposure = float(opt('exposure', '0.0'))
S.render.threads_mode = 'AUTO'
try: S.cycles_curves.shape = opt('hair', 'RIBBONS')
except Exception: pass

# три.js (Y вверх) → Blender (Z вверх)
C3 = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32)
def conv(P): P = P.reshape(-1, 3); return np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1).astype(np.float32)
C4 = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

# ---------- материалы ----------
MAT = {}
def nodes(m):
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); out = nt.nodes.new('ShaderNodeOutputMaterial'); return nt, out

def mat_attr_principled(name, rough=0.6, sss=0.0, sheen=0.0, mixB=False):
    if name in MAT: return MAT[name]
    m = bpy.data.materials.new(name); nt, out = nodes(m); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'col'; col = at.outputs['Color']
    if mixB:
        ab = nt.nodes.new('ShaderNodeAttribute'); ab.attribute_name = 'colB'; am = nt.nodes.new('ShaderNodeAttribute'); am.attribute_name = 'mix'
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
        nt.links.new(am.outputs['Fac'], mx.inputs[0]); nt.links.new(col, mx.inputs[6]); nt.links.new(ab.outputs['Color'], mx.inputs[7]); col = mx.outputs[2]
    nt.links.new(col, bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = rough
    if sss > 0:
        bs.inputs['Subsurface Weight'].default_value = sss; bs.inputs['Subsurface Radius'].default_value = (0.02, 0.008, 0.005); bs.inputs['Subsurface Scale'].default_value = 0.05
        nt.links.new(col, bs.inputs['Base Color'])
    if sheen > 0: bs.inputs['Sheen Weight'].default_value = sheen
    nt.links.new(bs.outputs[0], out.inputs[0]); MAT[name] = m; return m

def mat_hair(name, rough=0.35):
    # мех: рассеянный цвет волоска из движка + блик вдоль волоска (как у Kajiya-Kay в движке) + немного просвета
    if name in MAT: return MAT[name]
    m = bpy.data.materials.new(name); nt, out = nodes(m)
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'col'
    hi = nt.nodes.new('ShaderNodeHairInfo')
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['From Min'].default_value = 0.0; rr.inputs['From Max'].default_value = 1.0; rr.inputs['To Min'].default_value = float(opt('rootk', '0.62')); rr.inputs['To Max'].default_value = 1.0
    nt.links.new(hi.outputs['Intercept'], rr.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(at.outputs['Color'], mul.inputs[6]); nt.links.new(rr.outputs['Result'], mul.inputs[7])   # корни темнее, кончики светлее — как в движке
    df = nt.nodes.new('ShaderNodeBsdfDiffuse'); nt.links.new(mul.outputs[2], df.inputs['Color'])
    tl = nt.nodes.new('ShaderNodeBsdfTranslucent'); nt.links.new(mul.outputs[2], tl.inputs['Color'])
    hr = nt.nodes.new('ShaderNodeBsdfHair'); hr.component = 'Reflection'; hr.inputs['Color'].default_value = (1, 0.97, 0.92, 1); hr.inputs['RoughnessU'].default_value = 0.25; hr.inputs['RoughnessV'].default_value = 0.7
    m1 = nt.nodes.new('ShaderNodeMixShader'); m1.inputs[0].default_value = float(opt('transk', '0.15')); nt.links.new(df.outputs[0], m1.inputs[1]); nt.links.new(tl.outputs[0], m1.inputs[2])
    m2 = nt.nodes.new('ShaderNodeMixShader'); m2.inputs[0].default_value = float(opt('glossk', '0.12')); nt.links.new(m1.outputs[0], m2.inputs[1]); nt.links.new(hr.outputs[0], m2.inputs[2])
    nt.links.new(m2.outputs[0], out.inputs[0]); MAT[name] = m; return m

def mat_eye(name, img_path):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); nt, out = nodes(m)
    tc = nt.nodes.new('ShaderNodeTexCoord'); im = nt.nodes.new('ShaderNodeTexImage')
    im.image = bpy.data.images.load(img_path, check_existing=False); im.image.colorspace_settings.name = 'sRGB'; im.extension = 'EXTEND'; im.interpolation = 'Linear'
    nt.links.new(tc.outputs['Window'], im.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(im.outputs['Color'], em.inputs['Color']); em.inputs['Strength'].default_value = float(opt('eyek', '0.85'))
    gl = nt.nodes.new('ShaderNodeBsdfGlossy'); gl.inputs['Roughness'].default_value = 0.06
    ad = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(em.outputs[0], ad.inputs[0])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs[0].default_value = 0.1
    tr = nt.nodes.new('ShaderNodeHoldout') if False else None
    nt.links.new(em.outputs[0], mx.inputs[1]); nt.links.new(gl.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
    return m

def mat_std(md, texdir):
    key = json.dumps(md, sort_keys=True)
    if key in MAT: return MAT[key]
    m = bpy.data.materials.new('std'); nt, out = nodes(m)
    c = md.get('c', [1, 1, 1]); op = md.get('op', 1)
    base = None
    if md.get('map'):
        im = nt.nodes.new('ShaderNodeTexImage'); p = os.path.join(texdir, md['map']['id'] + '.png')
        if os.path.exists(p): im.image = bpy.data.images.load(p, check_existing=True); im.image.colorspace_settings.name = 'sRGB' if md['map'].get('srgb', True) else 'Non-Color'
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'UVMap'; nt.links.new(uv.outputs[0], im.inputs[0]); base = im
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'col'; at.attribute_type = 'GEOMETRY'
    rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (c[0], c[1], c[2], 1)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    nt.links.new(rgb.outputs[0], mul.inputs[6]); nt.links.new(at.outputs['Color'] if md.get('_vc') else rgb.outputs[0], mul.inputs[7])
    col = mul.outputs[2]
    if base is not None:
        mul2 = nt.nodes.new('ShaderNodeMix'); mul2.data_type = 'RGBA'; mul2.blend_type = 'MULTIPLY'; mul2.inputs[0].default_value = 1.0
        nt.links.new(col, mul2.inputs[6]); nt.links.new(base.outputs['Color'], mul2.inputs[7]); col = mul2.outputs[2]
    if md.get('_mixB'):
        ab = nt.nodes.new('ShaderNodeAttribute'); ab.attribute_name = 'colB'; am = nt.nodes.new('ShaderNodeAttribute'); am.attribute_name = 'mix'
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; nt.links.new(am.outputs['Fac'], mx.inputs[0]); nt.links.new(col, mx.inputs[6]); nt.links.new(ab.outputs['Color'], mx.inputs[7]); col = mx.outputs[2]
    if md.get('basic'):
        em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(col, em.inputs['Color']); em.inputs['Strength'].default_value = float(opt('basick', '0.75')); sh = em.outputs[0]
    else:
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); nt.links.new(col, bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = max(0.05, min(1.0, md.get('rough', 0.8))); bs.inputs['Metallic'].default_value = md.get('metal', 0)
        if md.get('tr', 0) > 0: bs.inputs['Transmission Weight'].default_value = md['tr']; bs.inputs['IOR'].default_value = md.get('ior', 1.5)
        if md.get('sheen', 0) > 0: bs.inputs['Sheen Weight'].default_value = md['sheen']
        if md.get('cc', 0) > 0: bs.inputs['Coat Weight'].default_value = md['cc']
        e = md.get('em', [0, 0, 0])
        if max(e) > 0.001 or md.get('emap'):
            bs.inputs['Emission Strength'].default_value = 1.0
            if md.get('emap') and os.path.exists(os.path.join(texdir, md['emap']['id'] + '.png')):
                ie = nt.nodes.new('ShaderNodeTexImage'); ie.image = bpy.data.images.load(os.path.join(texdir, md['emap']['id'] + '.png'), check_existing=True)
                uv2 = nt.nodes.new('ShaderNodeUVMap'); nt.links.new(uv2.outputs[0], ie.inputs[0])
                me = nt.nodes.new('ShaderNodeMix'); me.data_type = 'RGBA'; me.blend_type = 'MULTIPLY'; me.inputs[0].default_value = 1.0; me.inputs[6].default_value = (e[0], e[1], e[2], 1)
                nt.links.new(ie.outputs['Color'], me.inputs[7]); nt.links.new(me.outputs[2], bs.inputs['Emission Color'])
            else: bs.inputs['Emission Color'].default_value = (e[0], e[1], e[2], 1)
        if md.get('tp') and base is not None:
            ma = nt.nodes.new('ShaderNodeMath'); ma.operation = 'MULTIPLY'; ma.inputs[1].default_value = op; nt.links.new(base.outputs['Alpha'], ma.inputs[0]); nt.links.new(ma.outputs[0], bs.inputs['Alpha'])
        elif op < 0.999: bs.inputs['Alpha'].default_value = op
        sh = bs.outputs[0]
    nt.links.new(sh, out.inputs[0]); MAT[key] = m; return m

# ---------- геометрия ----------
def arr(B, d, dt=None):
    if not d: return None
    o, n, t = d; dt = dt or {'Float32Array': np.float32, 'Uint32Array': np.uint32}[t]
    return np.frombuffer(B, dt, count=n, offset=o)

def make_mesh(name, P, idx, col=None, uv=None, colB=None, mix=None, smooth=True):
    me = bpy.data.meshes.new(name); nv = len(P) // 1
    me.vertices.add(len(P)); me.vertices.foreach_set('co', P.ravel())
    nl = len(idx); nt = nl // 3; idx = idx[:nt * 3]
    me.loops.add(nt * 3); me.loops.foreach_set('vertex_index', idx.astype(np.int32))
    me.polygons.add(nt); me.polygons.foreach_set('loop_start', np.arange(0, nt * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    if col is not None:
        c = col.reshape(-1, 3)
        if len(c) == 1: c = np.repeat(c, len(P), 0)
        if len(c) == len(P):
            ca = me.color_attributes.new('col', 'FLOAT_COLOR', 'POINT'); rgba = np.ones((len(P), 4), np.float32); rgba[:, :3] = c; ca.data.foreach_set('color', rgba.ravel())
    if colB is not None and mix is not None:
        cb = me.color_attributes.new('colB', 'FLOAT_COLOR', 'POINT'); rgba = np.ones((len(P), 4), np.float32); rgba[:, :3] = colB.reshape(-1, 3); cb.data.foreach_set('color', rgba.ravel())
        am = me.attributes.new('mix', 'FLOAT', 'POINT'); am.data.foreach_set('value', mix)
    if uv is not None:
        ul = me.uv_layers.new(name='UVMap'); u = uv.reshape(-1, 2)[idx]; ul.data.foreach_set('uv', u.ravel())
    if smooth:
        try: me.shade_smooth()
        except Exception: me.polygons.foreach_set('use_smooth', np.ones(nt, bool))
    ob = bpy.data.objects.new(name, me); S.collection.objects.link(ob); return ob

def uv_xform(uv, t):
    # как three.js Texture.updateMatrix: setUvTransform(offset, repeat, rotation, center)
    if not t: return uv
    u = uv.reshape(-1, 2).copy(); rx, ry = t.get('repeat', [1, 1]); ox, oy = t.get('offset', [0, 0]); r = t.get('rotation', 0); cx, cy = t.get('center', [0, 0])
    c, s = math.cos(r), math.sin(r)
    x = u[:, 0] - cx; y = u[:, 1] - cy; x, y = rx * x, ry * y; x, y = c * x + s * y, -s * x + c * y; u[:, 0] = x + cx + ox; u[:, 1] = y + cy + oy
    if not t.get('flipY', True): u[:, 1] = 1 - u[:, 1]
    return u

CAMP = None; PXK = 0.0
def make_curves(name, P, K, rad, col, rscale=1.0):
    n = len(P) // K
    if n == 0: return None
    if CAMP is not None:   # как в движке: волосок не тоньше доли пикселя на своём расстоянии — иначе мех просвечивает
        d = np.linalg.norm(P - CAMP[None, :], axis=1); rad = np.maximum(np.minimum(rad * rscale, 0.006), d * PXK * float(opt('minpx', '0.3'))); rscale = 1.0   # предохранитель: волосок толще 6 мм — ошибка снятия
    hc = bpy.data.hair_curves.new(name); hc.add_curves([K] * n)
    hc.attributes['position'].data.foreach_set('vector', P.ravel())
    ra = hc.attributes.get('radius') or hc.attributes.new('radius', 'FLOAT', 'POINT'); ra.data.foreach_set('value', (rad * rscale).astype(np.float32))
    ca = hc.attributes.new('col', 'FLOAT_COLOR', 'CURVE'); rgba = np.ones((n, 4), np.float32); rgba[:, :3] = np.clip(col.reshape(-1, 3)[:n], 0, 1); ca.data.foreach_set('color', rgba.ravel())
    ob = bpy.data.objects.new(name, hc); S.collection.objects.link(ob); return ob

# ---------- свет ----------
def setup_lights(m):
    w = bpy.data.worlds.new('w'); S.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (1.0, 0.93, 0.85, 1); bg.inputs['Strength'].default_value = float(opt('world', '0.12'))
    L = []
    def area(name, loc, look, size, power, col, shape='DISK'):
        d = bpy.data.lights.new(name, 'AREA'); d.shape = shape; d.size = size; d.energy = power; d.color = col
        o = bpy.data.objects.new(name, d); o.location = loc; S.collection.objects.link(o)
        dirv = (Vector(look) - Vector(loc)).normalized(); o.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler(); return o
    def spot(name, loc, look, power, col, ang):
        d = bpy.data.lights.new(name, 'SPOT'); d.energy = power; d.color = col; d.spot_size = ang; d.spot_blend = 0.6; d.shadow_soft_size = 0.25
        o = bpy.data.objects.new(name, d); o.location = loc; S.collection.objects.link(o)
        o.rotation_euler = (Vector(look) - Vector(loc)).normalized().to_track_quat('-Z', 'Y').to_euler(); return o
    def sun(name, frm, to, strength, col, ang=0.03):
        d = bpy.data.lights.new(name, 'SUN'); d.energy = strength; d.color = col; d.angle = ang
        o = bpy.data.objects.new(name, d); S.collection.objects.link(o)
        o.rotation_euler = (Vector(to) - Vector(frm)).normalized().to_track_quat('-Z', 'Y').to_euler(); return o
    t3 = lambda p: (p[0], -p[2], p[1]); K = float(opt('lightk', '1.0'))
    # «как в кино» для комнаты: солнце в окно (пятно на полу, контур героев), небо из окна, мягкий ключевой свет слева-спереди, слабая заливка справа
    win = None
    for l in m.get('lights') or []:
        if l['t'] == 'SpotLight': win = Vector(t3(l['p']))
    win = win or Vector((0.9, 4.2, 2.15)); wc = Vector((win.x, 3.55, 1.85))
    sun('sun', (win.x + 1.6, 14.0, 9.5), (0.4, 0.2, 0.0), float(opt('sunk', '4.5')) * K, (1.0, 0.86, 0.68), 0.012)
    d = bpy.data.lights.new('sky', 'AREA'); d.shape = 'RECTANGLE'; d.size = 2.3; d.size_y = 1.75; d.energy = 260 * K; d.color = (0.78, 0.88, 1.0)
    o = bpy.data.objects.new('sky', d); o.location = wc; o.rotation_euler = (math.radians(90), 0, 0); S.collection.objects.link(o); o.visible_camera = False; o.visible_glossy = False
    tg = Vector((0.6, 0.4, 0.75)); cam = Vector(t3(m['cam']['pos']))
    area('key', (cam.x - 4.5, cam.y + 1.5, 3.1), tuple(tg), float(opt('keys', '1.6')), float(opt('keyw', '520')) * K, (1.0, 0.94, 0.86))
    area('fill', (cam.x + 4.0, cam.y + 0.5, 1.5), tuple(tg), 3.0, float(opt('fillw', '120')) * K, (0.92, 0.95, 1.0))
    area('top', (tg.x, tg.y + 0.5, 3.35), tuple(tg), 2.5, 90 * K, (1.0, 0.9, 0.78), 'SQUARE')

# ---------- кадр ----------
DYN = []
def clear_dyn():
    for o in DYN:
        d = o.data; bpy.data.objects.remove(o, do_unlink=True)
        try:
            if isinstance(d, bpy.types.Mesh): bpy.data.meshes.remove(d)
            else: bpy.data.hair_curves.remove(d)
        except Exception: pass
    DYN.clear()

def build(f, first):
    tag = 'f_%03d' % f; man = json.load(open(os.path.join(IN, tag + '.json'))); B = open(os.path.join(IN, tag + '.bin'), 'rb').read()
    texdir = os.path.join(IN, 'tex'); eng = os.path.join(IN, tag + '_eng.png')
    eye = mat_eye('eye', eng)
    global CAMP, PXK
    c = man['cam']; CAMP = conv(np.array(c['pos'], np.float32))[0]; PXK = 2 * math.tan(math.radians(c['fov']) / 2) / H
    if first: setup_lights(man)
    st = {'curves': 0, 'mesh': 0, 'static': 0}
    for ob in man['objs']:
        k = ob['k']
        if k == 'curves':
            P = conv(arr(B, ob['pos'])); n, K = ob['n'], ob['K']
            if ob.get('rad'): rad = arr(B, ob['rad']).copy()
            else: rad = np.tile(np.linspace(1.0, 0.25, K, dtype=np.float32), n) * float(opt('clayr', '0.00045'))
            if ob['kind'] == 'bars': rs = float(opt('barsr', '1.0'))
            elif ob['kind'] == 'neon': rs = float(opt('neonr', '1.0'))
            else: rs = 1.0
            col = arr(B, ob['col']).copy()
            if ob['kind'] == 'bars': col = np.clip(col * float(opt('barsk', '2.3')), 0, 0.92)
            o = make_curves(ob['name'][-24:], P, K, rad, col, rs)
            if o: o.data.materials.append(mat_hair('hair')); DYN.append(o); st['curves'] += n
            continue
        kind = ob.get('kind')
        static = kind == 'std'
        if static and not first: continue
        P = conv(arr(B, ob['pos'])); idx = arr(B, ob['idx']).astype(np.int64)
        if len(idx) < 3: continue
        col = arr(B, ob.get('col')); uv = arr(B, ob.get('uv')); colB = arr(B, ob.get('colB')); mix = arr(B, ob.get('mix'))
        md = dict(ob.get('mat') or {})
        if uv is not None and md.get('map'): uv = uv_xform(uv, md['map'])
        if kind == 'eye':
            o = make_mesh(ob['name'][-24:], P, idx, None, None); o.data.materials.append(eye)
        elif kind == 'skin':
            if col is not None and 'bars' in (ob.get('tag') or ''): col = np.clip(col * float(opt('barsk', '2.3')), 0, 0.92)
            o = make_mesh(ob['name'][-24:], P, idx, col, None); o.data.materials.append(mat_attr_principled('skin', 0.55, 0.15, 0.3))
        else:
            if col is not None and (md.get('vc') or md.get('ic') or colB is not None): md['_vc'] = 1
            if colB is not None and mix is not None: md['_mixB'] = 1
            o = make_mesh(ob['name'][-24:], P, idx, col, uv, colB, mix, smooth=True); o.data.materials.append(mat_std(md, texdir))
        if static: st['static'] += 1
        else: DYN.append(o); st['mesh'] += 1
    # камера
    cam = bpy.data.objects.get('cam')
    if not cam:
        cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); S.collection.objects.link(cam); S.camera = cam
    c = man['cam']; mw = c['mw']; M = Matrix([[mw[0], mw[4], mw[8], mw[12]], [mw[1], mw[5], mw[9], mw[13]], [mw[2], mw[6], mw[10], mw[14]], [0, 0, 0, 1]])
    cam.matrix_world = C4 @ M; cam.data.sensor_fit = 'VERTICAL'; cam.data.lens_unit = 'FOV'; cam.data.angle = math.radians(c['fov']); cam.data.clip_start = 0.05; cam.data.clip_end = 200
    log(tag, 't=%.3f' % man.get('t', 0), json.dumps(st))

first = True
for f in FRAMES:
    clear_dyn(); build(f, first); first = False
    S.render.filepath = os.path.join(OUT, 'r_%03d.png' % f)
    t1 = time.time(); bpy.ops.render.render(write_still=True); log('кадр', f, 'рендер за %.0f с' % (time.time() - t1))
    if TEST: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'test.blend'))
log('готово')
