# разметка героя на картинке: рисует эллипсы глаз, радужки, нос, губу, контур головы, уши — для проверки «на просвет»
# python3 show.py <картинка> <метки.json> <ключ> <выход.jpg> [x0,y0,x1,y1] [масштаб]
import sys, json, cv2, numpy as np
img_p, js, key, out = sys.argv[1:5]; box = list(map(int, sys.argv[5].split(','))) if len(sys.argv) > 5 else None; K = float(sys.argv[6]) if len(sys.argv) > 6 else 3
M = json.load(open(js))[key]; im = cv2.imread(img_p)
if box: im = im[box[1]:box[3], box[0]:box[2]]; off = np.array(box[:2], float)
else: off = np.zeros(2)
im = cv2.resize(im, None, fx=K, fy=K, interpolation=cv2.INTER_CUBIC)
P = lambda p: tuple(int(round(v)) for v in (np.array(p, float) - off) * K)
for e in M.get('eyes', []):
    cv2.ellipse(im, P(e['c']), (int(e['w'] / 2 * K), int(e['h'] / 2 * K)), e.get('rot', 0), 0, 360, (0, 255, 255), 1, cv2.LINE_AA)
    if 'iris' in e: cv2.circle(im, P(e['iris'][:2]), int(e['iris'][2] * K), (255, 0, 255), 1, cv2.LINE_AA)
for k, col in (('nose', (0, 0, 255)), ('lip', (255, 0, 0))):
    if k in M: cv2.drawMarker(im, P(M[k]), col, cv2.MARKER_CROSS, 14, 2)
for p in M.get('head', []): cv2.circle(im, P(p), 5, (0, 255, 0), 2)
for e in M.get('ears', []): cv2.line(im, P(e[0]), P(e[1]), (255, 255, 0), 2)
cv2.imwrite(out, im)
