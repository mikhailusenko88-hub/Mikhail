# Blender 4.2: собрать Барсика из out/geo.npz и отрендерить кадр «как в кино» (Cycles).
# blender -b -P render.py -- [shot=close|full] [samples=96] [w=1280] [h=720]
import bpy, sys, math, time, os
import numpy as np
from mathutils import Vector, Matrix

T0 = time.time()
def log(*a): print('[%5.1fs]' % (time.time() - T0), *a, flush=True)
args = dict(a.split('=') for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
SHOT = args.get('shot', 'close'); SPP = int(args.get('samples', 96)); W = int(args.get('w', 1280)); Hh = int(args.get('h', 720))
OUT = args.get('out', 'out/barsik_%s.png' % SHOT)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
G = np.load(os.path.join(os.path.dirname(bpy.data.filepath) or '.', 'out/geo.npz'))
log('npz', list(G.keys()))

# ---------- материалы ----------
def mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); return m, nt, out
def principled(nt, **kw):
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    for k, v in kw.items(): b.inputs[k].default_value = v
    return b
def attr(nt, name, typ='GEOMETRY'):
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = name; a.attribute_type = typ; return a
def math_node(nt, op, a=None, b=None, va=0.0, vb=0.0):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    if a is not None: nt.links.new(a, n.inputs[0])
    else: n.inputs[0].default_value = va
    if b is not None: nt.links.new(b, n.inputs[1])
    else: n.inputs[1].default_value = vb
    return n.outputs[0]

def mel_to_rgb(mel, cream):
    xs = np.array([0.0, 0.1, 0.36, 0.66, 1.0])
    cs = np.array([[0.92, 0.86, 0.78], [0.80, 0.58, 0.38], [0.62, 0.25, 0.065], [0.32, 0.1, 0.03], [0.1, 0.04, 0.02]])
    return np.stack([np.interp(mel, xs, cs[:, i]) for i in range(3)], -1)

# кожа под шерстью (+ мордочка, внутри уха, подводка века)
def skin_material():
    m, nt, out = mat('skin')
    a = attr(nt, 'skin_col')
    b = principled(nt, **{'Roughness': 0.62, 'Subsurface Weight': 0.25, 'Subsurface Scale': 0.02, 'Sheen Weight': 0.6, 'Sheen Roughness': 0.35})
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
    nt.links.new(a.outputs['Color'], b.inputs['Base Color'])
    s = attr(nt, 'sss'); nt.links.new(s.outputs['Fac'], b.inputs['Subsurface Weight'])
    nt.links.new(b.outputs[0], out.inputs[0]); return m

def fur_material():
    m, nt, out = mat('fur')
    h = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    try: h.model = 'CHIANG'
    except Exception: pass
    h.parametrization = 'MELANIN'
    info = nt.nodes.new('ShaderNodeHairInfo')
    mel = attr(nt, 'mel'); red = attr(nt, 'red')
    # кончики чуть светлее: меланин * (1 - 0.22 * t)
    k = math_node(nt, 'MULTIPLY', info.outputs['Intercept'], None, vb=-0.22)
    k = math_node(nt, 'ADD', k, None, vb=1.0)
    ml = math_node(nt, 'MULTIPLY', mel.outputs['Fac'], k)
    nt.links.new(ml, h.inputs['Melanin']); nt.links.new(red.outputs['Fac'], h.inputs['Melanin Redness'])
    for k_, v in [('Roughness', 0.32), ('Radial Roughness', 0.32), ('Coat', 0.12), ('Random Color', 0.06), ('Random Roughness', 0.12), ('IOR', 1.55)]:
        if k_ in h.inputs: h.inputs[k_].default_value = v
    nt.links.new(h.outputs[0], out.inputs[0]); return m

