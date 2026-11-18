# «Blender-учитель»: маленькая сеть учится превращать кадр движка в кадр Blender. Учится только на месте и вещах (тела героев в Blender без шерсти — маска).
import numpy as np, torch, torch.nn as nn, json, glob, os, sys, time
from PIL import Image
torch.set_num_threads(os.cpu_count()); torch.manual_seed(0); np.random.seed(0)
TR = [int(x) for x in sys.argv[1].split(',')]; TE = [int(x) for x in sys.argv[2].split(',')]; W, H = 640, 360
def load(t):
    X = np.asarray(Image.open(f'ours/r{t}_nash.png').convert('RGB').resize((W, H), Image.LANCZOS), np.float32) / 255
    Y = np.asarray(Image.open(f'out/r{t}.png').convert('RGB').resize((W, H), Image.LANCZOS), np.float32) / 255
    mf = sorted(glob.glob(f'out/r{t}_mask*.png')); M = np.asarray(Image.open(mf[0]).convert('L').resize((W, H)), np.float32) / 255 if mf else np.zeros((H, W), np.float32)
    from PIL import ImageFilter
    Mi = Image.fromarray((M > .3).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9)); keep = 1 - np.asarray(Mi, np.float32) / 255   # героев с запасом — вон
    return X, Y, keep
def coords(): yy, xx = np.mgrid[0:H, 0:W].astype(np.float32); return np.stack([xx / W * 2 - 1, yy / H * 2 - 1])
C2 = coords()
def tens(X): return torch.from_numpy(np.concatenate([X.transpose(2, 0, 1), C2]))[None]
class Net(nn.Module):   # мелкая: можно перенести в шейдер движка (4 свёртки 3×3, 16 каналов, половинный размер)
    def __init__(s, c=16):
        super().__init__(); s.a = nn.Sequential(nn.Conv2d(5, c, 3, padding=1), nn.ReLU(), nn.Conv2d(c, c, 3, padding=2, dilation=2), nn.ReLU(), nn.Conv2d(c, c, 3, padding=4, dilation=4), nn.ReLU(), nn.Conv2d(c, c, 3, padding=8, dilation=8), nn.ReLU(), nn.Conv2d(c, 3, 1))
    def forward(s, x): h = nn.functional.avg_pool2d(x, 2); r = s.a(h); r = nn.functional.interpolate(r, scale_factor=2, mode='bilinear', align_corners=False); return (x[:, :3] + .5 * torch.tanh(r)).clamp(0, 1)
D = {t: load(t) for t in TR + TE}; net = Net(); opt = torch.optim.Adam(net.parameters(), 3e-3); t0 = time.time()
XT = torch.cat([tens(D[t][0]) for t in TR]); YT = torch.cat([torch.from_numpy(D[t][1].transpose(2, 0, 1))[None] for t in TR]); KT = torch.cat([torch.from_numpy(D[t][2])[None, None] for t in TR])
for it in range(1500):
    i = np.random.randint(len(TR), size=4); y0 = np.random.randint(0, H - 192); x0 = np.random.randint(0, W - 256)
    x = XT[i, :, y0:y0 + 192, x0:x0 + 256]; y = YT[i, :, y0:y0 + 192, x0:x0 + 256]; k = KT[i, :, y0:y0 + 192, x0:x0 + 256]
    loss = ((net(x) - y).abs() * k).sum() / (k.sum() * 3 + 1); opt.zero_grad(); loss.backward(); opt.step()
    if it == 1000:
        for g in opt.param_groups: g['lr'] = 1e-3
    if it % 250 == 0: print('шаг', it, 'ошибка', round(loss.item(), 4), round(time.time() - t0), 'с', flush=True)
os.makedirs('out/net', exist_ok=True); rep = {}
with torch.no_grad():
    for t in TR + TE:
        X, Y, K = D[t]; P = net(tens(X))[0].numpy().transpose(1, 2, 0)
        e0 = float((np.abs(X - Y).mean(2) * K).sum() / K.sum()); e1 = float((np.abs(P - Y).mean(2) * K).sum() / K.sum())
        rep[t] = {'учебный' if t in TR else 'проверка': 1, 'ошибка_было': round(e0 * 255, 2), 'ошибка_сеть': round(e1 * 255, 2)}
        row = np.concatenate([X, P, Y], 1); Image.fromarray((row * 255).astype(np.uint8)).save(f'out/net/r{t}_bylo_set_blender.jpg', quality=90)
torch.save(net.state_dict(), 'out/net/net.pt'); json.dump({k: [v.tolist() for v in net.state_dict().values()] for k in ['w']} if False else {n: p.tolist() for n, p in net.state_dict().items()}, open('out/net/weights.json', 'w'))
json.dump(rep, open('out/net/itog.json', 'w'), ensure_ascii=False, indent=1); print(json.dumps(rep, ensure_ascii=False), flush=True)
