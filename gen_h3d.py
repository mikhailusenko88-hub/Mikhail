# Hunyuan3D-2mini (Tencent, открытая): картинка -> 3D-форма. На процессоре машины GitHub, без видеокарты.
import sys, os, time, glob, torch
from PIL import Image
from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline, FloaterRemover, DegenerateFaceRemover, FaceReducer
torch.set_num_threads(os.cpu_count())
t0 = time.time()
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2mini', subfolder='hunyuan3d-dit-v2-mini-turbo', use_safetensors=True, device='cpu', dtype=torch.float32)
try: pipe.enable_flashvdm(mc_algo='mc')
except Exception as e: print('flashvdm нет:', e)
def all_float():
    for k_, v_ in list(vars(pipe).items()):
        if isinstance(v_, torch.nn.Module):
            v_.float(); print('  %s -> float32' % k_, flush=True)
    try: pipe.dtype = torch.float32
    except Exception: pass
all_float()
print('модель загружена за %.0f с' % (time.time() - t0), flush=True)
rem = BackgroundRemover(); os.makedirs('out', exist_ok=True)
for f in sorted(glob.glob('in/*.png')):
    name = os.path.basename(f)[:-4]; t1 = time.time()
    img = Image.open(f).convert('RGB'); img = rem(img); img.save('out/%s_mask.png' % name)
    all_float()
    with torch.autocast('cpu', enabled=False):
      mesh = pipe(image=img, num_inference_steps=int(os.environ.get('STEPS', 5)), octree_resolution=int(os.environ.get('OCT', 256)), num_chunks=8000,
                  generator=torch.manual_seed(1234), output_type='trimesh')[0]
    mesh.export('out/%s_h3d_raw.ply' % name)
    try:
        parts = mesh.split(only_watertight=False); mesh = max(parts, key=lambda m: len(m.faces))   # самая большая часть, без «мусора»
    except Exception as e: print('split:', e)
    try:
        import fast_simplification
        if len(mesh.faces) > 80000:
            v, f_ = fast_simplification.simplify(mesh.vertices, mesh.faces, target_reduction=1 - 80000 / len(mesh.faces)); import trimesh; mesh = trimesh.Trimesh(v, f_)
    except Exception as e: print('simplify:', e)
    mesh.export('out/%s_h3d.glb' % name); mesh.export('out/%s_h3d.ply' % name)
    print('%s: %d вершин, %.0f с' % (name, len(mesh.vertices), time.time() - t1), flush=True)
