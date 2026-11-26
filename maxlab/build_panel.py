"""Файл 3ds Max с панелью «Наш декор»: основа — настоящий файл Max 2012 (одна Editable Mesh), подменяется геометрия.
Запуск: python3 build_panel.py A907 2700 out.max"""
import json, struct, sys, math
import maxfile as mx

art, L, outp = sys.argv[1], float(sys.argv[2]), sys.argv[3]
code = art.replace(' ', '').replace('/', '-')
prof = json.load(open('profiles_site.json'))[art]
W = max(p[0] for p in prof)
# замкнутый контур (x, y): лицевая линия слева направо, затем тыл y=0 справа налево
poly = [(float(x), float(y)) for x, y in prof] + [(W, 0.0), (0.0, 0.0)]
# убрать повторы
P = []
for p in poly:
    if not P or (abs(P[-1][0]-p[0]) > 1e-6 or abs(P[-1][1]-p[1]) > 1e-6):
        P.append(p)
if abs(P[0][0]-P[-1][0]) < 1e-6 and abs(P[0][1]-P[-1][1]) < 1e-6:
    P.pop()
n = len(P)
area = sum(P[i][0]*P[(i+1) % n][1] - P[(i+1) % n][0]*P[i][1] for i in range(n)) / 2
if area < 0:                       # нужен обход против часовой
    P.reverse()
nface = len(prof)                  # первые точки — лицевая линия (до разворота): для групп сглаживания — по нормали

