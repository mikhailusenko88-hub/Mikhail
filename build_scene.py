# Сцена кадра движка «Мультиков» → Blender Cycles. Запуск: blender -b -P build_scene.py -- scene.json(.gz) out_prefix [samples] [width]
import bpy, json, sys, gzip, base64, math, os
from mathutils import Matrix, Vector
a = sys.argv[sys.argv.index('--') + 1:]; SRC, OUT = a[0], a[1]; SPP = int(a[2]) if len(a) > 2 else 192; WID = int(a[3]) if len(a) > 3 else 960
d = json.load(gzip.open(SRC, 'rt') if SRC.endswith('.gz') else open(SRC))
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # three (y вверх) → Blender (z вверх)
C3 = C.to_3x3()
def m4(x): return Matrix([[x[0], x[4], x[8], x[12]], [x[1], x[5], x[9], x[13]], [x[2], x[6], x[10], x[14]], [x[3], x[7], x[11], x[15]]])
# текстуры
imgs = []
for i, t in enumerate(d['texs']):
    fn = '/tmp/tx_%d.png' % i; open(fn, 'wb').write(base64.b64decode(t['url'].split(',')[1]))
    im = bpy.data.images.load(fn); im.colorspace_settings.name = 'sRGB' if t['srgb'] else 'Non-Color'; imgs.append((im, t))
