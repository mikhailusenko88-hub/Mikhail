import bpy, sys, numpy as np, traceback
print("BLENDER", bpy.app.version_string)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
try:
    cu = bpy.data.hair_curves.new("Fur")
    print("CURVES DIR", [d for d in dir(cu) if not d.startswith('_')])
    N = 2000; P = 4
    cu.add_curves([P] * N)
    rng = np.random.default_rng(1)
    roots = rng.uniform(-0.5, 0.5, (N, 3)); roots[:, 2] = 0
    pts = np.repeat(roots, P, axis=0); t = np.tile(np.linspace(0, 1, P), N)
    pts[:, 2] += t * 0.3; pts[:, 0] += t * t * 0.05
    cu.position_data.foreach_set('vector', pts.astype(np.float32).ravel())
    print("ATTRS", [a.name for a in cu.attributes])
    if 'radius' not in cu.attributes: cu.attributes.new('radius', 'FLOAT', 'POINT')
    cu.attributes['radius'].data.foreach_set('value', (0.004 * (1 - t * 0.8)).astype(np.float32))
    a = cu.attributes.new('mel', 'FLOAT', 'CURVE'); a.data.foreach_set('value', rng.uniform(0.2, 0.6, N).astype(np.float32))
    ob = bpy.data.objects.new("Fur", cu); sc.collection.objects.link(ob)
    m = bpy.data.materials.new("hair"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); h = nt.nodes.new('ShaderNodeBsdfHairPrincipled'); h.parametrization = 'MELANIN'
    at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'mel'
    nt.links.new(at.outputs['Fac'], h.inputs['Melanin']); nt.links.new(h.outputs[0], o.inputs[0])
    print("HAIR INPUTS", [i.name for i in h.inputs])
    cu.materials.append(m)
    print("CURVES OK")
except Exception:
    traceback.print_exc()
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -2, 0.6); cam.rotation_euler = (1.35, 0, 0)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 3; sc.collection.objects.link(sun); sun.rotation_euler = (0.6, 0.3, 0)
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[1].default_value = 0.5
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 16; sc.render.resolution_x = 320; sc.render.resolution_y = 180
print("CURVES SHAPE OPTS", sc.cycles_curves.bl_rna.properties['shape'].enum_items.keys() if hasattr(sc, 'cycles_curves') else None)
print("VIEW TRANSFORMS", [v for v in ['AgX', 'Filmic', 'Standard']])
print("LOOKS", sc.view_settings.bl_rna.properties['look'].enum_items.keys())
sc.render.filepath = "//out/api_test.png"
bpy.ops.render.render(write_still=True)
print("RENDER DONE")
