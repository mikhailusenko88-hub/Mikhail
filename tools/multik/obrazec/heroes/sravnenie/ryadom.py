# обложка и мой герой рядом в одном масштабе и с тем же наклоном (по линии глаз и ширине головы)
import sys, json, math, numpy as np, cv2
obl, key, mine, mk, view, out = sys.argv[1:7]
M = json.load(open(obl))[key]; img = cv2.imread(M['img'] if M['img'].startswith('/') else '/home/claude/out/geroi/' + M['img'])
eL, eR = np.array(M['eyes'][0]['c'], float), np.array(M['eyes'][1]['c'], float); c = (eL + eR) / 2; ang = math.degrees(math.atan2(eR[1] - eL[1], eR[0] - eL[0]))
hl, hr = np.array(M['head'][0], float), np.array(M['head'][1], float); W = np.linalg.norm(hr - hl)
S = 300.0 / W; R = cv2.getRotationMatrix2D(tuple(c), ang, S); R[:, 2] += np.array([300, 330]) - c
A = cv2.warpAffine(img, R, (600, 600), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
mk = json.load(open(mk))[view]; me = cv2.imread(mine); L = cv2.imread(mine.replace('.jpg', '_0_lbl.png'), cv2.IMREAD_UNCHANGED)
a, b = np.array(mk['eyes'][0], float), np.array(mk['eyes'][1], float); cm = (a + b) / 2
ys, xs = np.nonzero(np.isin(L, (1, 2, 3, 5)) & (np.abs(np.arange(L.shape[0])[:, None] - cm[1]) < 2)); Wm = xs.max() - xs.min()
Sm = 300.0 / Wm; R2 = cv2.getRotationMatrix2D(tuple(cm), 0, Sm); R2[:, 2] += np.array([300, 330]) - cm
B = cv2.warpAffine(me, R2, (600, 600), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
for im in (A, B):
    for y in (330,): cv2.line(im, (0, y), (600, y), (0, 200, 255), 1)
    for x in (150, 300, 450): cv2.line(im, (x, 0), (x, 600), (0, 200, 255), 1)
cv2.imwrite(out, np.concatenate([A, B, cv2.addWeighted(A, 0.5, B, 0.5, 0)], 1))
