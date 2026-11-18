# «Картинка → 3D» (менеджер, 18.11.2026): Hunyuan3D-2mini на процессоре машины GitHub.
# Вход — in/<IMG>.png (RGBA из prep.py: голова без чужого, маска жёсткая), выход — out/<IMG>_s<SEED>.ply/.glb и _raw.ply.
# Отличия от geroi3d: обычная модель (не turbo), 30 шагов, сетка 256, своё зерно на машину; фон не вырезается заново.
import os, time, json, torch
from PIL import Image
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
torch.set_num_threads(os.cpu_count())
IMG, SEED = os.environ['IMG'], int(os.environ.get('SEED', 1))
SUB = os.environ.get('MODEL', 'hunyuan3d-dit-v2-mini'); STEPS = int(os.environ.get('STEPS', 30)); OCT = int(os.environ.get('OCT', 256))
t0 = time.time()
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2mini', subfolder=SUB, use_safetensors=True, device='cpu', dtype=torch.float32)
for k_, v_ in list(vars(pipe).items()):
    if isinstance(v_, torch.nn.Module): v_.float()
try: pipe.dtype = torch.float32
except Exception: pass
print('модель %s загружена за %.0f с' % (SUB, time.time() - t0), flush=True)
os.makedirs('out', exist_ok=True)
img = Image.open(f'in/{IMG}.png').convert('RGBA')
t1 = time.time()
with torch.autocast('cpu', enabled=False):
    mesh = pipe(image=img, num_inference_steps=STEPS, octree_resolution=OCT, num_chunks=20000,
                generator=torch.manual_seed(SEED), output_type='trimesh')[0]
tag = f'{IMG}_s{SEED}'
if mesh is None: raise SystemExit(f'{tag}: поверхность не найдена')
mesh.export(f'out/{tag}_raw.ply')
parts = mesh.split(only_watertight=False); mesh = max(parts, key=lambda m: len(m.faces))
if len(mesh.faces) > 150000:
    import fast_simplification, trimesh
    v, f_ = fast_simplification.simplify(mesh.vertices, mesh.faces, target_reduction=1 - 150000 / len(mesh.faces)); mesh = trimesh.Trimesh(v, f_)
mesh.export(f'out/{tag}.ply'); mesh.export(f'out/{tag}.glb')
info = {'img': IMG, 'seed': SEED, 'model': SUB, 'steps': STEPS, 'oct': OCT, 'verts': len(mesh.vertices), 'faces': len(mesh.faces),
        'parts': len(parts), 'sec': round(time.time() - t1)}
json.dump(info, open(f'out/{tag}.json', 'w'), ensure_ascii=False); print(info, flush=True)