# ---------- кожа ----------
def build_skin():
    v, f, n = G['skin_v'], G['skin_f'], G['skin_n']; reg = G['skin_reg']
    me = bpy.data.meshes.new('BarsikSkin'); me.from_pydata(v.tolist(), [], f.tolist()); me.update()
    me.polygons.foreach_set('use_smooth', np.ones(len(f), bool))
    try: me.normals_split_custom_set_from_vertices(n.tolist())
    except Exception as e: log('normals', e)
    rgb = mel_to_rgb(G['skin_mel'], G['skin_cream']) * 0.82
    # мордочка без шерсти: кремовая бархатная; внутри уха — розовое; подводка века — тёмная
    muzzle = reg == 2
    rgb[muzzle] = mel_to_rgb(np.full(muzzle.sum(), 0.1), None) * 0.98
    ear_in = reg == 8; rgb[ear_in] = (0.62, 0.3, 0.32)
    E = G['eyes']; RE = float(G['re'][0]); LN = G['lid_n']; LO = float(G['lid_off'][0])
    liner = np.zeros(len(v), bool)
    for c in E:
        q = v - c; d = np.linalg.norm(q, axis=-1); cut = q @ LN - LO
        liner |= (d < RE + 0.011) & (q[:, 1] < 0.01)   # тёмная кожа вокруг глаза — как подводка у настоящих кошек
    rgb[liner] = (0.09, 0.04, 0.02)
    sss = np.where(ear_in, 0.9, np.where(reg == 4, 0.5, 0.18)).astype(np.float32)
    rgba = np.concatenate([rgb, np.ones((len(v), 1))], -1).astype(np.float32)
    ca = me.color_attributes.new('skin_col', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', rgba.ravel())
    sa = me.attributes.new('sss', 'FLOAT', 'POINT'); sa.data.foreach_set('value', sss)
    ob = bpy.data.objects.new('BarsikSkin', me); sc.collection.objects.link(ob); me.materials.append(skin_material())
    log('skin', len(v)); return ob

# ---------- шерсть ----------
def build_fur():
    P = G['fur_pts']; n, k, _ = P.shape
    cu = bpy.data.hair_curves.new('BarsikFur'); cu.add_curves([k] * n)
    cu.position_data.foreach_set('vector', P.astype(np.float32).ravel())
    if 'radius' not in cu.attributes: cu.attributes.new('radius', 'FLOAT', 'POINT')
    t = np.tile(np.linspace(0, 1, k, dtype=np.float32), n)
    rad = np.repeat(G['fur_rad'], k) * (1.0 - 0.85 * t ** 1.3)
    cu.attributes['radius'].data.foreach_set('value', rad.astype(np.float32))
    for nm, arr in [('mel', G['fur_mel']), ('red', G['fur_red'])]:
        a = cu.attributes.new(nm, 'FLOAT', 'CURVE'); a.data.foreach_set('value', arr.astype(np.float32))
    cu.materials.append(fur_material())
    ob = bpy.data.objects.new('BarsikFur', cu); sc.collection.objects.link(ob); log('fur', n); return ob

# ---------- глаза ----------
def eye_material(side):
    m, nt, out = mat('eye%d' % side)
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    # c = -y (локально глаз смотрит в -Y; радиус 1)
    c = math_node(nt, 'MULTIPLY', sep.outputs['Y'], None, vb=-1.0)
    iris = nt.nodes.new('ShaderNodeMapRange'); nt.links.new(c, iris.inputs['Value']); iris.inputs['From Min'].default_value = 0.70; iris.inputs['From Max'].default_value = 0.715
    pup = nt.nodes.new('ShaderNodeMapRange'); nt.links.new(c, pup.inputs['Value']); pup.inputs['From Min'].default_value = 0.915; pup.inputs['From Max'].default_value = 0.922
    ring = nt.nodes.new('ShaderNodeMapRange'); nt.links.new(c, ring.inputs['Value']); ring.inputs['From Min'].default_value = 0.70; ring.inputs['From Max'].default_value = 0.79
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 9.0; nz.inputs['Detail'].default_value = 6.0
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 0.05, 1.0); nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs[0], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac'])
    ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[0].color = (0.06, 0.2, 0.05, 1)
    ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (0.35, 0.62, 0.12, 1)
    el = ramp.color_ramp.elements.new(0.55); el.color = (0.16, 0.42, 0.08, 1)
    # тёмный ободок радужки
    dark = nt.nodes.new('ShaderNodeMixRGB'); dark.blend_type = 'MULTIPLY'
    inv = math_node(nt, 'SUBTRACT', None, ring.outputs[0], va=1.0)
    nt.links.new(inv, dark.inputs['Fac']); nt.links.new(ramp.outputs[0], dark.inputs['Color1']); dark.inputs['Color2'].default_value = (0.2, 0.25, 0.16, 1)
    # белок -> радужка -> зрачок
    m1 = nt.nodes.new('ShaderNodeMixRGB'); nt.links.new(iris.outputs[0], m1.inputs['Fac']); m1.inputs['Color1'].default_value = (0.9, 0.88, 0.86, 1); nt.links.new(dark.outputs['Color'], m1.inputs['Color2'])
    m2 = nt.nodes.new('ShaderNodeMixRGB'); nt.links.new(pup.outputs[0], m2.inputs['Fac']); nt.links.new(m1.outputs['Color'], m2.inputs['Color1']); m2.inputs['Color2'].default_value = (0.004, 0.003, 0.003, 1)
    b = principled(nt, **{'Roughness': 0.35, 'Subsurface Weight': 0.15, 'Subsurface Scale': 0.01})
    nt.links.new(m2.outputs['Color'], b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0]); return m