def ear_clip(pts):
    idx = list(range(len(pts)))
    tris = []
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    def inside(p, a, b, c):
        d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
        return d1 >= 0 and d2 >= 0 and d3 >= 0
    guard = 0
    while len(idx) > 3 and guard < 100000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k-1], idx[k], idx[(k+1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            raise SystemExit('триангуляция не сошлась')
    tris.append(tuple(idx))
    return tris

caps = ear_clip(P)
# вершины: стена в плоскости XZ, панель растёт к зрителю (−Y), длина по Z
verts = [(x, -y, 0.0) for x, y in P] + [(x, -y, L) for x, y in P]
faces = []      # (a, b, c, smooth, flags)
def edgevis(a, b, c):
    return 0
for i in range(n):
    j = (i + 1) % n
    a, b, c, d = i, j, n + j, n + i
    (x0, y0), (x1, y1) = P[i], P[j]
    back = abs(y0) < 1e-6 and abs(y1) < 1e-6
    side = abs(x0 - x1) < 1e-6
    sm = 0 if (back or side) else 1
    faces.append((a, b, c, sm, 0b011))
    faces.append((a, c, d, sm, 0b110))
for (a, b, c) in caps:            # торцы: низ смотрит вниз (обход обратный), верх — вверх
    def vis(u, v):
        return 1 if (abs(u - v) == 1 or abs(u - v) == n - 1) else 0
    faces.append((a, c, b, 0, vis(a, c) | vis(c, b) << 1 | vis(b, a) << 2))
    faces.append((n + a, n + b, n + c, 0, vis(a, b) | vis(b, c) << 1 | vis(c, a) << 2))
# ориентация: объём со знаком должен быть > 0 (нормали наружу); иначе развернуть все грани
def vol(fs):
    t = 0.0
    for a, b, c, _, _ in fs:
        A, B, C = verts[a], verts[b], verts[c]
        t += (A[0]*(B[1]*C[2]-B[2]*C[1]) - A[1]*(B[0]*C[2]-B[2]*C[0]) + A[2]*(B[0]*C[1]-B[1]*C[0])) / 6
    return t
bad = 0
if vol(faces) < 0:
    faces = [(a, c, b, sm, ((fl >> 2) & 1) | (fl & 2) | ((fl & 1) << 2)) for a, b, c, sm, fl in faces]
print('объём, см³:', round(vol(faces) / 1000, 1), '(площадь сечения × длина:', round(abs(area) * L / 1000, 1), ')')
print('контур', n, 'вершин', len(verts), 'граней', len(faces))

ents = mx.read_cfb(open('boxes.max', 'rb').read())
st = mx.streams(ents)
scene = mx.parse(st['Scene'])
root = scene[0]
em, node = root.children[388], root.children[390]
m = em.find(0x08FE)
m.find(0x0914).data = struct.pack('<I', len(verts)) + b''.join(struct.pack('<3f', *v) for v in verts)
m.find(0x0912).data = struct.pack('<I', len(faces)) + b''.join(struct.pack('<IIIIHH', a, b, c, sm, fl, 0) for a, b, c, sm, fl in faces)
# UV: развёртка «коробкой» — x и z в метрах (для текстуры белого цвета вид не важен)
tv = [(v[0]/1000.0, v[2]/1000.0, 0.0) for v in verts]
m.find(0x2394).data = struct.pack('<I', len(tv)) + b''.join(struct.pack('<3f', *t) for t in tv)
m.find(0x2396).data = struct.pack('<I', len(faces)) + b''.join(struct.pack('<III', a, b, c) for a, b, c, _, _ in faces)
node_name = f"NashDekor_{code}"
node.find(0x0962).data = node_name.encode('utf-16le')
name9 = f"{code.replace('-', '')}-{int(L)}"[:9].ljust(9)     # в сводке файла место ровно на 9 знаков
TEX = 'nd_white_1.jpg'                      # 14 знаков — как прежнее имя текстуры
for idx in (360, 371):
    nm = root.children[idx].find(0x4000).find(0x4001)
    nm.data = TEX.encode('utf-16le')
# единицы сцены: объект Scene, чанк 0x8520 = (тип системной единицы, масштаб); 3 = миллиметры, 1 ед. = 1 мм.
# 0x8500 — вид отображения (1 = метрический), 0x8530 — 0 (мм). Образцы: (0 = дюймы, 1.0) и вид 2 (US).
sc_obj = next(c for c in root.children if c.container and c.find(0x8520))
sc_obj.find(0x8520).data = struct.pack('<if', 3, 1.0)
sc_obj.find(0x8500).data = struct.pack('<i', 1)
sc_obj.find(0x8530).data = struct.pack('<i', 0)
new = {'Scene': mx.dump(scene)}
# путь к текстуре — рядом с файлом
fa = st['FileAssetMetaData2']
guid, tl = fa[:16], struct.unpack_from('<I', fa, 16)[0]
typ = fa[20:20 + tl*2]
new['FileAssetMetaData2'] = guid + struct.pack('<I', tl) + typ + b'\0\0' + struct.pack('<I', len(TEX)) + TEX.encode('utf-16le') + b'\0\0'
def same(s, a, b):
    assert len(a) == len(b), (a, b)
    return s.replace(a.encode('utf-16le'), b.encode('utf-16le'))
ds = st['\x05DocumentSummaryInformation']
for a, b in (('Omega', 'Dekor'), ('OMEGA-DATOR', 'NASHDEKOR-1'), ('Tex_0033_1.dds', TEX), ('Mesh_0033', name9),
             ('Vertices: 994', ('Vertices: %d' % len(verts)).ljust(13)), ('Faces: 390', ('Faces: %d' % len(faces)).ljust(10))):
    ds = same(ds, a, b)
new['\x05DocumentSummaryInformation'] = ds
si = bytearray(same(st['\x05SummaryInformation'], 'Omega', 'Dekor'))
k = si.find(b'(\x00\x00\x00\x80\x00\x00\x00<\x00\x00\x00')
if k > 0:                                   # миниатюра 128×60: светло-серый фон и силуэт панели
    off, w, h = k + 40, 128, 60
    row = (w * 3 + 3) & ~3
    for yy in range(h):
        for xx in range(w):
            inside = 44 <= xx <= 84 and 6 <= yy <= 54
            stripe = inside and ((xx - 44) % 8 in (0, 1))
            col = (120, 120, 120) if stripe else ((235, 235, 235) if inside else (180, 180, 180))
            p = off + yy * row + xx * 3
            si[p:p+3] = bytes(col)
new['\x05SummaryInformation'] = bytes(si)
# Config: имя пользователя и компьютера в заметке о сохранении (XOR 0x9D)
cfg = mx.parse(st['Config'])
def xs(s):
    return bytes(ch ^ 0x9D for ch in (s + '\0').encode('latin1'))
raw = mx.dump(cfg)
for a, b in (('Omega', 'Dekor'), ('OMEGA-DATOR', 'NASHDEKOR-1')):
    raw = raw.replace(xs(a), xs(b))
new['Config'] = raw
open(outp, 'wb').write(mx.write_cfb(ents, new))
obj = outp[:-4] + '.obj'
with open(obj, 'w') as f:
    f.write(f"# Наш декор — {art}, {int(W)}x{int(round(max(p[1] for p in P)))}x{int(L)} мм, единицы — мм\nmtllib {obj.split('/')[-1][:-4]}.mtl\no {node_name}\n")
    for v in verts: f.write("v %.4f %.4f %.4f\n" % v)
    for t in tv: f.write("vt %.5f %.5f\n" % t[:2])
    f.write("usemtl NashDekor_white\ns 1\n")
    for a, b, c, _, _ in faces: f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")
open(outp[:-4] + '.mtl', 'w').write("newmtl NashDekor_white\nKd 0.965 0.965 0.957\nKa 0 0 0\nKs 0.04 0.04 0.04\nNs 20\nmap_Kd nd_white_1.jpg\n")
print('готово', outp, obj)
