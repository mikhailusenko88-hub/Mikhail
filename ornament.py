"""Ёлочные шары, полные цветных шариков, падают на пол и разбиваются (осколки на ломких связях). Blender 4.2, Cycles, Bullet.
Параметры: cols=red,gold  ox  R (радиус шара-игрушки)  nsh (осколков)  thr (прочность связей)  h0 (высота низа шара в кадре 1)  ts (замедление)  r (шарики внутри).
Серия «ведро против сосуда». Blender 4.2, Cycles, физика Bullet. Параметры как в marbles.py + vessel=cat, nosim=1.
blender -b --factory-startup -P marbles.py -- name=NAME frames=40,120,220 res=1080x1920 samples=64 n=3000
  frames=a,b,c   — какие кадры отрисовать (симуляция идёт до последнего)
  range=S-E      — кадры подряд (для видео)
Выход: out/NAME/f_0040.jpg …, out/NAME/pos.npz (координаты шаров по кадрам — для звука)."""
import math
import os
import random
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
A = dict(a.split("=", 1) for a in argv if "=" in a)
NAME = A.get("name", "test")
OUT = os.path.join("out", NAME)
os.makedirs(OUT, exist_ok=True)
RX, RY = (int(v) for v in A.get("res", "1080x1920").split("x"))
SAMPLES = int(A.get("samples", "64"))
FR_END = int(A.get("end", "300"))
if "range" in A:
    a, b = (int(v) for v in A["range"].split("-"))
    FRAMES = list(range(a, b + 1))
else:
    FRAMES = [int(v) for v in A.get("frames", "40,120,220").split(",")]
SIM_TO = max(FRAMES) if "range" not in A else max(FRAMES)
BR = float(A.get("r", "0.0075"))                 # радиус шара, м
SEED = int(A.get("seed", "7"))
ANIM = A.get("anim")                             # out/<sim>/anim.npz — готовое движение шаров (рендер без физики)
BG = A.get("bg", "light")                         # dark — тёмная студия (первый ролик), light — светлая студия с циклорамой (как у топа ниши)
LP = float(A.get("lp", "0.55"))                     # множитель силы ламп
PALN = A.get("pal", "rainbow")                   # rainbow | candy (пастель)
random.seed(SEED)
t0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = float(A.get("noise", "0.03"))
sc.cycles.use_denoising = True
sc.cycles.denoiser = "OPENIMAGEDENOISE"
sc.cycles.max_bounces = 10
sc.cycles.transmission_bounces = 10
sc.cycles.transparent_max_bounces = 10
sc.cycles.glossy_bounces = 6
sc.cycles.caustics_reflective = False
sc.cycles.caustics_refractive = False
sc.cycles.blur_glossy = 1.0
sc.render.resolution_x, sc.render.resolution_y = RX, RY
sc.render.resolution_percentage = 100
sc.render.fps = 30
sc.frame_start, sc.frame_end = 1, FR_END
sc.view_settings.view_transform = A.get("vt", "Standard")
try:
    sc.view_settings.look = A.get("look", "Medium High Contrast").replace("_", " ")
except TypeError as e:                           # имя «вида» не подошло к этому view transform — без него
    print("look не подошёл:", e, flush=True)
    sc.view_settings.look = "None"
sc.view_settings.exposure = float(A.get("ev", "-1.3"))
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 93

