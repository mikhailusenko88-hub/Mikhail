# Подарочные боксы со сладостями: Blender Cycles, запуск:
#   blender -b --factory-startup -P boxes.py -- name=<имя> box=podarok_blue res=800x800 samples=48
import bpy, bmesh, math, random, sys, os, json
from mathutils import Vector, Matrix

A = {}
for a in sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []:
    if '=' in a:
        k, v = a.split('=', 1); A[k] = v
NAME = A.get('name', 'test')
BOX = A.get('box', 'podarok_blue')
RES = [int(x) for x in A.get('res', '800x800').split('x')]
SAMPLES = int(A.get('samples', '48'))
NOISE = float(A.get('noise', '0.05'))
EV = float(A.get('ev', '0'))
SEED = int(A.get('seed', '7'))
OUT = f'out/{NAME}'
os.makedirs(OUT, exist_ok=True)
random.seed(SEED)
SIDE = json.load(open('tex/sidecolors.json'))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.adaptive_threshold = NOISE
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = A.get('look', 'AgX - Medium High Contrast')
except Exception: pass
sc.view_settings.exposure = EV
sc.render.film_transparent = False

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1]

# ---------------- materials
def principled(name, color=None, rough=0.5, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    if color is not None: b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = rough
    for k, v in kw.items():
        if k in b.inputs: b.inputs[k].default_value = v
    return m, b

def paper_bump(m, b, scale=900, strength=0.06):
    nt = m.node_tree
    n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = 6
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength; bp.inputs['Distance'].default_value = 0.0004
    nt.links.new(n.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

def cardboard(name, hexcol, rough=0.55):
    m, b = principled(name, srgb(hexcol), rough, **{'Specular IOR Level': 0.35})
    paper_bump(m, b, 1400, 0.05)
    return m

def satin(name, hexcol):
    m, b = principled(name, srgb(hexcol), 0.22, **{'Anisotropic': 0.7, 'Sheen Weight': 0.4, 'Specular IOR Level': 0.6})
    return m

def film():
    m, b = principled('film', [1, 1, 1, 1], 0.03, **{'Transmission Weight': 1.0, 'IOR': 1.35})
    return m

def shred_mat(hexes):
    m, b = principled('shred', None, 0.55, **{'Sheen Weight': 0.3, 'Subsurface Weight': 0.08})
    nt = m.node_tree
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    cr = nt.nodes.new('ShaderNodeValToRGB'); cr.color_ramp.interpolation = 'CONSTANT'
    el = cr.color_ramp.elements
    while len(el) < len(hexes): el.new(0.5)
    for i, h in enumerate(hexes):
        el[i].position = i / len(hexes); el[i].color = srgb(h)
    nt.links.new(oi.outputs['Random'], cr.inputs['Fac'])
    nt.links.new(cr.outputs['Color'], b.inputs['Base Color'])
    paper_bump(m, b, 2500, 0.15)
    return m

def image_mat(key, rough=0.35, coat=0.25, proj=None):
    m, b = principled('img_' + key + (proj or ''), None, rough, **{'Coat Weight': coat, 'Specular IOR Level': 0.5})
    nt = m.node_tree
    im = nt.nodes.new('ShaderNodeTexImage'); im.image = bpy.data.images.load(os.path.abspath(f'tex/{key}.png'))
    im.interpolation = 'Cubic'; im.extension = 'CLIP'
    if proj == 'front':   # planar projection along -Y from generated coords (for egg / drum)
        tc = nt.nodes.new('ShaderNodeTexCoord'); sp = nt.nodes.new('ShaderNodeSeparateXYZ'); cb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(tc.outputs['Generated'], sp.inputs[0]); nt.links.new(sp.outputs['X'], cb.inputs['X']); nt.links.new(sp.outputs['Z'], cb.inputs['Y'])
        nt.links.new(cb.outputs[0], im.inputs['Vector'])
    side = SIDE.get(key, [0.6, 0.6, 0.6])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[7].default_value = [side[0] ** 2.2, side[1] ** 2.2, side[2] ** 2.2, 1]
    nt.links.new(im.outputs['Color'], mix.inputs[6])
    # where the image is transparent: on egg/drum use side color, on flat packs cut out
    if proj == 'front':
        inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1
        nt.links.new(im.outputs['Alpha'], inv.inputs[1]); nt.links.new(inv.outputs[0], mix.inputs[0])
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    else:
        nt.links.new(im.outputs['Color'], b.inputs['Base Color'])
        nt.links.new(im.outputs['Alpha'], b.inputs['Alpha'])
    return m, im.image.size[:]

COL = bpy.context.collection
def link(ob): COL.objects.link(ob); return ob

def mesh_obj(name, bm, mat=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); link(ob)
    if mat: me.materials.append(mat)
    for p in me.polygons: p.use_smooth = False
    return ob

def cuboid(name, sx, sy, sz, loc=(0, 0, 0), mat=None, bevel=0.0006):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    ob = mesh_obj(name, bm, mat); ob.location = loc
    if bevel:
        md = ob.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = 2
    return ob

# ---------------- backdrop and light
def backdrop(hexcol):
    bm = bmesh.new()
    prof = []
    R = 0.35
    for i in range(0, 13):
        a = math.pi / 2 * i / 12
        prof.append((0.6 + R * math.sin(a), R - R * math.cos(a)))
    pts = [(-2.0, 0.0)] + prof + [(0.6 + R, 2.2)]
    rows = []
    for x in (-2.5, 2.5):
        rows.append([bm.verts.new((x, y, z)) for y, z in pts])
    for i in range(len(pts) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    m, b = principled('backdrop', srgb(hexcol), 0.85)
    paper_bump(m, b, 300, 0.02)
    ob = mesh_obj('backdrop', bm, m)
    for p in ob.data.polygons: p.use_smooth = True
    return ob

def area(name, loc, target, size, power, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.size = size; ld.energy = power; ld.color = color
    ld.shape = 'RECTANGLE'; ld.size_y = size * 0.75
    ob = bpy.data.objects.new(name, ld); link(ob); ob.location = loc
    d = Vector(target) - Vector(loc); ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

def world():
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    hd = None
    for hid in (A.get('hdri', 'studio_small_09'), 'brown_photostudio_02'):
        for ext in ('hdr', 'exr'):
            p = f'assets/hdris/{hid}/{hid}.{ext}'
            if os.path.exists(p): hd = p; break
        if hd: break
    if hd:
        env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(os.path.abspath(hd))
        mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
        mp.inputs['Rotation'].default_value[2] = math.radians(float(A.get('hdri_rot', '140')))
        nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = float(A.get('hdrik', '0.25'))
        print('HDRI', hd)
    else:
        bg.inputs['Color'].default_value = (0.8, 0.78, 0.75, 1); bg.inputs['Strength'].default_value = 0.4
        print('no HDRI')

# ---------------- box parts
def open_box(w, h, t, mat, inner_mat):
    parts = [cuboid('bottom', w, w, t, (0, 0, t / 2), mat)]
    for sx, sy, lx, ly in ((w, t, 0, -w / 2 + t / 2), (w, t, 0, w / 2 - t / 2), (t, w - 2 * t, -w / 2 + t / 2, 0), (t, w - 2 * t, w / 2 - t / 2, 0)):
        parts.append(cuboid('wall', sx, sy, h, (lx, ly, h / 2), mat))
    # inner liner a bit lighter (printed white inside is common; we keep colour but slightly lighter)
    return parts

def ribbon_curve(name, pts2d, width, mat, closed=False):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '2D'; cu.fill_mode = 'NONE'; cu.extrude = width / 2; cu.resolution_u = 24
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts2d) - 1)
    for p, (x, y) in zip(sp.bezier_points, pts2d):
        p.co = (x, y, 0); p.handle_left_type = p.handle_right_type = 'AUTO'
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu); link(ob); cu.materials.append(mat)
    md = ob.modifiers.new('sol', 'SOLIDIFY'); md.thickness = 0.0005
    return ob

def bow(mat, s=1.0):
    """bow on a surface at z=0: two standing loops, a knot and two flat tails"""
    objs = []
    L, H = 0.045 * s, 0.026 * s
    for sg in (-1, 1):
        pts = [(0, 0.002 * s), (sg * L * 0.45, H), (sg * L, H * 0.75), (sg * L * 0.95, H * 0.15), (sg * L * 0.5, 0.0), (0, 0.002 * s)]
        ob = ribbon_curve('loop', pts, 0.024 * s, mat, closed=True)
        ob.rotation_euler = (math.radians(90), 0, math.radians(sg * 8))
        objs.append(ob)
    for sg in (-1, 1):
        tl = cuboid('tail', 0.075 * s, 0.022 * s, 0.0008, (sg * 0.03 * s, -0.026 * s, 0.0006), mat, bevel=0)
        tl.rotation_euler = (0, 0, math.radians(sg * 55))
        objs.append(tl)
    knot = cuboid('knot', 0.018 * s, 0.026 * s, 0.012 * s, (0, 0, 0.006 * s), mat, bevel=0.003 * s)
    objs.append(knot)
    return objs

def lid(w, h, t, mat, rib, win=0.5):
    """lid lying flat, top surface at z=h, window in the middle; returns list of objects (parented to empty)"""
    root = bpy.data.objects.new('lid', None); link(root)
    obs = []
    wi = w * win
    fr = (w - wi) / 2
    obs.append(cuboid('lt1', w, fr, t, (0, -w / 2 + fr / 2, h - t / 2), mat))
    obs.append(cuboid('lt2', w, fr, t, (0, w / 2 - fr / 2, h - t / 2), mat))
    obs.append(cuboid('lt3', fr, wi, t, (-w / 2 + fr / 2, 0, h - t / 2), mat))
    obs.append(cuboid('lt4', fr, wi, t, (w / 2 - fr / 2, 0, h - t / 2), mat))
    obs.append(cuboid('film', wi + 0.004, wi + 0.004, 0.0004, (0, 0, h - t * 0.6), film(), bevel=0))
    for sx, sy, lx, ly in ((w, t, 0, -w / 2 + t / 2), (w, t, 0, w / 2 - t / 2), (t, w - 2 * t, -w / 2 + t / 2, 0), (t, w - 2 * t, w / 2 - t / 2, 0)):
        obs.append(cuboid('skirt', sx, sy, h, (lx, ly, h / 2), mat))
    # ribbon crossing off-centre so the window stays visible
    rw = 0.024; off = w * 0.30; e = 0.0012
    obs.append(cuboid('rib1', w + 2 * e, rw, 0.0008, (0, off, h + 0.0004), rib, bevel=0))
    obs.append(cuboid('rib2', rw, w + 2 * e, 0.0008, (off, 0, h + 0.0004), rib, bevel=0))
    for sg in (-1, 1):
        obs.append(cuboid('rib1s', 0.0008, rw, h, (sg * (w / 2 + e), off, h / 2), rib, bevel=0))
        obs.append(cuboid('rib2s', rw, 0.0008, h, (off, sg * (w / 2 + e), h / 2), rib, bevel=0))
    bw = bow(rib, w / 0.2 * 0.9)
    for o in bw:
        o.location = (off + o.location.x, off + o.location.y, h + 0.0008 + o.location.z)
    obs += bw
    for o in obs: o.parent = root
    return root

# ---------------- shred
def shred_meshes(n=5):
    mes = []
    for k in range(n):
        bm = bmesh.new()
        L = random.uniform(0.035, 0.06); seg = int(L / 0.0035); wdt = random.uniform(0.0028, 0.0042)
        prev = None; tw = 0
        for i in range(seg + 1):
            x = -L / 2 + L * i / seg
            z = (0.0016 if i % 2 else -0.0016) * random.uniform(0.6, 1.2)
            y0 = math.sin(i * 0.35 + k) * 0.003
            tw += random.uniform(-0.35, 0.35)
            a = Vector((0, math.cos(tw) * wdt / 2, math.sin(tw) * wdt / 2))
            c = Vector((x, y0, z))
            v1 = bm.verts.new(c + a); v2 = bm.verts.new(c - a)
            if prev: bm.faces.new((prev[0], prev[1], v2, v1))
            prev = (v1, v2)
        me = bpy.data.meshes.new(f'shred{k}'); bm.to_mesh(me); bm.free(); mes.append(me)
    return mes

def fill_shred(w, top, mat, count, mound=0.012, bottom=0.003, margin=0.006):
    mes = shred_meshes(6)
    for me in mes: me.materials.append(mat)
    col = bpy.data.collections.new('shred'); sc.collection.children.link(col)
    half = w / 2 - margin
    for i in range(count):
        x, y = random.uniform(-half, half), random.uniform(-half, half)
        r = max(abs(x), abs(y)) / half
        zmax = top + mound * (1 - r * r)
        z = random.uniform(bottom, zmax) if random.random() < 0.35 else random.uniform(zmax - 0.01, zmax)
        ob = bpy.data.objects.new('s', random.choice(mes)); col.objects.link(ob)
        ob.location = (x, y, z)
        ob.rotation_euler = (random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6), random.uniform(0, math.tau))
        s = random.uniform(0.8, 1.25); ob.scale = (s, s, s)
    return col

