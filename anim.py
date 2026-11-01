# Blender: 10 секунд Барсика в движении. blender -b -P anim.py -- chunk=0 of=20 [samples=40]
import bpy, sys, math, os, subprocess, time
import numpy as np
from mathutils import Vector, Euler

_args = dict(a.split('=') for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
CH, OF = int(_args.get('chunk', 0)), int(_args.get('of', 1)); ASPP = int(_args.get('samples', 40))
FPS, DUR = 25, 10.0; NF = int(FPS * DUR)
# общие материалы и окружение берём из render.py (без сборки героя)
sys.argv = ['blender', '--', 'mode=bg']
exec(open('render.py', encoding='utf-8').read().split('# ---------- сборка ----------')[0])
A = np.load('out/anim.npz'); RE = float(A['re'][0]); EY = A['eyes']; PIV = A['piv']
CAM0 = Vector((0.62, -2.4, 0.82)); CAM1 = Vector((0.5, -2.05, 0.8))

def empty(name, loc, parent=None):
    e = bpy.data.objects.new(name, None); sc.collection.objects.link(e); e.location = Vector(loc)
    if parent: e.parent = parent
    return e
def attach(ob, e):
    bpy.context.view_layer.update(); ob.parent = e; ob.matrix_parent_inverse = e.matrix_world.inverted()

SKIN = skin_material(); FUR = fur_material()
def skin_obj(name, v, f, n, col, reg, eyes_ring=True):
    me = bpy.data.meshes.new(name); me.from_pydata(v.tolist(), [], f.tolist()); me.update()
    me.polygons.foreach_set('use_smooth', np.ones(len(f), bool))
    try: me.normals_split_custom_set_from_vertices(n.tolist())
    except Exception as e: log('normals', e)
    rgb = col * 0.9
    rgb[reg == 2] = (0.9, 0.76, 0.6); rgb[reg == 8] = (0.62, 0.3, 0.32); rgb[reg == 10] = (0.16, 0.03, 0.03); rgb[reg == 11] = (0.72, 0.28, 0.32)
    if eyes_ring:
        ring = np.zeros(len(v), bool)
        for c in EY: q = v - c; ring |= (np.linalg.norm(q, axis=-1) < RE + 0.011) & (q[:, 1] < 0.01)
        rgb[ring] = (0.09, 0.04, 0.02)
    sss = np.where(reg == 8, 0.9, np.where(reg == 4, 0.5, 0.18)).astype(np.float32)
    ca = me.color_attributes.new('skin_col', 'FLOAT_COLOR', 'POINT'); ca.data.foreach_set('color', np.concatenate([rgb, np.ones((len(v), 1))], -1).astype(np.float32).ravel())
    sa = me.attributes.new('sss', 'FLOAT', 'POINT'); sa.data.foreach_set('value', sss)
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); me.materials.append(SKIN); return ob
def fur_obj(name, pre):
    P = A[pre + 'fur_pts']; n, k, _ = P.shape
    cu = bpy.data.hair_curves.new(name); cu.add_curves([k] * n); cu.position_data.foreach_set('vector', P.astype(np.float32).ravel())
    if 'radius' not in cu.attributes: cu.attributes.new('radius', 'FLOAT', 'POINT')
    t = np.tile(np.linspace(0, 1, k, dtype=np.float32), n)
    cu.attributes['radius'].data.foreach_set('value', (np.repeat(A[pre + 'fur_rad'], k) * (1.0 - 0.85 * t ** 1.3)).astype(np.float32))
    a = cu.attributes.new('col', 'FLOAT_COLOR', 'CURVE'); a.data.foreach_set('color', np.concatenate([A[pre + 'fur_col'], np.ones((n, 1))], -1).astype(np.float32).ravel())
    cu.materials.append(FUR); ob = bpy.data.objects.new(name, cu); sc.collection.objects.link(ob); return ob

# ---------- герой по частям ----------
body_e = empty('E_body', (0, 0, 0))
E = {'head': empty('E_head', PIV[0], body_e), 'armL': empty('E_armL', PIV[1], body_e), 'armR': empty('E_armR', PIV[2], body_e), 'tail': empty('E_tail', PIV[3], body_e)}
for nm in ['body', 'armL', 'armR', 'tail']:
    s = skin_obj(nm, A[nm + '_v'], A[nm + '_f'], A[nm + '_n'], A[nm + '_col'], A[nm + '_reg'], eyes_ring=False); fz = fur_obj(nm + '_fur', nm + '_')
    for o in (s, fz): attach(o, body_e if nm == 'body' else E[nm])