# ---------------------------------------------------------------- материалы
def mat_principled(name, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return m, p


if BG == "light":
    m_floor, _ = mat_principled("floor", **{"Base Color": (0.40, 0.40, 0.42, 1), "Roughness": 0.34, "Specular IOR Level": 0.45})
else:
    m_floor, _ = mat_principled("floor", **{"Base Color": (0.006, 0.007, 0.010, 1), "Roughness": 0.16, "Specular IOR Level": 0.7})
m_glass, _ = mat_principled("glass", **{"Base Color": (0.97, 0.99, 1.0, 1), "Roughness": 0.015, "IOR": 1.5, "Transmission Weight": 1.0})
m_metal, _ = mat_principled("bucket", **{"Base Color": (0.012, 0.07, 0.36, 1), "Roughness": 0.35, "Coat Weight": 0.35, "Coat Roughness": 0.18})   # синее эмалированное ведро
m_ball, pb = mat_principled("ball", **{"Roughness": 0.18, "Coat Weight": 0.8, "Coat Roughness": 0.04})
nt = m_ball.node_tree
oi = nt.nodes.new("ShaderNodeObjectInfo")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = "CONSTANT"
PAL = [(0.85, 0.01, 0.02), (1.0, 0.22, 0.0), (1.0, 0.62, 0.0), (0.04, 0.6, 0.04), (0.0, 0.45, 0.85),
       (0.03, 0.08, 0.9), (0.35, 0.03, 0.85), (0.95, 0.04, 0.35)]   # линейные значения: в Standard выходят сочными
if PALN == "candy":                              # пастель «леденцы»
    PAL = [(1.0, 0.32, 0.45), (1.0, 0.52, 0.22), (1.0, 0.82, 0.2), (0.3, 0.82, 0.5), (0.3, 0.62, 1.0),
           (0.55, 0.4, 1.0), (1.0, 0.25, 0.25), (0.15, 0.78, 0.82)]
els = ramp.color_ramp.elements
while len(els) < len(PAL):
    els.new(0.5)
for i, c in enumerate(PAL):
    els[i].position = i / len(PAL)
    els[i].color = (*c, 1)
nt.links.new(oi.outputs["Random"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], pb.inputs["Base Color"])

# ---------------------------------------------------------------- мир, пол, свет
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
if BG == "light":
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.56, 0.60, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = float(A.get("wl", "0.8"))
else:
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.005, 0.009, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0

bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(m_floor)
if BG == "light":                                # циклорама: пол плавно переходит в стену — фон без линии горизонта
    prof = [(0.45 + 0.9 * math.sin(math.radians(a)), 0.9 - 0.9 * math.cos(math.radians(a))) for a in range(0, 91, 5)] + [(1.35, 4.0)]
    bmc = bmesh.new()
    rows = []
    for x in (-5.0, 5.0):
        rows.append([bmc.verts.new((x, y, max(z, 0.0006))) for y, z in prof])
    for i in range(len(prof) - 1):
        bmc.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    mec = bpy.data.meshes.new("cyc")
    bmc.to_mesh(mec)
    bmc.free()
    cyc = bpy.data.objects.new("cyc", mec)
    sc.collection.objects.link(cyc)
    cyc.data.materials.append(m_floor)
    for pg in cyc.data.polygons:
        pg.use_smooth = True


def area(name, loc, rot, size, power, color):
    d = bpy.data.lights.new(name, "AREA")
    d.size = size
    d.energy = power * LP
    d.color = color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    o.visible_camera = False
    return o


area("top", (0.05, -0.45, 1.45), (math.radians(20), 0, 0), 0.7, 150, (1.0, 0.95, 0.88))
area("rim", (0.7, 0.55, 0.75), (math.radians(-55), math.radians(35), math.radians(140)), 0.45, 140 * float(A.get("rim", "0.25")), (0.55, 0.7, 1.0))   # в светлой студии rim<1: иначе синее пятно на стене
area("fill", (-0.9, -0.8, 0.5), (math.radians(70), 0, math.radians(-50)), 0.5, 45, (1.0, 0.8, 0.7))

# ---------------------------------------------------------------- физика
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = int(A.get("sub", "10"))
rbw.solver_iterations = int(A.get("it", "10"))
rbw.point_cache.frame_start = 1
rbw.point_cache.frame_end = FR_END


def add_rb(obj, typ, shape, friction=0.45, rest=0.35, mass=0.01):
    bpy.context.view_layer.objects.active = obj
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.ops.rigidbody.object_add(type=typ)
    rb = obj.rigid_body
    rb.collision_shape = shape
    rb.friction = friction
    rb.restitution = rest
    rb.mass = mass
    rb.collision_margin = 0.0008
    return rb



# ---------------------------------------------------------------- ёлочные шары
ts = float(A.get("ts", "0.6"))                   # замедление времени физики (0,6 — плавнее, «слоу-мо»)
rbw.time_scale = ts
ORN_R = float(A.get("R", "0.085"))
NSH = int(A.get("nsh", "60"))
THR = float(A.get("thr", "0.6"))
H0 = float(A.get("h0", "0.45"))
OXO = float(A.get("ox", "0.12"))
COLS = A.get("cols", "red,gold").split(",")
BRK = A.get("brk", "auto") == "auto"            # auto — раскол по сценарию в момент удара; off — только ломкие связи (thr)
BRK_SPREAD = int(A.get("spread", "3"))          # за сколько кадров трещина пробегает от низа до верха
F_IMP = 1 + int(math.sqrt(2 * float(A.get("h0", "0.45")) / 9.81) * 30 / float(A.get("ts", "0.6")))   # кадр касания пола
SHRINK = float(A.get("shrink", "0.998"))         # осколки чуть сжаты к своему центру (0,985 — видна сетка трещин)
ORN_COL = {
    "red": {"Base Color": (0.62, 0.012, 0.02, 1), "Metallic": 0.55, "Roughness": 0.12, "Coat Weight": 1.0, "Coat Roughness": 0.03},
    "gold": {"Base Color": (1.0, 0.70, 0.28, 1), "Metallic": 1.0, "Roughness": 0.14, "Coat Weight": 0.6, "Coat Roughness": 0.05},
    "purple": {"Base Color": (0.22, 0.03, 0.55, 1), "Metallic": 0.55, "Roughness": 0.12, "Coat Weight": 1.0, "Coat Roughness": 0.03},
    "silver": {"Base Color": (0.9, 0.92, 0.95, 1), "Metallic": 1.0, "Roughness": 0.1},
    "green": {"Base Color": (0.02, 0.35, 0.08, 1), "Metallic": 0.55, "Roughness": 0.12, "Coat Weight": 1.0, "Coat Roughness": 0.03},
}
m_cap, _ = mat_principled("cap", **ORN_COL["silver"])
# толстая невидимая плита вместо тонкой плоскости пола: иначе быстрые осколки проваливаются сквозь пол и удар гасится
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.05))
slab = bpy.context.active_object
slab.scale = (3.0, 3.0, 0.1)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
slab.hide_render = True
slab.display_type = "WIRE"
add_rb(slab, "PASSIVE", "BOX", friction=0.6, rest=0.25)
rng_o = np.random.default_rng(SEED)
dyn = []                                         # всё, что движется: осколки, колпачки, шарики (порядок = столбцы pos.npz)
NSHARD = 0


