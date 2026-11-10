# Проверка: импорт FBX / OBJ / DAE / GLB в чистую сцену Blender (метры) и габариты.
import bpy, os, glob
ROOT = os.path.abspath('out/Наш декор — 3D-модели')
res = []
for rel in ['3 Плинтусы напольные/A703/A703', '2 Панели с декором/3-7/3-7', '1 Панели белые под покраску/A910/A910']:
    for ext in ('fbx', 'obj', 'dae', 'glb'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        p = f'{ROOT}/{rel}.{ext}'
        try:
            if ext == 'fbx': bpy.ops.import_scene.fbx(filepath=p)
            elif ext == 'obj': bpy.ops.wm.obj_import(filepath=p)
            elif ext == 'dae': bpy.ops.wm.collada_import(filepath=p)
            else: bpy.ops.import_scene.gltf(filepath=p)
            obs = [o for o in bpy.data.objects if o.type == 'MESH']
            bpy.context.view_layer.update()
            d = obs[0].dimensions
            imgs = [i.filepath for i in bpy.data.images if i.source == 'FILE' or i.packed_file]
            ok_img = [os.path.exists(bpy.path.abspath(i.filepath)) or bool(i.packed_file) for i in bpy.data.images if i.type == 'IMAGE']
            res.append(f'{rel.split("/")[-1]}.{ext}: {d.x:.4f} x {d.y:.4f} x {d.z:.4f} (единицы сцены = м), mats={[m.name for m in obs[0].data.materials]}, images_ok={ok_img}')
        except Exception as e:
            res.append(f'{rel}.{ext}: ОШИБКА {e!r}'[:300])
open('out/verify.txt', 'w', encoding='utf-8').write('\n'.join(res) + '\n')
print('\n'.join(res))
