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
print('модель загружена за %.0f с' % (time.time() - t0), flush=True)
rem = BackgroundRemover(); os.makedirs('out', exist_ok=True)
for f in sorted(glob.glob('in/*.png')):
    name = os.path.basename(f)[:-4]; t1 = time.time()
    img = Image.open(f).convert('RGB'); img = rem(img); img.save('out/%s_mask.png' % name)
    mesh = pipe(image=img, num_inference_steps=int(os.environ.get('STEPS', 5)), octree_resolution=int(os.environ.get('OCT', 256)), num_chunks=8000,
                generator=torch.manual_seed(1234), output_type='trimesh')[0]
    mesh = FloaterRemover()(mesh); mesh = DegenerateFaceRemover()(mesh); mesh = FaceReducer()(mesh, max_facenum=60000)
    mesh.export('out/%s_h3d.glb' % name); mesh.export('out/%s_h3d.ply' % name)
    print('%s: %d вершин, %.0f с' % (name, len(mesh.vertices), time.time() - t1), flush=True)
