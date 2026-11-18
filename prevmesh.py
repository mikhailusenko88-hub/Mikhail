# предпросмотр сетки с пяти сторон (pyrender + OSMesa): глина, мягкий свет
import os, sys, glob, math, numpy as np, trimesh
os.environ.setdefault('PYOPENGL_PLATFORM', 'osmesa')
import pyrender
from PIL import Image
def look(eye, tgt):
    f = tgt - eye; f /= np.linalg.norm(f); r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    M = np.eye(4); M[:3, 0] = r; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = eye; return M
for f in sorted(glob.glob('out/*.glb')):
    sc = trimesh.load(f, force='mesh'); m = sc if isinstance(sc, trimesh.Trimesh) else sc.dump(concatenate=True)
    c = m.bounds.mean(0); R = np.linalg.norm(m.extents) * 0.55
    mat = pyrender.MetallicRoughnessMaterial(baseColorFactor=[0.8, 0.72, 0.62, 1], metallicFactor=0, roughnessFactor=0.7)
    ims = []
    for yaw in (0, 35, -35, 90, 180):
        s = pyrender.Scene(ambient_light=[0.35, 0.35, 0.35], bg_color=[0.85, 0.9, 0.95, 1]); s.add(pyrender.Mesh.from_trimesh(m, material=mat, smooth=True))
        a = math.radians(yaw); eye = c + np.array([math.sin(a), 0.15, math.cos(a)]) * R * 2.3
        s.add(pyrender.PerspectiveCamera(yfov=math.radians(30)), pose=look(eye, c))
        s.add(pyrender.DirectionalLight(intensity=3.0), pose=look(c + np.array([-1, 1.5, 2]) * R, c))
        s.add(pyrender.DirectionalLight(intensity=1.2), pose=look(c + np.array([1.5, 0.5, -1]) * R, c))
        rr = pyrender.OffscreenRenderer(400, 400); col, _ = rr.render(s); rr.delete(); ims.append(Image.fromarray(col))
    S = Image.new('RGB', (2000, 400)); [S.paste(im, (i * 400, 0)) for i, im in enumerate(ims)]; S.save(f[:-4] + '_krug.jpg', quality=88); print('ок', f)
