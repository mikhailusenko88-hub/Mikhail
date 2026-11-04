"""Генератор трасс из блоков и запуск физики.

Мир: x 0..1000 (между стенками), y вниз. Шарик r=22.
Каждый этап = старт в кольцах + случайные блоки + финиш.
"""
import math
import os
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R_BALL = 22.0
G = 1200.0
FPS = 30

# kind: 0 стенка, 1 колышек, 2 кольцо, 3 бампер, 4 лопасть/люк, 5 рампа
KIND_E = {0: 0.35, 1: 0.45, 2: 0.4, 3: 1.0, 4: 0.35, 5: 0.25}
KIND_MU = {0: 0.03, 1: 0.03, 2: 0.08, 3: 0.0, 4: 0.06, 5: 0.02}


class Body:
    def __init__(self, px, py, look="static", **kw):
        self.px, self.py = px, py
        self.a0 = kw.get("a0", 0.0)
        self.w = kw.get("w", 0.0)
        self.amp = kw.get("amp", 0.0)
        self.k = kw.get("k", 0.0)
        self.P = kw.get("P", 0.0)
        self.ph = kw.get("ph", 0.0)
        self.bias = kw.get("bias", 0.0)
        self.ox = kw.get("ox", 0.0)
        self.oy = kw.get("oy", 0.0)
        self.k2 = kw.get("k2", 0.0)
        self.P2 = kw.get("P2", 0.0)
        self.ph2 = kw.get("ph2", 0.0)
        self.ton = kw.get("ton", -1.0)
        self.toff = kw.get("toff", 1e9)
        self.hp = kw.get("hp", -1)
        self.look = look          # static / ring / spinner / flap
        self.color = kw.get("color", None)
        self.segs = []            # (ax, ay, bx, by, rad, kind) в локальных координатах
        self.ring_r = kw.get("ring_r", 0)
        self.ring_idx = kw.get("ring_idx", 0)

    @property
    def dynamic(self):
        return self.w != 0 or self.P > 0 or self.P2 > 0

    def angle(self, t):
        th = self.a0 + self.w * t
        if self.P > 0:
            s = math.sin(2 * math.pi * t / self.P + self.ph) - self.bias
            if self.k > 0:
                s = max(-1.0, min(1.0, s * self.k))
            th += self.amp * s
        return th

    def offset(self, t):
        if self.P2 <= 0:
            return self.px, self.py
        s = math.sin(2 * math.pi * t / self.P2 + self.ph2)
        if self.k2 > 0:
            s = max(-1.0, min(1.0, s * self.k2))
        return self.px + self.ox * s, self.py + self.oy * s


class Track:
    def __init__(self, rng):
        self.rng = rng
        self.bodies = [Body(0, 0)]   # тело 0 — вся статика
        self.static = self.bodies[0]
        self.deco = []               # подписи блоков (для отладки)
        self.spawn = []
        self.finish_y = None
        self.ring_center = None
        self.modules = []

    def add_body(self, b):
        self.bodies.append(b)
        return b

    def seg(self, ax, ay, bx, by, rad=8, kind=0, body=None):
        (body or self.static).segs.append((ax, ay, bx, by, rad, kind))

    def poly(self, pts, rad=8, kind=0, body=None):
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            self.seg(ax, ay, bx, by, rad, kind, body)

    def peg(self, x, y, rad=8, kind=1, body=None):
        self.seg(x, y, x, y, rad, kind, body)

    # ---- запись для phys ----
    def write_input(self, path, balls, qual, tmax, after, frames, events, seed):
        lines = [f"G {G}", f"SEED {seed}", f"BALLS {len(balls)} {R_BALL}"]
        for x, y, vx, vy in balls:
            lines.append(f"{x:.3f} {y:.3f} {vx:.3f} {vy:.3f}")
        lines.append(f"BODIES {len(self.bodies)}")
        for b in self.bodies:
            lines.append(" ".join(f"{v:.6f}" for v in (b.px, b.py, b.a0, b.w, b.amp, b.k, b.P, b.ph, b.bias, b.ox, b.oy,
                                                        b.k2, b.P2, b.ph2, b.ton, b.toff)) + f" {b.hp}")
        segs = []
        for i, b in enumerate(self.bodies):
            for (ax, ay, bx, by, rad, kind) in b.segs:
                e = KIND_E[kind]
                mu = KIND_MU[kind]
                segs.append(f"{i} {ax:.3f} {ay:.3f} {bx:.3f} {by:.3f} {rad:.2f} {e:.3f} {mu:.3f} {kind}")
        lines.append(f"SEGS {len(segs)}")
        lines += segs
        lines.append(f"FINISH {self.finish_y:.2f} {qual} {tmax:.1f} {after:.2f}")
        lines.append(f"OUT {frames} {events}")
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")