def fib_sphere(n, jit):
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    th = np.pi * (1 + 5 ** 0.5) * k
    p = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    p += rng_o.normal(0, jit, p.shape)
    return p / np.linalg.norm(p, axis=1, keepdims=True)


def make_ornament(cx, col):
    """Сфера → ячейки Вороного по поверхности → осколки (стенка 2 мм), склеенные ломкими связями."""
    global NSHARD
    cz = H0 + ORN_R
    mat, _ = mat_principled("orn_" + col, **ORN_COL[col])
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=ORN_R)
    bm.faces.ensure_lookup_table()
    seeds = fib_sphere(NSH, 0.12)
    fc = np.array([tuple(f.calc_center_median()) for f in bm.faces])
    lab = np.argmax((fc / np.linalg.norm(fc, axis=1, keepdims=True)) @ seeds.T, axis=1)
    adj = set()
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2:
            a, b = lab[lf[0].index], lab[lf[1].index]
            if a != b:
                adj.add((min(a, b), max(a, b)))
    pieces = {}
    for pid in range(NSH):
        fidx = np.where(lab == pid)[0]
        if not len(fidx):
            continue
        verts, faces, vmap = [], [], {}
        for fi in fidx:
            f = bm.faces[int(fi)]
            ids = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = len(verts)
                    verts.append(tuple(v.co))
                ids.append(vmap[v.index])
            faces.append(ids)
        V = np.array(verts)
        c = V.mean(0)
        V = c + (V - c) * SHRINK - c                  # сжать к центру осколка, начало координат — в центре
        me = bpy.data.meshes.new(f"sh_{col}_{pid}")
        me.from_pydata(V.tolist(), [], faces)
        me.update()
        for pg in me.polygons:
            pg.use_smooth = True
        NR = np.array(verts)
        NR /= np.linalg.norm(NR, axis=1, keepdims=True)              # нормали как у целой сферы — швов между осколками не видно
        try:
            me.normals_split_custom_set_from_vertices([tuple(v) for v in NR])
        except Exception as ex:
            print("нормали:", ex, flush=True)
        o = bpy.data.objects.new(f"sh_{col}_{pid}", me)
        sc.collection.objects.link(o)
        o.location = (cx + c[0], c[1], cz + c[2])
        sol = o.modifiers.new("sol", "SOLIDIFY")
        sol.thickness = 0.002
        sol.offset = -1.0
        o.data.materials.append(mat)
        if not ANIM:
            rb = add_rb(o, "ACTIVE", "CONVEX_HULL", friction=0.5, rest=0.25, mass=0.003)
            rb.mesh_source = "FINAL"
            rb.collision_margin = 0.0004
        pieces[pid] = (o, c)
        dyn.append(o)
    bm.free()
    # колпачок с петелькой — приклеен к трём верхним осколкам
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.017, depth=0.022, location=(cx, 0, cz + ORN_R + 0.006))
    cap = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    cap.data.materials.append(m_cap)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.008, minor_radius=0.0018, location=(cx, 0, cz + ORN_R + 0.022), rotation=(math.radians(90), 0, 0))
    loop = bpy.context.active_object
    loop.data.materials.append(m_cap)
    loop.parent = cap
    loop.matrix_parent_inverse = cap.matrix_world.inverted()
    if not ANIM:
        add_rb(cap, "ACTIVE", "CONVEX_HULL", friction=0.5, rest=0.2, mass=0.004)
    dyn.append(cap)
    NSHARD += len(pieces) + 1
    if ANIM:
        return cz
    top = sorted(pieces, key=lambda k: -pieces[k][1][2])[:3]
    links = list(adj) + [(-1, t) for t in top]
    for a, b in links:
        oa = cap if a == -1 else pieces[a][0]
        ob = pieces[b][0]
        e = bpy.data.objects.new("con", None)
        sc.collection.objects.link(e)
        e.location = (Vector(oa.location) + Vector(ob.location)) / 2
        bpy.context.view_layer.objects.active = e
        for s_ in bpy.context.selected_objects:
            s_.select_set(False)
        e.select_set(True)
        bpy.ops.rigidbody.constraint_add(type="FIXED")
        k = e.rigid_body_constraint
        k.object1, k.object2 = oa, ob
        k.use_breaking = True
        k.breaking_threshold = THR
        k.disable_collisions = True
        if BRK:                                      # раскол по сценарию: связи выключаются в момент удара, снизу вверх (трещина бежит от пола)
            zrel = (e.location.z - (cz - ORN_R)) / (2 * ORN_R)          # 0 — низ шара, 1 — верх
            fb = F_IMP + int(round(zrel * BRK_SPREAD)) + int(rng_o.integers(0, 2))
            k.enabled = True
            k.keyframe_insert("enabled", frame=max(1, fb - 1))
            k.enabled = False
            k.keyframe_insert("enabled", frame=fb)
    return cz