def cornea_material():
    m, nt, out = mat('cornea')
    b = principled(nt, **{'Roughness': 0.0, 'Transmission Weight': 1.0, 'IOR': 1.336, 'Base Color': (1, 1, 1, 1), 'Specular IOR Level': 0.8})
    nt.links.new(b.outputs[0], out.inputs[0]); return m

def build_eyes():
    RE = float(G['re'][0]); cm = cornea_material()
    for i, c in enumerate(G['eyes']):
        s = 1 if c[0] > 0 else -1
        tgt = Vector((0.36, -1.6, 0.84)) if SHOT == 'close' else Vector((0.5, -2.8, 0.75))
        fwd = (tgt - Vector(c)).normalized()
        rot = Vector((0, -1, 0)).rotation_difference(fwd)
        me = bpy.data.meshes.new('eye'); ob = bpy.data.objects.new('Eye%d' % i, me); sc.collection.objects.link(ob)
        import bmesh; bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=48, radius=1.0); bm.to_mesh(me); bm.free()
        for p in me.polygons: p.use_smooth = True
        ob.scale = (RE, RE, RE); ob.location = Vector(c); ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = rot
        me.materials.append(eye_material(i))
        # роговица — выпуклая линза над радужкой
        me2 = bpy.data.meshes.new('cornea'); co = bpy.data.objects.new('Cornea%d' % i, me2); sc.collection.objects.link(co)
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0); bm.to_mesh(me2); bm.free()
        for p in me2.polygons: p.use_smooth = True
        co.parent = ob; co.scale = (0.872, 0.872, 0.872); co.location = (0, -0.208, 0)
        me2.materials.append(cm); co.visible_shadow = False
    log('eyes')

def build_mesh(name, v, f, m):
    me = bpy.data.meshes.new(name); me.from_pydata(v.tolist(), [], f.tolist()); me.update()
    me.polygons.foreach_set('use_smooth', np.ones(len(f), bool))
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(m); return ob

def nose_material():
    m, nt, out = mat('nose'); b = principled(nt, **{'Base Color': (0.78, 0.36, 0.42, 1), 'Roughness': 0.38, 'Subsurface Weight': 0.3, 'Subsurface Scale': 0.01, 'Coat Weight': 0.25, 'Coat Roughness': 0.25})
    nt.links.new(b.outputs[0], out.inputs[0]); return m
def scarf_material():
    m, nt, out = mat('scarf')
    tc = nt.nodes.new('ShaderNodeTexCoord'); wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 140; wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.45; bump.inputs['Distance'].default_value = 0.002; nt.links.new(wv.outputs['Fac'], bump.inputs['Height'])
    b = principled(nt, **{'Base Color': (0.015, 0.09, 0.45, 1), 'Roughness': 0.85, 'Sheen Weight': 0.7, 'Sheen Roughness': 0.4})
    nt.links.new(bump.outputs[0], b.inputs['Normal']); nt.links.new(b.outputs[0], out.inputs[0]); return m
def flat_material(name, rgb, rough=0.5, trans=0.0):
    m, nt, out = mat(name); b = principled(nt, **{'Base Color': (*rgb, 1), 'Roughness': rough, 'Transmission Weight': trans})
    nt.links.new(b.outputs[0], out.inputs[0]); return m

def build_curve(name, pts, r0, r1, m):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 1.0; cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    co = np.concatenate([pts, np.ones((len(pts), 1))], -1).astype(np.float32); sp.points.foreach_set('co', co.ravel())
    sp.points.foreach_set('radius', np.linspace(r0, r1, len(pts)).astype(np.float32))
    ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob); cu.materials.append(m); return ob