# ===================== блоки =====================

def walls_and_ceiling(T, y_top, y_bot):
    T.seg(0, y_top, 0, y_bot, 9, 0)
    T.seg(1000, y_top, 1000, y_bot, 9, 0)
    T.seg(0, y_top, 1000, y_top, 9, 0)


def funnel(T, y, gap=190, h=270):
    T.poly([(0, y), (500 - gap / 2, y + h)], 9, 0)
    T.poly([(1000, y), (500 + gap / 2, y + h)], 9, 0)
    return y + h + 50


def m_ring_start(T, y, nb):
    rng = T.rng
    cx, cy = 500.0, y + 430.0
    T.ring_center = (cx, cy)
    radii = [190.0, 275.0, 360.0]
    gaps = [math.radians(g) for g in (32, 28, 25)]
    base_w = [0.95, -0.8, 0.62]
    sgn = rng.choice([-1, 1])
    xs = [3, 10, 20, 32]
    hps = [int(round(float(np.interp(nb, xs, v)))) for v in ([5, 13, 20, 22], [4, 10, 16, 20], [3, 8, 11, 14])]
    toffs = [5.6 + rng.uniform(-0.4, 0.6), 9.6 + rng.uniform(-0.5, 0.7), 13.2 + rng.uniform(-0.5, 0.8)]
    for i, (R, gap) in enumerate(zip(radii, gaps)):
        w = base_w[i] * sgn * rng.uniform(0.85, 1.2)
        b = T.add_body(Body(cx, cy, "ring", a0=rng.uniform(0, 2 * math.pi), w=w, hp=hps[i], toff=toffs[i], ring_r=R, ring_idx=i))
        n = max(12, int(math.ceil((2 * math.pi - gap) / math.radians(5))))
        a_from = gap / 2
        a_to = 2 * math.pi - gap / 2
        pts = [(R * math.cos(a_from + (a_to - a_from) * j / n), R * math.sin(a_from + (a_to - a_from) * j / n))
               for j in range(n + 1)]
        T.poly(pts, 8, 2, b)
    # старт: шарики в гексагональной решётке внутри малого кольца
    cand = []
    lim = radii[0] - 8 - R_BALL - 6
    step = 2 * R_BALL + 3
    for iy in range(-6, 7):
        for ix in range(-6, 7):
            px = ix * step + (iy % 2) * step / 2
            py = iy * step * 0.866
            if px * px + py * py <= lim * lim:
                cand.append((cx + px, cy + py))
    rng.shuffle(cand)
    for (px, py) in cand[:nb]:
        a = rng.uniform(0, 2 * math.pi)
        sp = rng.uniform(250, 480)
        T.spawn.append((px, py, sp * math.cos(a), sp * math.sin(a)))
    return funnel(T, cy + 330)


def m_pegs(T, y, nb=0):
    rng = T.rng
    rows = rng.randint(7, 10)
    dx, dy = 96.0, 74.0
    bump = set(rng.sample(range(rows * 9), rng.randint(0, 4)))
    k = 0
    for r in range(rows):
        off = 48.0 if r % 2 else 0.0
        x = 104.0 + off
        while x <= 900:
            yy = y + 40 + r * dy
            if k in bump and 150 < x < 850:
                T.peg(x, yy, 18, 3)
            else:
                T.peg(x, yy, 8, 1)
            k += 1
            x += dx
    T.modules.append(("pegs", y))
    return y + 40 + rows * dy + 50