CENTERS = []
for i, col in enumerate(COLS):
    cx = (i - (len(COLS) - 1) / 2) * 2 * OXO
    CENTERS.append((cx, make_ornament(cx, col)))
print(f"осколков и колпачков {NSHARD}, связей {len([o for o in sc.objects if o.name.startswith('con')])}", flush=True)

# шарики внутри: сеткой с дрожанием
BR = float(A.get("r", "0.006"))
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=BR, location=(0, 0, -5))
base = bpy.context.active_object
bpy.ops.object.shade_smooth()
base.data.materials.append(m_ball)
if not ANIM:
    add_rb(base, "ACTIVE", "SPHERE", friction=0.5, rest=float(A.get("brest", "0.45")), mass=0.002)
    base.rigid_body.linear_damping = 0.05
    base.rigid_body.angular_damping = float(A.get("adamp", "0.6"))
step = 2.08 * BR
RIN = ORN_R - 0.0022 - BR - 0.0015
balls = []
NB = []
for cx, cz in CENTERS:
    n0 = len(balls)
    m = int(RIN / step)
    for ix in range(-m, m + 1):
        for iy in range(-m, m + 1):
            for iz in range(-m, m + 1):
                x, y, z = ix * step, iy * step, iz * step
                if x * x + y * y + z * z > RIN * RIN:
                    continue
                o = base.copy()
                sc.collection.objects.link(o)
                if not ANIM and rbw.collection.objects.get(o.name) is None:
                    rbw.collection.objects.link(o)
                o.location = (cx + x + random.uniform(-0.1, 0.1) * BR, y + random.uniform(-0.1, 0.1) * BR, cz + z)
                balls.append(o)
    NB.append(len(balls) - n0)