# ---------------- products
SIZE = {'KK': (0.135, 'w', 'bar', 0.012), 'TW20': (0.14, 'w', 'bar', 0.008), 'CHUPA': (0.12, 'w', 'bag', 0.012), 'FINI': (0.11, 'h', 'bag', 0.012),
        'PMINI': (0.095, 'h', 'box', 0.014), 'PCHOC': (0.15, 'h', 'box', 0.018), 'PSTR': (0.15, 'h', 'box', 0.018), 'KJ': (0.075, 'h', 'egg', 0.045),
        'HAR': (0.17, 'h', 'bag', 0.024), 'TW42': (0.08, 'h', 'drum', 0.052), 'BB': (0.16, 'h', 'bag', 0.024)}

def product(key, scale=1.0):
    size, by, kind, depth = SIZE[key]
    m, (iw, ih) = image_mat(key, rough=0.32 if kind in ('bag', 'bar') else 0.45, coat=0.35 if kind in ('bag', 'bar', 'egg') else 0.1,
                            proj='front' if kind in ('egg', 'drum') else None)
    if by == 'h': H = size * scale; W = H * iw / ih
    else: W = size * scale; H = W * ih / iw
    D = depth * scale
    if kind in ('bag', 'bar', 'box'):
        bm = bmesh.new()
        nu, nv = (28, 36) if kind == 'bag' else (2, 2)
        grid = []
        for j in range(nv + 1):
            row = []
            for i in range(nu + 1):
                u, v = i / nu, j / nv
                x, y = (u - 0.5) * W, (v - 0.5) * H
                if kind == 'bag':
                    f = (1 - abs(2 * u - 1) ** 5) * (1 - abs(2 * v - 1) ** 7)
                    z = D * 0.5 * f
                else:
                    z = D * 0.5
                row.append(bm.verts.new((x, y, z)))
            grid.append(row)
        uv = bm.loops.layers.uv.new('UVMap')
        for j in range(nv):
            for i in range(nu):
                f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
                for lp, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    lp[uv].uv = (ii / nu, jj / nv)
        ob = mesh_obj(key, bm, m)
        for p in ob.data.polygons: p.use_smooth = kind == 'bag'
        sol = ob.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = D if kind != 'bag' else 0.003; sol.offset = -1 if kind != 'bag' else 0
        if kind != 'bag':
            sm, sb = principled('side_' + key, [c ** 2.2 for c in SIDE[key]] + [1], 0.4)
            ob.data.materials.append(sm); sol.material_offset_rim = 1
        return ob, W, H, D
    if kind == 'egg':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1)
        ob = bpy.context.active_object
        for v in ob.data.vertices:
            z = v.co.z; k = 1 - 0.12 * z
            v.co.x *= k; v.co.y *= k
        ob.scale = (W / 2, D / 2, H / 2); bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth(); ob.data.materials.append(m); ob.name = key
        return ob, W, H, D
    if kind == 'drum':
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=W / 2, depth=H)
        ob = bpy.context.active_object; bpy.ops.object.shade_smooth(); ob.data.materials.append(m); ob.name = key
        md = ob.modifiers.new('bv', 'BEVEL'); md.width = 0.002; md.segments = 3; md.limit_method = 'ANGLE'
        return ob, W, H, D