def m_zigzag(T, y, nb=0):
    rng = T.rng
    n = rng.randint(4, 6)
    ang = math.radians(rng.uniform(12.5, 16.5))
    t = math.tan(ang)
    L = 820.0
    yy = y + 20
    for i in range(n):
        if i % 2 == 0:
            T.seg(0, yy, L, yy + L * t, 9, 5)
            if rng.random() < 0.5:
                bx = rng.uniform(250, 650)
                T.peg(bx, yy + bx * t - 9, 7, 1)
        else:
            T.seg(1000, yy, 1000 - L, yy + L * t, 9, 5)
            if rng.random() < 0.5:
                bx = rng.uniform(350, 750)
                T.peg(bx, yy + (1000 - bx) * t - 9, 7, 1)
        yy = yy + L * t + 92
    T.modules.append(("zigzag", y))
    return yy + 40


def m_windmills(T, y, nb=0):
    rng = T.rng
    T.poly([(440, y + 60), (500, y), (560, y + 60)], 8, 0)
    centers = [(260.0, y + 240.0), (740.0, y + 240.0)]
    if rng.random() < 0.75:
        centers.append((500.0, y + 570.0))
    for (cx, cy) in centers:
        arms = rng.choice([3, 4])
        w = rng.choice([-1, 1]) * rng.uniform(1.1, 1.9)
        b = T.add_body(Body(cx, cy, "spinner", a0=rng.uniform(0, 6.28), w=w))
        for a in range(arms):
            th = 2 * math.pi * a / arms
            T.seg(0, 0, 150 * math.cos(th), 150 * math.sin(th), 9, 4, b)
        T.seg(0, 0, 0, 0, 16, 4, b)
    T.modules.append(("windmills", y))
    return y + (570 if len(centers) == 3 else 240) + 159 + 70


def m_trapdoors(T, y, nb=0):
    rng = T.rng
    P = rng.uniform(4.2, 5.8)
    ph0 = rng.uniform(0, 6.28)
    yl = y + 20
    for lvl in range(rng.choice([2, 3])):
        T.seg(0, yl, 370, yl + 150, 9, 0)
        T.seg(1000, yl, 630, yl + 150, 9, 0)
        ph = ph0 + lvl * rng.uniform(1.6, 3.0)
        a = math.radians(41)
        bl = T.add_body(Body(370, yl + 150, "flap", a0=a, amp=a, k=6.0, P=P, ph=ph, bias=0.5))
        T.seg(0, 0, 128, 0, 8, 4, bl)
        br = T.add_body(Body(630, yl + 150, "flap", a0=-a, amp=-a, k=6.0, P=P, ph=ph, bias=0.5))
        T.seg(0, 0, -128, 0, 8, 4, br)
        yl += 400
    T.modules.append(("trapdoors", y))
    return yl - 400 + 150 + 128 + 80


def _chan_zig(T, x0, x1, y, H):
    w = x1 - x0
    L = w * 0.72
    t = math.tan(math.radians(20))
    yy = y + 40
    i = 0
    while yy + L * t < y + H - 60:
        if i % 2 == 0:
            T.seg(x0, yy, x0 + L, yy + L * t, 7, 5)
        else:
            T.seg(x1, yy, x1 - L, yy + L * t, 7, 5)
        yy += L * t + 80
        i += 1


def _chan_pegs(T, x0, x1, y, H):
    yy = y + 50
    r = 0
    while yy < y + H - 40:
        xs = [x0 + 80, x0 + 158, x0 + 237] if r % 2 == 0 else [x0 + 120, x0 + 198]
        for x in xs:
            T.peg(x, yy, 7, 1)
        yy += 70
        r += 1


def _chan_spin(T, x0, x1, y, H):
    rng = T.rng
    cx = (x0 + x1) / 2
    yy = y + 120
    while yy < y + H - 90:
        b = T.add_body(Body(cx, yy, "spinner", a0=rng.uniform(0, 6.28), w=rng.choice([-1, 1]) * rng.uniform(2.0, 3.0)))
        T.seg(-70, 0, 70, 0, 9, 4, b)
        yy += 190


def _chan_bump(T, x0, x1, y, H):
    yy = y + 90
    r = 0
    while yy < y + H - 60:
        cx = (x0 + x1) / 2 + (-55 if r % 2 else 55)
        T.peg(cx, yy, 22, 3)
        yy += 150
        r += 1


def m_tunnels(T, y, nb=0):
    rng = T.rng
    H = rng.uniform(850, 1100)
    T.seg(333, y, 333, y + H, 9, 0)
    T.seg(667, y, 667, y + H, 9, 0)
    kinds = [_chan_zig, _chan_pegs, _chan_spin, _chan_bump]
    rng.shuffle(kinds)
    for (x0, x1), fn in zip([(9, 324), (342, 658), (676, 991)], kinds[:3]):
        fn(T, x0, x1, y, H)
    T.modules.append(("tunnels", y))
    return funnel(T, y + H + 20, 200, 260)