HEADS = {}
for var in ['base', 'a', 'o', 'blink']:
    pre = 'head_' if var == 'base' else 'head_%s_' % var
    HEADS[var] = skin_obj('head_' + var, A[pre + 'v'], A[pre + 'f'], A[pre + 'n'], A[pre + 'col'], A[pre + 'reg'], eyes_ring=var != 'blink'); attach(HEADS[var], E['head'])
attach(fur_obj('head_fur', 'head_'), E['head'])
BLINKFUR = fur_obj('blink_fur', 'blinkfur_'); attach(BLINKFUR, E['head'])
# глаза смотрят в камеру
EYEOBJ = []; cm = cornea_material()
import bmesh
for i, c in enumerate(EY):
    fwd = (CAM0 - Vector(c)).normalized(); rot = Vector((0, -1, 0)).rotation_difference(fwd)
    me = bpy.data.meshes.new('eye'); ob = bpy.data.objects.new('Eye%d' % i, me); sc.collection.objects.link(ob)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=48, radius=1.0); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob.scale = (RE, RE, RE); ob.location = Vector(c); ob.rotation_mode = 'QUATERNION'; ob.rotation_quaternion = rot; me.materials.append(eye_material(i))
    me2 = bpy.data.meshes.new('cornea'); co = bpy.data.objects.new('Cornea%d' % i, me2); sc.collection.objects.link(co)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0); bm.to_mesh(me2); bm.free()
    for p in me2.polygons: p.use_smooth = True
    co.parent = ob; co.scale = (0.872, 0.872, 0.872); co.location = (0, -0.208, 0); me2.materials.append(cm); co.visible_shadow = False
    attach(ob, E['head']); EYEOBJ += [ob, co]
attach(build_mesh('Nose', A['nose_v'], A['nose_f'], nose_material()), E['head'])
attach(build_mesh('Scarf', A['scarf_v'], A['scarf_f'], scarf_material()), body_e)
mm = flat_material('mouth', (0.12, 0.04, 0.03), 0.5); wm = flat_material('whisker', (0.92, 0.9, 0.86), 0.35); crm = flat_material('crease', (0.07, 0.035, 0.02), 0.5)
MB = [build_curve('MouthB%d' % i, l, 0.0017, 0.0015, mm) for i, l in enumerate(A['mouth_base'])]
MO = [build_curve('MouthO%d' % i, l, 0.0017, 0.0015, mm) for i, l in enumerate(A['mouth_open'])]
CR = [build_curve('Crease%d' % i, l, 0.0012, 0.0024, crm) for i, l in enumerate(A['creases'])]
WH = [build_curve('Whisk%d' % i, l, 0.0011, 0.00025, wm) for i, l in enumerate(A['whisk'])]
for o in MB + MO + CR + WH: attach(o, E['head'])

# ---------- окружение, свет, камера ----------
sc.view_layers[0].use_pass_mist = True
build_world()
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.6; sun.data.angle = math.radians(4); sun.data.color = (1.0, 0.85, 0.66)
sun.rotation_mode = 'QUATERNION'; sun.rotation_quaternion = Vector((0, 0, -1)).rotation_difference(Vector((0.55, 0.5, -0.67)).normalized())
def area_light(nm, en, size, col, loc, tgt):
    l = bpy.data.objects.new(nm, bpy.data.lights.new(nm, 'AREA')); sc.collection.objects.link(l); l.data.energy = en; l.data.size = size; l.data.color = col; l.location = loc; look_at(l, tgt); return l
area_light('Rim', 260, 0.8, (1.0, 0.9, 0.75), (-0.7, 1.1, 1.35), (0, 0, 0.72))
area_light('Key', 70, 1.6, (1.0, 0.95, 0.88), (-1.3, -1.5, 1.55), (0, -0.05, 0.7))
area_light('Fill', 45, 2.0, (0.75, 0.9, 1.0), (1.6, -1.0, 0.6), (0, 0, 0.6))
area_light('EyeLight', 8, 0.3, (1, 0.97, 0.93), (0.25, -2.0, 1.05), (0, -0.14, 0.77))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 55; cam.data.sensor_width = 36; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 3.2
compositor()

# ---------- движение ----------
def ss(a, b, t): x = min(1, max(0, (t - a) / (b - a))); return x * x * (3 - 2 * x)
def env(t, a, b, fade=0.25): return ss(a, a + fade, t) * (1 - ss(b - fade, b, t))
# речь: (начало, длительность, гласная) — «Привет! Я Барсик.» и «Пойдём гулять?»
SYL = [(1.05, .18, 'a'), (1.23, .22, 'a'), (1.62, .2, 'a'), (1.85, .2, 'a'), (2.05, .2, 'a'),
       (5.85, .2, 'o'), (6.05, .26, 'o'), (6.45, .18, 'o'), (6.63, .3, 'a')]