def place_flat(ob, x, y, z, yaw, tilt):
    """ob lies with face up (+Z), image top toward +Y; tilt lifts the back edge"""
    ob.location = (x, y, z)
    ob.rotation_euler = (math.radians(tilt), 0, math.radians(yaw))

def place_stand(ob, x, y, z, yaw, lean):
    ob.location = (x, y, z)
    ob.rotation_euler = (math.radians(-lean), 0, math.radians(yaw))

# ---------------- name card
def name_card(line1, line2, loc, rot):
    root = bpy.data.objects.new('card', None); link(root)
    cw, ch = 0.10, 0.06
    m, b = principled('card', srgb('FFFDF7'), 0.7); paper_bump(m, b, 800, 0.04)
    c = cuboid('cardp', cw, ch, 0.0006, (0, 0, 0), m, bevel=0); c.parent = root
    fnt = bpy.data.fonts.load(os.path.abspath('fonts/Lora-Italic.ttf'))
    tm, tb = principled('ink', srgb('5A3C32'), 0.6)
    for txt, sz, y in ((line1, 0.014, 0.006), (line2, 0.0085, -0.014)):
        cu = bpy.data.curves.new('t', 'FONT'); cu.body = txt; cu.font = fnt; cu.size = sz; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
        cu.materials.append(tm)
        t = bpy.data.objects.new('t', cu); link(t); t.location = (0, y, 0.00035); t.parent = root
    root.location = loc; root.rotation_euler = [math.radians(a) for a in rot]
    return root