def m_ring_gate(T, y, nb=0):
    rng = T.rng
    cx, cy, R = 500.0, y + 320.0, 220.0
    d = R + 8 + 30 + 8
    a = math.radians(50)
    tipx, tipy = d * math.sin(a), cy - d * math.cos(a)
    T.seg(0, y, cx - tipx, tipy, 9, 0)
    T.seg(1000, y, cx + tipx, tipy, 9, 0)
    ngap = rng.choice([1, 2, 2])
    gap = math.radians(46)
    w = rng.choice([-1, 1]) * rng.uniform(0.9, 1.3) * (1.25 if ngap == 1 else 1.0)
    b = T.add_body(Body(cx, cy, "ring", a0=rng.uniform(0, 6.28), w=w, ring_r=R, ring_idx=3))
    for g in range(ngap):
        base = g * 2 * math.pi / ngap
        span = 2 * math.pi / ngap - gap
        n = max(8, int(span / math.radians(5)))
        pts = [(R * math.cos(base + gap / 2 + span * j / n), R * math.sin(base + gap / 2 + span * j / n)) for j in range(n + 1)]
        T.poly(pts, 8, 2, b)
    T.modules.append(("ring_gate", y))
    return cy + R + 8 + 90


def m_bumpers(T, y, nb=0):
    rng = T.rng
    rows = rng.randint(3, 4)
    yy = y + 60
    for r in range(rows):
        xs = [230, 500, 770] if r % 2 == 0 else [365, 635]
        for x in xs:
            T.peg(x + rng.uniform(-25, 25), yy, 26, 3)
        T.seg(0, yy + 40, 80, yy + 85, 8, 0)
        T.seg(1000, yy + 40, 920, yy + 85, 8, 0)
        yy += 175
    T.modules.append(("bumpers", y))
    return yy + 30


def m_rotor(T, y, nb=0):
    rng = T.rng
    y2 = funnel(T, y, 380, 200)
    cx, cy = 500.0, y2 + 300.0
    arms = rng.choice([3, 4])
    b = T.add_body(Body(cx, cy, "spinner", a0=rng.uniform(0, 6.28), w=rng.choice([-1, 1]) * rng.uniform(0.7, 1.0)))
    for a in range(arms):
        th = 2 * math.pi * a / arms
        T.seg(0, 0, 290 * math.cos(th), 290 * math.sin(th), 10, 4, b)
    T.seg(0, 0, 0, 0, 22, 4, b)
    T.modules.append(("rotor", y))
    return cy + 300 + 80


def m_stairs(T, y, nb=0):
    rng = T.rng
    flights = rng.choice([2, 3])
    step_w, drop = 110.0, 60.0
    tl = math.tan(math.radians(8)) * step_w
    y1 = y + 20
    for fl in range(flights):
        for s in range(7):
            if fl % 2 == 0:
                x0 = s * step_w
                T.seg(x0, y1 + s * drop, x0 + step_w, y1 + s * drop + tl, 7, 5)
            else:
                x0 = 1000 - s * step_w
                T.seg(x0, y1 + s * drop, x0 - step_w, y1 + s * drop + tl, 7, 5)
        y1 += 560
    T.modules.append(("stairs", y))
    return y1 - 560 + 6 * drop + tl + 90


def m_twin_rings(T, y, nb=0):
    rng = T.rng
    R = 150.0
    cy = y + 260.0
    d = R + 8 + 30 + 8
    a = math.radians(50)
    sx, sy = d * math.sin(a), d * math.cos(a)
    c1, c2 = 265.0, 735.0
    T.seg(0, y, c1 - sx, cy - sy, 9, 0)
    T.poly([(c1 + sx, cy - sy), (500, y + 40), (c2 - sx, cy - sy)], 9, 0)
    T.seg(1000, y, c2 + sx, cy - sy, 9, 0)
    gap = math.radians(52)
    w0 = rng.uniform(1.0, 1.4)
    for j, cx in enumerate((c1, c2)):
        w = w0 * (1 if j == 0 else -1) * rng.choice([1, -1]) * rng.uniform(0.9, 1.1)
        b = T.add_body(Body(cx, cy, "ring", a0=rng.uniform(0, 6.28), w=w, ring_r=R, ring_idx=4 + j))
        span = 2 * math.pi - gap
        n = int(span / math.radians(6))
        pts = [(R * math.cos(gap / 2 + span * k / n), R * math.sin(gap / 2 + span * k / n)) for k in range(n + 1)]
        T.poly(pts, 8, 2, b)
    T.modules.append(("twin_rings", y))
    return cy + R + 8 + 90