bpy.data.objects.remove(base, do_unlink=True)
dyn += balls
balls = dyn                                      # дальше (запись движения и рендер) — все движущиеся тела
VES = None
LIFT = 0.0
print(f"шариков {NB}, всего тел {len(balls)}, сцена {time.time() - t0:.0f} с", flush=True)

# ---------------------------------------------------------------- камера: вертикальный кадр, медленный наезд
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 50
cam_d.sensor_fit = "VERTICAL"
cam_d.sensor_height = 36
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
tgt = bpy.data.objects.new("tgt", None)
sc.collection.objects.link(tgt)
tgt.location = (float(A.get("tx", "0")), 0, float(A.get("tz", "0.14")))
c = cam.constraints.new("TRACK_TO")
c.target = tgt
c.track_axis = "TRACK_NEGATIVE_Z"
c.up_axis = "UP_Y"
CY0, CY1 = float(A.get("cy0", "-2.15")), float(A.get("cy1", "-1.85"))     # камера: отъезд/наезд (м) и высота
CZ0, CZ1 = float(A.get("cz0", "0.72")), float(A.get("cz1", "0.62"))
for f, y, z in ((1, CY0, CZ0), (FR_END, CY1, CZ1)):
    cam.location = (float(A.get("cx", "0")), y, z)
    cam.keyframe_insert("location", frame=f)
cam_d.dof.use_dof = True
cam_d.dof.focus_object = tgt
cam_d.dof.aperture_fstop = 8

# ---------------------------------------------------------------- симуляция (по кадрам) или готовое движение
if ANIM:
    an = np.load(ANIM)
    APOS, AROT = an["pos"].astype(np.float32), an["rot"].astype(np.float32)
    assert APOS.shape[1] == len(balls), (APOS.shape, len(balls))
    for o in balls:
        o.rotation_mode = "QUATERNION"
    for f in FRAMES:
        sc.frame_set(f)
        k = min(f - 1, APOS.shape[0] - 1)
        for i, o in enumerate(balls):
            o.location = APOS[k, i]
            o.rotation_quaternion = AROT[k, i]
        sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
        bpy.ops.render.render(write_still=True)
        print(f"кадр {f} нарисован, {time.time() - t0:.0f} с", flush=True)
    sys.exit(0)

if A.get("nosim"):
    rbw.enabled = False                          # проба вида: без физики, но вёдра наклоняются по кадрам
    for f in FRAMES:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
        bpy.ops.render.render(write_still=True)
    sys.exit(0)
pos = np.zeros((SIM_TO, len(balls), 3), np.float32)
rot = np.zeros((SIM_TO, len(balls), 4), np.float32)
for f in range(1, SIM_TO + 1):
    sc.frame_set(f)
    for i, o in enumerate(balls):
        mw = o.matrix_world
        pos[f - 1, i] = mw.translation
        rot[f - 1, i] = mw.to_quaternion()
    if f % 30 == 0:
        print(f"кадр {f}, {time.time() - t0:.0f} с", flush=True)
np.savez_compressed(os.path.join(OUT, "pos.npz"), pos=pos.astype(np.float16), r=BR, fps=30, orn=1, nshard=NSHARD, nb=np.array(NB), ts=ts)
np.savez_compressed(os.path.join(OUT, "anim.npz"), pos=pos, rot=rot.astype(np.float16))
print(f"симуляция готова, {time.time() - t0:.0f} с", flush=True)
if A.get("mode") == "sim":
    sys.exit(0)

# ---------------------------------------------------------------- рендер
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
    bpy.ops.render.render(write_still=True)
    print(f"кадр {f} нарисован, {time.time() - t0:.0f} с", flush=True)