def mouth(t):
    for a, d, v in SYL:
        if a <= t < a + d:
            ph = (t - a) / d
            return v if 0.15 < ph < 0.8 else ('o' if v == 'a' and (ph < 0.3 or ph > 0.7) else 'base') if 0.08 < ph < 0.9 else 'base'
    return 'base'
def eyes_closed(t):
    if 8.25 <= t < 9.7: return True                       # довольно жмурится
    return any(b <= t < b + 0.12 for b in (0.5, 3.95, 7.75))
def pose(t):
    # голова: кивки при речи, поворот налево и обратно, наклон, довольный наклон в конце
    yaw = -0.5 * ss(2.7, 3.3, t) * (1 - ss(5.0, 5.6, t)) + 0.06 * math.sin(t * 0.9)
    pitch = 0.05 * math.sin(t * 7.5) * env(t, 1.0, 2.5) + 0.04 * math.sin(t * 6.5) * env(t, 5.8, 7.0) + 0.12 * ss(7.6, 7.9, t) * (1 - ss(7.9, 8.25, t)) - 0.06 * ss(8.2, 8.6, t)
    roll = 0.17 * env(t, 5.6, 7.7, 0.4) - 0.14 * ss(8.2, 8.7, t) + 0.03 * math.sin(t * 1.3)
    E['head'].rotation_euler = Euler((pitch, roll, yaw), 'XYZ')
    # правая лапа: машет «привет», потом зовёт за собой
    up = ss(0.95, 1.3, t) * (1 - ss(2.55, 3.0, t))
    wave = math.sin((t - 1.3) * 11) * 0.28 * env(t, 1.3, 2.55, 0.15)
    beck = ss(6.1, 6.4, t) * (1 - ss(7.3, 7.7, t)); bw = math.sin((t - 6.4) * 9) * 0.22 * env(t, 6.4, 7.3, 0.15)
    E['armR'].rotation_euler = Euler((-1.0 * beck + bw, -1.75 * up + wave, 0.0), 'XYZ')
    E['armL'].rotation_euler = Euler((0.04 * math.sin(t * 1.7), 0.05 * math.sin(t * 1.3 + 1), 0), 'XYZ')
    # хвост: машет всё время, в конце — трубой
    E['tail'].rotation_euler = Euler((-0.35 * ss(8.2, 8.8, t), 0.0, 0.28 * math.sin(t * 2.6)), 'XYZ')
    # дыхание и радостные подпрыгивания
    bounce = 0.012 * abs(math.sin((t - 8.3) * 6.0)) * env(t, 8.3, 9.9, 0.2)
    body_e.location = (0, 0, 0.003 * math.sin(t * 2 * math.pi / 2.8) + bounce)
    body_e.rotation_euler = Euler((0, 0.015 * math.sin(t * 1.1), 0), 'XYZ')
    # лицо: какой вариант головы
    closed = eyes_closed(t); m = 'base' if closed else mouth(t)
    for k, ob in HEADS.items(): ob.hide_render = not (k == ('blink' if closed else m))
    BLINKFUR.hide_render = not closed
    for o in EYEOBJ: o.hide_render = closed
    for o in MB: o.hide_render = m != 'base'
    for o in MO: o.hide_render = m == 'base' or closed
    for o in CR: o.hide_render = not closed
    # камера: медленный наезд
    k = ss(0, DUR, t); cam.location = CAM0.lerp(CAM1, k); look_at(cam, Vector((0, -0.03, 0.6)).lerp(Vector((0, -0.05, 0.66)), k))
    cam.data.dof.focus_distance = (cam.location - Vector((0.0, -0.15, 0.76))).length

r = sc.render; r.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = ASPP; sc.cycles.adaptive_threshold = 0.03
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 4
sc.cycles_curves.shape = 'THICK'; sc.cycles_curves.subdivisions = 2
r.resolution_x = 1280; r.resolution_y = 720; r.resolution_percentage = 100; r.use_compositing = True
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Punchy'
except Exception: pass
sc.render.use_persistent_data = True    # сцена не пересобирается заново на каждый кадр
per = math.ceil(NF / OF); frames = list(range(CH * per, min(NF, (CH + 1) * per)))
os.makedirs('out/frames', exist_ok=True); os.makedirs('out/anim', exist_ok=True)
for f in frames:
    pose(f / FPS); r.filepath = os.path.abspath('out/frames/%04d.png' % f)
    bpy.ops.render.render(write_still=True); log('кадр', f)
if frames:
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-start_number', str(frames[0]), '-i', 'out/frames/%04d.png', '-frames:v', str(len(frames)),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', 'out/anim/chunk_%02d.mp4' % CH], check=True)
log('кусок готов', CH, frames[:1], frames[-1:])