def m_pendulums(T, y, nb=0):
    rng = T.rng
    L = 250.0
    P = rng.uniform(2.2, 3.0)
    for j, px in enumerate((290.0, 710.0)):
        b = T.add_body(Body(px, y + 30, "flap", a0=math.pi / 2, amp=math.radians(rng.uniform(38, 44)), k=0.0, P=P,
                            ph=(0 if j == 0 else math.pi) + rng.uniform(-0.4, 0.4)))
        T.seg(0, 0, L, 0, 6, 4, b)
        T.seg(L, 0, L, 0, 34, 4, b)
        T.peg(px, y + 30, 12, 0)
    # колышки ниже маятников, чтобы ловить отбитых
    yy = y + 30 + L + 34 + 70
    for r in range(3):
        for x in ([180, 380, 620, 820] if r % 2 == 0 else [280, 500, 720]):
            T.peg(x, yy, 9, 1)
        yy += 80
    T.modules.append(("pendulums", y))
    return yy + 30


def m_finish(T, y):
    y2 = funnel(T, y, 230, 260)
    top = y2 - 50
    T.seg(385, top, 385, top + 240, 9, 0)
    T.seg(615, top, 615, top + 240, 9, 0)
    T.finish_y = top + 120
    T.modules.append(("finish", y))
    return top + 240


MODULES = {
    "pegs": m_pegs, "zigzag": m_zigzag, "windmills": m_windmills, "trapdoors": m_trapdoors,
    "tunnels": m_tunnels, "ring_gate": m_ring_gate, "bumpers": m_bumpers, "rotor": m_rotor,
    "stairs": m_stairs, "twin_rings": m_twin_rings, "pendulums": m_pendulums,
}


def build_stage(rng, nb, n_modules):
    T = Track(rng)
    y = m_ring_start(T, 0.0, nb)
    order = []
    while len(order) < n_modules:
        names = list(MODULES)
        rng.shuffle(names)
        if order and names[0] == order[-1]:
            names.append(names.pop(0))
        order += names
    order = order[:n_modules]
    for name in order:
        y = MODULES[name](T, y, nb)
    y = m_finish(T, y)
    walls_and_ceiling(T, -320.0, T.finish_y + 1000)
    T.order = order
    T.height = T.finish_y + 1000
    return T


def run_stage(T, qual, seed, tmax=200.0, after=2.5):
    tmp = tempfile.mkdtemp(prefix="stage_")
    inp, fr, ev = (os.path.join(tmp, n) for n in ("in.txt", "frames.bin", "events.txt"))
    T.write_input(inp, T.spawn, qual, tmax, after, fr, ev, seed)
    subprocess.run([os.path.join(HERE, "phys"), inp], check=True)
    nb = len(T.spawn)
    data = np.fromfile(fr, dtype=np.float32).reshape(-1, nb, 4)
    hits, breaks, fins, kicks, outs, dmg = [], {}, [], [], [], []
    end = None
    for line in open(ev):
        p = line.split()
        if p[0] == "H":
            hits.append((float(p[1]), int(p[2]), float(p[3]), float(p[4]), float(p[5]), int(p[6])))
        elif p[0] == "D":
            dmg.append((float(p[1]), int(p[2])))
        elif p[0] == "B":
            breaks[int(p[2])] = float(p[1])
        elif p[0] == "F":
            fins.append((float(p[1]), int(p[2])))
        elif p[0] == "K":
            kicks.append((float(p[1]), int(p[2])))
        elif p[0] == "O":
            outs.append((float(p[1]), int(p[2])))
        elif p[0] == "END":
            end = (float(p[1]), int(p[2]))
    return {"pos": data, "hits": hits, "breaks": breaks, "dmg": dmg, "fins": fins, "kicks": kicks, "outs": outs, "end": end,
            "qual": qual, "tmp": tmp}