# ---------------- scenes
THEME = {
    'blue': dict(box='2E5FC0', rib='A9C8F2', shred=['8DB6EE', 'C9DDF7', 'F4F7FC', '6E9BE0', 'B3CFF4']),
    'pink': dict(box='E77FAB', rib='FBE3EE', shred=['F4B3CC', 'FAD3E1', 'FFF3F7', 'EE96B9', 'FBC6D8']),
}
# items: key, x, y, yaw, tilt/lean, mode ('flat' or 'stand'), layer
LAYOUT = {
    'podarok_blue': dict(theme='blue', w=0.20, h=0.06, items=[
        ('HAR', -0.046, 0.022, 7, 24, 'flat', 0), ('PCHOC', 0.047, 0.028, -6, 26, 'flat', 0), ('TW42', 0.008, 0.026, -10, 6, 'stand', 0),
        ('KJ', -0.010, -0.020, 20, 55, 'stand', 1), ('FINI', -0.056, -0.042, 14, 14, 'flat', 1), ('TW20', 0.030, -0.040, -9, 10, 'flat', 1),
        ('KK', 0.004, -0.066, 4, 8, 'flat', 2)], card=('Артёму', 'С Новым годом!')),
    'podarok_pink': dict(theme='pink', w=0.20, h=0.06, items=[
        ('HAR', -0.046, 0.022, 7, 24, 'flat', 0), ('PSTR', 0.047, 0.028, -6, 26, 'flat', 0), ('PMINI', 0.006, 0.030, -12, 20, 'flat', 1),
        ('KJ', -0.010, -0.018, 20, 55, 'stand', 1), ('FINI', -0.056, -0.042, 14, 14, 'flat', 1), ('CHUPA', 0.044, -0.028, -10, 12, 'flat', 1),
        ('TW20', 0.020, -0.048, 8, 10, 'flat', 2), ('KK', 0.000, -0.068, -3, 8, 'flat', 3)], card=('Соне', 'С Новым годом!')),
    'wow_blue': dict(theme='blue', w=0.30, h=0.08, items=[
        ('BB', -0.080, 0.045, 6, 24, 'flat', 0), ('PCHOC', 0.000, 0.050, -2, 26, 'flat', 0), ('HAR', 0.082, 0.042, -7, 24, 'flat', 0),
        ('TW42', -0.095, -0.040, 8, 6, 'stand', 0), ('FINI', -0.040, -0.030, 10, 16, 'flat', 1), ('KJ', 0.020, -0.012, -20, 55, 'stand', 1),
        ('PMINI', 0.085, -0.030, -12, 18, 'flat', 1), ('TW20', 0.030, -0.065, 7, 10, 'flat', 2), ('TW20', -0.040, -0.088, -4, 8, 'flat', 2),
        ('KK', 0.060, -0.100, -3, 8, 'flat', 3)], card=('Диме', 'С Новым годом!')),
    'wow_pink': dict(theme='pink', w=0.30, h=0.08, items=[
        ('BB', -0.080, 0.045, 6, 24, 'flat', 0), ('PSTR', 0.000, 0.050, -2, 26, 'flat', 0), ('HAR', 0.082, 0.042, -7, 24, 'flat', 0),
        ('PMINI', -0.092, -0.035, 10, 16, 'flat', 1), ('FINI', -0.040, -0.030, 10, 16, 'flat', 1), ('KJ', 0.020, -0.012, -20, 55, 'stand', 1),
        ('CHUPA', 0.080, -0.010, -10, 12, 'flat', 1), ('PMINI', 0.090, -0.050, -12, 16, 'flat', 2), ('TW20', 0.030, -0.065, 7, 10, 'flat', 2),
        ('TW20', -0.040, -0.088, -4, 8, 'flat', 2), ('KK', 0.060, -0.100, -3, 8, 'flat', 3)], card=('Алисе', 'С Новым годом!')),
}

