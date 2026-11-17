# «Тюль»: мелкая мягкая сетка с моего героя натягивается на героя с обложки (плотный оптический поток).
# Где сетка растягивается/сжимается и куда ползёт — там у меня ошибка пропорций.
# python3 setka.py <обложка.jpg> <x0,y0,x1,y1 рамка на обложке> <мой.jpg> "<3 точки на обложке>" "<3 точки у меня>" <выход.jpg> [шаг сетки, px обложки]
import sys, json, numpy as np, cv2
cov_path, box, mine_path, pc, pm, out = sys.argv[1:7]; step = float(sys.argv[7]) if len(sys.argv) > 7 else 3
x0, y0, x1, y1 = map(int, box.split(','))
P = lambda s: np.array([[float(v) for v in q.split(',')] for q in s.split(';')], np.float32)
pc, pm = P(pc), P(pm)
cov = cv2.imread(cov_path)[y0:y1, x0:x1]; K = 4                      # работаем в 4× увеличении обложки
cov = cv2.resize(cov, None, fx=K, fy=K, interpolation=cv2.INTER_CUBIC); H, W = cov.shape[:2]
mine = cv2.imread(mine_path)
A = cv2.getAffineTransform(pm, (pc - np.array([x0, y0], np.float32)) * K)     # мои 3 точки -> те же на обложке
warp = cv2.warpAffine(mine, A, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
def feat(img):   # «рисунок» без меха и света: края и тёмные/светлые пятна
    g = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32); g = cv2.GaussianBlur(g, (0, 0), 6)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1); e = np.sqrt(gx * gx + gy * gy)
    e = e / (np.percentile(e, 99) + 1e-6); f = 0.6 * np.clip(e, 0, 1) + 0.4 * (g / 255.0)
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)
fa, fb = feat(warp), feat(cov)
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST); dis.setFinestScale(0); dis.setPatchSize(24); dis.setPatchStride(4)
dis.setGradientDescentIterations(60); dis.setVariationalRefinementAlpha(40.0); dis.setVariationalRefinementIterations(10)
flow = dis.calc(fa, fb, None)                                          # куда сдвинуть мою точку, чтобы попасть в обложку
flow = cv2.GaussianBlur(flow, (0, 0), 10)                              # «мягкая» тюль
vis = cv2.addWeighted(cov, 0.55, warp, 0.45, 0)
s = int(step * K); mag = np.linalg.norm(flow, axis=-1); mmax = np.percentile(mag, 98) + 1e-6
def col(m): t = min(1.0, m / mmax); return (int(255 * (1 - t)), int(200 * (1 - abs(t - .5) * 2)), int(255 * t))
for y in range(0, H, s):                                                # горизонтальные нити
    pts = [(x + flow[y, x, 0], y + flow[y, x, 1]) for x in range(0, W, 2)]
    for (ax, ay), (bx, by), x in zip(pts[:-1], pts[1:], range(0, W, 2)): cv2.line(vis, (int(ax), int(ay)), (int(bx), int(by)), col(mag[y, x]), 1, cv2.LINE_AA)
for x in range(0, W, s):                                                # вертикальные нити
    pts = [(x + flow[y, x, 0], y + flow[y, x, 1]) for y in range(0, H, 2)]
    for (ax, ay), (bx, by), y in zip(pts[:-1], pts[1:], range(0, H, 2)): cv2.line(vis, (int(ax), int(ay)), (int(bx), int(by)), col(mag[y, x]), 1, cv2.LINE_AA)
for y in range(s * 4, H, s * 8):                                        # редкие стрелки: куда двигать
    for x in range(s * 4, W, s * 8):
        dx, dy = flow[y, x]
        if abs(dx) + abs(dy) > 3 * K: cv2.arrowedLine(vis, (x, y), (int(x + dx), int(y + dy)), (0, 0, 255), 2, cv2.LINE_AA, tipLength=.3)
side = np.concatenate([cv2.resize(cov, (W // 2, H // 2)), cv2.resize(warp, (W // 2, H // 2))], 0)
cv2.imwrite(out, np.concatenate([vis, cv2.resize(side, (side.shape[1] * H // side.shape[0], H))], 1), [cv2.IMWRITE_JPEG_QUALITY, 88])
# сводка по меткам: куда «просит» сдвинуть каждую из моих 3 точек (в px обложки)
mp = (cv2.transform(pm[None], A)[0]).astype(int)
print(json.dumps({n: [round(float(flow[min(H - 1, max(0, p[1])), min(W - 1, max(0, p[0]))][k]) / K, 1) for k in (0, 1)] for n, p in zip(['глаз ближний', 'глаз дальний', 'нос'], mp)}, ensure_ascii=False))