# ---------- окружение: туманный лес ----------
def bark_material():
    m, nt, out = mat('bark')
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 8
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (6, 6, 0.6); tc = nt.nodes.new('ShaderNodeTexCoord'); nt.links.new(tc.outputs['Object'], mp.inputs[0]); nt.links.new(mp.outputs[0], nz.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac']); ramp.color_ramp.elements[0].color = (0.05, 0.035, 0.025, 1); ramp.color_ramp.elements[1].color = (0.22, 0.17, 0.11, 1)
    moss = nt.nodes.new('ShaderNodeMixRGB'); nt.links.new(ramp.outputs[0], moss.inputs['Color1']); moss.inputs['Color2'].default_value = (0.12, 0.25, 0.06, 1)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    mf = math_node(nt, 'LESS_THAN', sep.outputs['Z'], None, vb=0.9); nt.links.new(mf, moss.inputs['Fac'])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.8; nt.links.new(nz.outputs['Fac'], bump.inputs['Height'])
    b = principled(nt, **{'Roughness': 0.9}); nt.links.new(moss.outputs['Color'], b.inputs['Base Color']); nt.links.new(bump.outputs[0], b.inputs['Normal'])
    nt.links.new(b.outputs[0], out.inputs[0]); return m

def ground_material():
    m, nt, out = mat('ground')
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 1.5; nz.inputs['Detail'].default_value = 8
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac']); ramp.color_ramp.elements[0].color = (0.04, 0.09, 0.02, 1); ramp.color_ramp.elements[1].color = (0.16, 0.26, 0.05, 1)
    b = principled(nt, **{'Roughness': 0.95}); nt.links.new(ramp.outputs[0], b.inputs['Base Color']); nt.links.new(b.outputs[0], out.inputs[0]); return m

def grass_material():
    m, nt, out = mat('grass'); info = nt.nodes.new('ShaderNodeHairInfo')
    ramp = nt.nodes.new('ShaderNodeValToRGB'); nt.links.new(info.outputs['Intercept'], ramp.inputs['Fac']); ramp.color_ramp.elements[0].color = (0.02, 0.06, 0.01, 1); ramp.color_ramp.elements[1].color = (0.25, 0.45, 0.06, 1)
    b = principled(nt, **{'Roughness': 0.6, 'Subsurface Weight': 0.0}); nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); nt.links.new(ramp.outputs[0], tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs[0].default_value = 0.3; nt.links.new(b.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0]); return m

def build_world():
    rng = np.random.default_rng(11)
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); gp = bpy.context.active_object; gp.data.materials.append(ground_material())
    bm_ = bark_material()
    for i in range(16):
        x = rng.uniform(-5.5, 5.5); y = rng.uniform(1.6, 10.0); r = rng.uniform(0.16, 0.42)
        if abs(x) < 0.9 and y < 3: x += 1.6 * np.sign(x or 1)
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=14, location=(x, y, 7)); tr = bpy.context.active_object; tr.data.materials.append(bm_)
        bpy.ops.object.shade_smooth()
    for i in range(5):  # мшистые камни
        x = rng.uniform(-2.5, 2.5); y = rng.uniform(1.2, 4.5)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=rng.uniform(0.2, 0.45), location=(x, y, 0.05)); st = bpy.context.active_object; st.scale = (1.3, 1.0, 0.6)
        st.data.materials.append(flat_material('moss%d' % i, (0.1, 0.22, 0.05), 0.95)); bpy.ops.object.shade_smooth()
    # трава вокруг
    n = 90000; R = np.sqrt(rng.random(n)) * 3.2; A = rng.random(n) * 6.283
    root = np.stack([np.cos(A) * R, np.sin(A) * R * 1.6 + 0.6, np.zeros(n)], -1)
    ok = ~((np.abs(root[:, 0]) < 0.25) & (np.abs(root[:, 1] - 0.0) < 0.25)); root = root[ok]; n = len(root)
    hgt = rng.uniform(0.04, 0.11, n); lean = rng.normal(0, 0.35, (n, 2))
    k = 4; t = np.linspace(0, 1, k)
    pts = root[:, None, :] + np.stack([lean[:, 0][:, None] * t * t * hgt[:, None], lean[:, 1][:, None] * t * t * hgt[:, None], hgt[:, None] * t], -1)
    cu = bpy.data.hair_curves.new('Grass'); cu.add_curves([k] * n); cu.position_data.foreach_set('vector', pts.astype(np.float32).ravel())
    if 'radius' not in cu.attributes: cu.attributes.new('radius', 'FLOAT', 'POINT')
    cu.attributes['radius'].data.foreach_set('value', np.tile(np.array([0.0028, 0.0022, 0.0014, 0.0002], np.float32), n))
    cu.materials.append(grass_material()); ob = bpy.data.objects.new('Grass', cu); sc.collection.objects.link(ob)
    # небо/фон: бирюзовая дымка
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes['Background']
    bg.inputs[0].default_value = (0.42, 0.62, 0.6, 1); bg.inputs[1].default_value = 0.9
    w.mist_settings.start = 1.6; w.mist_settings.depth = 9.0; w.mist_settings.falloff = 'QUADRATIC'
    log('world')

def look_at(ob, target):
    d = Vector(target) - ob.location; ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')