L = LAYOUT[BOX]; T = THEME[L['theme']]
w, h, t = L['w'], L['h'], 0.0022
world()
backdrop(A.get('bg', 'F1E7DC'))
boxmat = cardboard('box', T['box'])
rib = satin('ribbon', T['rib'])
open_box(w, h, t, boxmat, boxmat)
shred = shred_mat(T['shred'])
top = h - 0.016
fill_shred(w - 2 * t, top, shred, int(A.get('shred', str(int(5200 * (w / 0.2) ** 2)))))
sc_ = float(A.get('iscale', '0.92'))
for key, x, y, yaw, tl, mode, layer in L['items']:
    ob, W, H, D = product(key, sc_)
    zb = top + 0.006 + layer * 0.007
    if mode == 'flat':
        zz = zb + math.sin(math.radians(tl)) * H * 0.5 * 0.6
        place_flat(ob, x, y, zz, yaw, tl)
    elif key == 'KJ':
        a = math.radians(tl)
        place_stand(ob, x, y, top + 0.002 + H / 2 * math.cos(a) * 0.8 + layer * 0.004, yaw, tl)
    else:
        place_stand(ob, x, y, top - 0.012 + H / 2, yaw, tl)
# a few strands of shred over the front items for depth
fill_shred(w - 2 * t, top + 0.004, shred, int(A.get('shred2', str(int(260 * (w / 0.2) ** 2)))), mound=0.004, bottom=top, margin=0.02)

