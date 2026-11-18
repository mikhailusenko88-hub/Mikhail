"""Ведро цветных шаров высыпается в стеклянный куб — Blender 4.2, Cycles, настоящая физика (Bullet).
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
sc.view_settings.look = A.get("look", "Medium High Contrast")
sc.view_settings.exposure = float(A.get("ev", "0"))
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


m_floor, _ = mat_principled("floor", **{"Base Color": (0.006, 0.007, 0.010, 1), "Roughness": 0.16, "Specular IOR Level": 0.7})
m_glass, _ = mat_principled("glass", **{"Base Color": (0.97, 0.99, 1.0, 1), "Roughness": 0.015, "IOR": 1.5, "Transmission Weight": 1.0})
m_metal, _ = mat_principled("bucket", **{"Base Color": (0.015, 0.09, 0.42, 1), "Roughness": 0.22, "Coat Weight": 0.6, "Coat Roughness": 0.08})   # синее эмалированное ведро
m_ball, pb = mat_principled("ball", **{"Roughness": 0.18, "Coat Weight": 0.8, "Coat Roughness": 0.04})
nt = m_ball.node_tree
oi = nt.nodes.new("ShaderNodeObjectInfo")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = "CONSTANT"
PAL = [(0.85, 0.01, 0.02), (1.0, 0.22, 0.0), (1.0, 0.62, 0.0), (0.04, 0.6, 0.04), (0.0, 0.45, 0.85),
       (0.03, 0.08, 0.9), (0.35, 0.03, 0.85), (0.95, 0.04, 0.35)]   # линейные значения: в Standard выходят сочными
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
w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.005, 0.009, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0

bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(m_floor)


def area(name, loc, rot, size, power, color):
    d = bpy.data.lights.new(name, "AREA")
    d.size = size
    d.energy = power
    d.color = color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


area("top", (0.0, -0.55, 1.35), (math.radians(28), 0, 0), 0.55, 160, (1.0, 0.95, 0.88))
area("rim", (0.7, 0.55, 0.75), (math.radians(-55), math.radians(35), math.radians(140)), 0.45, 140, (0.55, 0.7, 1.0))
area("fill", (-0.9, -0.8, 0.5), (math.radians(70), 0, math.radians(-50)), 0.5, 45, (1.0, 0.8, 0.7))

# ---------------------------------------------------------------- физика
bpy.ops.rigidbody.world_add()
rbw = sc.rigidbody_world
rbw.substeps_per_frame = 8
rbw.solver_iterations = 10
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


# стеклянный куб: внутри 0,32 × 0,20 × 0,50 м, стенки 8 мм
GW, GD, GH, T = 0.32, 0.20, 0.50, 0.004
slabs = [((0, 0, T / 2), (GW + 2 * T, GD + 2 * T, T)),
         ((-(GW + T) / 2, 0, GH / 2 + T), (T, GD + 2 * T, GH)),
         (((GW + T) / 2, 0, GH / 2 + T), (T, GD + 2 * T, GH)),
         ((0, -(GD + T) / 2, GH / 2 + T), (GW, T, GH)),
         ((0, (GD + T) / 2, GH / 2 + T), (GW, T, GH))]
for loc, dim in slabs:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.scale = dim
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_flat()
    o.data.materials.append(m_glass)
    add_rb(o, "PASSIVE", "BOX", friction=0.45, rest=0.15)
add_rb(floor, "PASSIVE", "BOX", friction=0.6, rest=0.12)

# ведро: усечённый конус без крышки, стенка 5 мм; начало координат — на кромке, через которую льётся
R0, R1, BH = 0.13, 0.17, 0.25
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=56, radius1=R0, radius2=R1, depth=BH)
top = [f for f in bm.faces if f.calc_center_median().z > BH / 2 - 1e-4]
bmesh.ops.delete(bm, geom=top, context="FACES")
bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-R1, 0, BH / 2)))      # кромка (x=+R1, верх) → в ноль
bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0, 0, -BH)))
me = bpy.data.meshes.new("bucket")
bm.to_mesh(me)
bm.free()
bucket = bpy.data.objects.new("bucket", me)
sc.collection.objects.link(bucket)
sol = bucket.modifiers.new("sol", "SOLIDIFY")
sol.thickness = 0.005
sol.offset = 1.0
bev = bucket.modifiers.new("bev", "BEVEL")
bev.width = 0.002
bucket.data.materials.append(m_metal)
for p in bucket.data.polygons:
    p.use_smooth = True
LIP = Vector((-0.11, 0.0, GH + T + 0.07))        # кромка над левой половиной куба: струя уходит вправо и падает в середину
bucket.location = LIP
rb = add_rb(bucket, "PASSIVE", "MESH", friction=0.35, rest=0.3)
rb.kinematic = True
rb.mesh_source = "FINAL"
# наклон: стоит до 0,6 с, к 2,3 с опрокинуто на 128°
for f, ang in ((1, 0), (20, 0), (50, 45), (95, 92), (150, 132), (FR_END, 132)):   # плавно: ровная струя
    bucket.rotation_euler = (0, math.radians(ang), 0)
    bucket.keyframe_insert("rotation_euler", frame=f)
for fc in bucket.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "BEZIER"

# шары: сеткой внутри ведра (в его локальных координатах), с дрожанием
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=BR, location=(0, 0, -5))
base = bpy.context.active_object
bpy.ops.object.shade_smooth()
base.data.materials.append(m_ball)
add_rb(base, "ACTIVE", "SPHERE", friction=0.5, rest=0.16, mass=0.012)
base.rigid_body.linear_damping = 0.1
base.rigid_body.angular_damping = 0.25
step = 2.08 * BR
balls = []
cz = -BH + BR + 0.004
center = Vector((-R1, 0, 0))
while cz < -0.03:
    rmax = R0 + (R1 - R0) * ((cz + BH) / BH) - BR - 0.006
    nx = int(rmax / step)
    for ix in range(-nx, nx + 1):
        for iy in range(-nx, nx + 1):
            x, y = ix * step, iy * step
            if x * x + y * y > rmax * rmax:
                continue
            p = center + Vector((x + random.uniform(-0.15, 0.15) * BR, y + random.uniform(-0.15, 0.15) * BR, cz))
            o = base.copy()
            sc.collection.objects.link(o)
            if rbw.collection.objects.get(o.name) is None:
                rbw.collection.objects.link(o)
            o.location = LIP + p
            balls.append(o)
    cz += step
bpy.data.objects.remove(base, do_unlink=True)
print(f"шаров {len(balls)}, сцена {time.time() - t0:.0f} с", flush=True)

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
tgt.location = (-0.03, 0, 0.36)
c = cam.constraints.new("TRACK_TO")
c.target = tgt
c.track_axis = "TRACK_NEGATIVE_Z"
c.up_axis = "UP_Y"
for f, y, z in ((1, -1.80, 0.66), (FR_END, -1.58, 0.58)):
    cam.location = (-0.05, y, z)
    cam.keyframe_insert("location", frame=f)
cam_d.dof.use_dof = True
cam_d.dof.focus_object = tgt
cam_d.dof.aperture_fstop = 8

# ---------------------------------------------------------------- симуляция (по кадрам) и координаты для звука
pos = np.zeros((SIM_TO, len(balls), 3), np.float32)
for f in range(1, SIM_TO + 1):
    sc.frame_set(f)
    for i, o in enumerate(balls):
        pos[f - 1, i] = o.matrix_world.translation
    if f % 30 == 0:
        print(f"кадр {f}, {time.time() - t0:.0f} с", flush=True)
np.savez_compressed(os.path.join(OUT, "pos.npz"), pos=pos.astype(np.float16), r=BR, fps=30,
                    glass=np.array([GW, GD, GH, T]))
print(f"симуляция готова, {time.time() - t0:.0f} с", flush=True)

# ---------------------------------------------------------------- рендер
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.jpg")
    bpy.ops.render.render(write_still=True)
    print(f"кадр {f} нарисован, {time.time() - t0:.0f} с", flush=True)