def build_lights_camera():
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 4.2; sun.data.angle = math.radians(3.5); sun.data.color = (1.0, 0.86, 0.68)
    sun.rotation_mode = 'QUATERNION'; sun.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(Vector((0.5, -0.62, -0.6)).normalized())
    key = bpy.data.objects.new('Key', bpy.data.lights.new('Key', 'AREA')); sc.collection.objects.link(key)
    key.data.energy = 140; key.data.size = 1.4; key.data.color = (1.0, 0.95, 0.88); key.location = (-1.3, -1.5, 1.55); look_at(key, (0, -0.05, 0.7))
    fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'AREA')); sc.collection.objects.link(fill)
    fill.data.energy = 45; fill.data.size = 2.0; fill.data.color = (0.75, 0.9, 1.0); fill.location = (1.6, -1.0, 0.6); look_at(fill, (0, 0, 0.6))
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
    E = G['eyes']
    if SHOT == 'close':
        cam.location = (0.62, -1.95, 0.9); target = (0.0, -0.04, 0.74); cam.data.lens = 55
        eyeL = bpy.data.objects.new('EyeLight', bpy.data.lights.new('EyeLight', 'AREA')); sc.collection.objects.link(eyeL)
        eyeL.data.energy = 6; eyeL.data.size = 0.25; eyeL.location = (0.2, -1.4, 1.05); look_at(eyeL, (0, -0.14, 0.77)); eyeL.data.color = (1, 0.97, 0.93)
    else:
        cam.location = (0.9, -2.9, 0.75); target = (0.0, 0.0, 0.5); cam.data.lens = 50
    look_at(cam, target)
    cam.data.dof.use_dof = True; near = E[np.argmax(E[:, 0])] if SHOT == 'close' else np.array([0, -0.1, 0.6])
    cam.data.dof.focus_distance = float(np.linalg.norm(np.array(cam.location) - near)); cam.data.dof.aperture_fstop = 2.2 if SHOT == 'close' else 3.2
    cam.data.sensor_width = 36

def compositor():
    sc.use_nodes = True; tr = sc.node_tree; tr.nodes.clear()
    rl = tr.nodes.new('CompositorNodeRLayers'); comp = tr.nodes.new('CompositorNodeComposite')
    mix = tr.nodes.new('CompositorNodeMixRGB'); mix.blend_type = 'MIX'
    mr = tr.nodes.new('CompositorNodeMapRange'); mr.inputs['To Max'].default_value = 0.72
    tr.links.new(rl.outputs['Mist'], mr.inputs['Value']); tr.links.new(mr.outputs[0], mix.inputs['Fac'])
    tr.links.new(rl.outputs['Image'], mix.inputs[1]); mix.inputs[2].default_value = (0.56, 0.74, 0.7, 1)
    glare = tr.nodes.new('CompositorNodeGlare'); glare.glare_type = 'FOG_GLOW'; glare.quality = 'HIGH'; glare.mix = -0.85; glare.threshold = 0.85
    tr.links.new(mix.outputs[0], glare.inputs['Image']); tr.links.new(glare.outputs['Image'], comp.inputs['Image'])

# ---------- сборка ----------
build_skin(); build_fur(); build_eyes()
build_mesh('Nose', G['nose_v'], G['nose_f'], nose_material())
build_mesh('Scarf', G['scarf_v'], G['scarf_f'], scarf_material())
mm = flat_material('mouth', (0.12, 0.04, 0.03), 0.5)
for i, l in enumerate(G['mouth']): build_curve('Mouth%d' % i, l, 0.0017, 0.0015, mm)
wm = flat_material('whisker', (0.92, 0.9, 0.86), 0.35)
for i, l in enumerate(G['whisk']): build_curve('Whisk%d' % i, l, 0.0011, 0.00025, wm)
sc.view_layers[0].use_pass_mist = True
build_world(); build_lights_camera(); compositor()

r = sc.render; r.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 3; sc.cycles.transmission_bounces = 6; sc.cycles.transparent_max_bounces = 8
sc.cycles_curves.shape = 'THICK'; sc.cycles_curves.subdivisions = 2
r.resolution_x = W; r.resolution_y = Hh; r.resolution_percentage = 100; r.use_compositing = True
sc.view_layers[0].use_pass_mist = True
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e: log('look', e)
r.threads_mode = 'AUTO'; r.filepath = os.path.abspath(OUT); r.image_settings.file_format = 'PNG'
log('render start', SHOT, SPP, W, Hh)
bpy.ops.render.render(write_still=True)
log('render done', OUT)