lw = w + 0.004
ld = lid(lw, 0.022 if w < 0.25 else 0.028, t, boxmat, rib)
lean = math.radians(float(A.get('lid_lean', '68')))
# lid stands behind the box, lower edge on the floor, leaning back; its top (window, bow) faces the camera
ld.rotation_euler = (lean, 0, math.radians(float(A.get('lid_yaw', '-8'))))
ld.location = (w * float(A.get('lid_x', '0.16')), w / 2 + 0.012 + math.cos(lean) * lw / 2, math.sin(lean) * lw / 2 + 0.001)
if L.get('card'):
    ct = math.radians(float(A.get('card_tilt', '64')))
    name_card(*L['card'], loc=(w * 0.30, -w / 2 - 0.004 - 0.03 * math.cos(ct), 0.03 * math.sin(ct) + 0.001), rot=(math.degrees(ct), 0, float(A.get('card_yaw', '-10'))))

# lights
area('key', (-0.55, -0.45, 0.75), (0, 0, 0.03), 0.9, float(A.get('key', '28')))
area('fill', (0.65, -0.35, 0.35), (0, 0, 0.03), 0.7, float(A.get('fill', '7')), (1, 0.97, 0.94))
area('rim', (0.1, 0.65, 0.55), (0, 0, 0.05), 0.6, float(A.get('rim', '9')))

# camera
el = math.radians(float(A.get('cam_el', '48'))); az = math.radians(float(A.get('cam_az', '-12')))
dist = float(A.get('cam_d', '0.78')) * (w / 0.2) ** 0.95
tgt = Vector((0, 0.02 * w / 0.2, 0.035))
cpos = tgt + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * dist
cd = bpy.data.cameras.new('cam'); cd.lens = float(A.get('lens', '60'))
cam = bpy.data.objects.new('cam', cd); link(cam); cam.location = cpos
cam.rotation_euler = (tgt - cpos).to_track_quat('-Z', 'Y').to_euler()
cd.dof.use_dof = True; cd.dof.focus_distance = (tgt - cpos).length; cd.dof.aperture_fstop = float(A.get('fstop', '11'))
sc.camera = cam

bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(f'{OUT}/scene.blend')) if A.get('saveblend') else None
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.abspath(f'{OUT}/{NAME}.png')
bpy.ops.render.render(write_still=True)
print('DONE', sc.render.filepath)