mcache = {}
def material(md, has_vc, has_uv):
    key = json.dumps(md, sort_keys=True) + str(has_vc) + str(has_uv)
    if key in mcache: return mcache[key]
    m = bpy.data.materials.new('m%d' % len(mcache)); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    b = N['Principled BSDF']; col = N.new('ShaderNodeRGB'); col.outputs[0].default_value = (*md['color'], 1); out = col.outputs[0]; alpha = None
    if md['map'] is not None and has_uv:
        im, t = imgs[md['map']]; tx = N.new('ShaderNodeTexImage'); tx.image = im; tx.extension = 'REPEAT' if t['wrap'] else 'EXTEND'
        uv = N.new('ShaderNodeUVMap'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (t['rep'][0], t['rep'][1], 1); mp.inputs['Location'].default_value = (t['off'][0], t['off'][1], 0)
        Lk.new(uv.outputs[0], mp.inputs[0]); Lk.new(mp.outputs[0], tx.inputs[0])
        mu = N.new('ShaderNodeMix'); mu.data_type = 'RGBA'; mu.blend_type = 'MULTIPLY'; mu.inputs['Factor'].default_value = 1
        Lk.new(out, mu.inputs['A']); Lk.new(tx.outputs['Color'], mu.inputs['B']); out = mu.outputs['Result']; alpha = tx.outputs['Alpha']
    if has_vc and md['vc']:
        at = N.new('ShaderNodeAttribute'); at.attribute_name = 'Col'; mu = N.new('ShaderNodeMix'); mu.data_type = 'RGBA'; mu.blend_type = 'MULTIPLY'; mu.inputs['Factor'].default_value = 1
        Lk.new(out, mu.inputs['A']); Lk.new(at.outputs['Color'], mu.inputs['B']); out = mu.outputs['Result']
    if md['unlit']:
        b.inputs['Base Color'].default_value = (0, 0, 0, 1); Lk.new(out, b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.0
    else:
        Lk.new(out, b.inputs['Base Color']); b.inputs['Roughness'].default_value = max(.05, md['rough']); b.inputs['Metallic'].default_value = md['metal']
        if md['sheen']: b.inputs['Sheen Weight'].default_value = md['sheen']
        if md['clearcoat']: b.inputs['Coat Weight'].default_value = md['clearcoat']
        if max(md['emis']) > 0: b.inputs['Emission Color'].default_value = (*md['emis'], 1); b.inputs['Emission Strength'].default_value = 1.0
    if md['transparent'] or md['alphaTest'] > 0:
        if alpha is not None:
            if md['opacity'] < 1: mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = md['opacity']; Lk.new(alpha, mm.inputs[0]); alpha = mm.outputs[0]
            Lk.new(alpha, b.inputs['Alpha'])
        else: b.inputs['Alpha'].default_value = md['opacity']
    mcache[key] = m; return m
nobj = 0
for k, M in enumerate(d['meshes']):
    pos = M['pos']; nv = len(pos) // 3; idx = M['idx'] if M['idx'] else list(range(nv)); nt = len(idx) // 3
    if nt == 0: continue
    me = bpy.data.meshes.new('g%d' % k); me.vertices.add(nv); me.vertices.foreach_set('co', pos)
    me.loops.add(nt * 3); me.loops.foreach_set('vertex_index', idx); me.polygons.add(nt); me.polygons.foreach_set('loop_start', list(range(0, nt * 3, 3)))
    me.update(calc_edges=True)
    if M['uv']:
        uvl = me.uv_layers.new(name='UVMap'); uv = M['uv']; flat = [0.0] * (nt * 6)
        for j, vi in enumerate(idx): flat[j * 2] = uv[vi * 2]; flat[j * 2 + 1] = uv[vi * 2 + 1]
        uvl.data.foreach_set('uv', flat)
    if M['col']:
        at = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT'); c = M['col']; rgba = []
        for i in range(nv): rgba += [c[i * 3], c[i * 3 + 1], c[i * 3 + 2], 1.0]
        at.data.foreach_set('color', rgba)
    me.shade_smooth()
    if M['nrm']:
        n = M['nrm']
        try: me.normals_split_custom_set_from_vertices([(n[i * 3], n[i * 3 + 1], n[i * 3 + 2]) for i in range(nv)])
        except Exception as e: pass
    me.materials.append(material(M['mat'], bool(M['col']), bool(M['uv'])))
    for j, mw in enumerate(M['mats']):
        ob = bpy.data.objects.new('o%d' % nobj, me); ob.matrix_world = C @ m4(mw); sc.collection.objects.link(ob); nobj += 1
        if M.get('hero'): ob.pass_index = 1   # тела героев — маска для обучения
        if M.get('icol'):   # цвет экземпляра (книги на полке)
            md = dict(M['mat']); md['color'] = [md['color'][c] * M['icol'][j][c] for c in range(3)]; ob.material_slots[0].link = 'OBJECT'; ob.material_slots[0].material = material(md, bool(M['col']), bool(M['uv']))
# свет
for i, L in enumerate(d['lights']):
    if L['type'] == 'sun':
        ld = bpy.data.lights.new('sun%d' % i, 'SUN'); ld.energy = L['I']; ld.color = L['color']; ld.angle = math.radians(4 if L['shadow'] else 12)
        ob = bpy.data.objects.new('sun%d' % i, ld); v = (C3 @ Vector(L['dir'])).normalized(); ob.rotation_euler = (-v).to_track_quat('-Z', 'Y').to_euler()
    else:
        ld = bpy.data.lights.new('pt%d' % i, 'POINT'); ld.energy = 4 * math.pi * L['I']; ld.color = L['color']; ld.shadow_soft_size = .15
        ob = bpy.data.objects.new('pt%d' % i, ld); ob.location = C3 @ Vector(L['pos'])
    sc.collection.objects.link(ob)
# небо и окружение: полусферный свет three (облучённость = цвет × сила) → фон радиацией цвет × сила / π; + окружение three (градиент) × его силу
sky = [0, 0, 0]; gnd = [0, 0, 0]
for h in d['hemis']:
    for c in range(3): sky[c] += h['sky'][c] * h['I'] / math.pi; gnd[c] += h['ground'][c] * h['I'] / math.pi
E = d['envI']; up = [sky[c] + [.73, .82, 1.0][c] * E for c in range(3)]; hor = [(sky[c] + gnd[c]) / 2 + 1.0 * E for c in range(3)]; dn = [gnd[c] + [.25, .23, .19][c] * E for c in range(3)]
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; N = w.node_tree.nodes; Lk = w.node_tree.links
tc = N.new('ShaderNodeTexCoord'); sx = N.new('ShaderNodeSeparateXYZ'); mr = N.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1; cr = N.new('ShaderNodeValToRGB')
Lk.new(tc.outputs['Generated'], sx.inputs[0]); Lk.new(sx.outputs['Z'], mr.inputs['Value']); Lk.new(mr.outputs[0], cr.inputs[0])
el = cr.color_ramp.elements; el[0].position = 0; el[0].color = (*dn, 1); el[1].position = 1; el[1].color = (*up, 1); e = el.new(.5); e.color = (*hor, 1)
Lk.new(cr.outputs['Color'], N['Background'].inputs['Color']); N['Background'].inputs['Strength'].default_value = 1.0
# камера
cd = bpy.data.cameras.new('cam'); cd.sensor_fit = 'VERTICAL'; cd.angle_y = math.radians(d['cam']['fov']); cd.clip_start = d['cam']['near']; cd.clip_end = d['cam']['far']
co = bpy.data.objects.new('cam', cd); co.matrix_world = C @ m4(d['cam']['mw']); sc.collection.objects.link(co); sc.camera = co
# рендер
r = sc.render; r.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = True
r.resolution_x = WID; r.resolution_y = round(WID / d['cam']['aspect']); r.resolution_percentage = 100
try: sc.view_settings.view_transform = 'Khronos PBR Neutral'
except Exception: sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
vl = sc.view_layers[0]; vl.use_pass_object_index = True; vl.use_pass_ambient_occlusion = True; vl.use_pass_diffuse_direct = True; vl.use_pass_diffuse_indirect = True; vl.use_pass_diffuse_color = True
# маска тел героев (для обучения): компоновщик пишет её отдельным файлом
sc.use_nodes = True; ct = sc.node_tree; ct.nodes.clear(); rl = ct.nodes.new('CompositorNodeRLayers'); cp = ct.nodes.new('CompositorNodeComposite'); ct.links.new(rl.outputs['Image'], cp.inputs['Image'])
idm = ct.nodes.new('CompositorNodeIDMask'); idm.index = 1; fo = ct.nodes.new('CompositorNodeOutputFile'); fo.base_path = os.path.dirname(os.path.abspath(OUT)); fo.file_slots[0].path = os.path.basename(OUT) + '_mask'; fo.format.file_format = 'PNG'
ct.links.new(rl.outputs['IndexOB'], idm.inputs['ID value']); ct.links.new(idm.outputs['Alpha'], fo.inputs[0])
print('объектов', nobj, 'материалов', len(mcache), 'вид', sc.view_settings.view_transform, flush=True)
bpy.ops.render.render(write_still=False)
img = bpy.data.images['Render Result']
r.image_settings.file_format = 'PNG'; img.save_render(OUT + '.png')
r.image_settings.file_format = 'OPEN_EXR_MULTILAYER'; r.image_settings.color_depth = '16'; img.save_render(OUT + '.exr')
print('готово', OUT, flush=True)
