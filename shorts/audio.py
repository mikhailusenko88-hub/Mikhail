"""Звук гонки: своя музыка (синтез, без чужих прав) + звуки ударов, колец, финиша."""
import math

import numpy as np

SR = 44100


class Mix:
    def __init__(self, seconds, seed=1):
        self.n = int((seconds + 2) * SR)
        self.music = np.zeros(self.n, np.float32)
        self.sfx = np.zeros(self.n, np.float32)
        self.r = np.random.default_rng(seed)
        self._noise = self.r.uniform(-1, 1, SR * 2).astype(np.float32)

    def put(self, buf, sig, at):
        s = int(at * SR)
        if s < 0 or s >= self.n:
            return
        e = min(self.n, s + len(sig))
        buf[s:e] += sig[:e - s]

    # ---------- инструменты
    def tone(self, f, dur, vol, decay=6.0, harm=(1.0, 0.3, 0.1), attack=0.003):
        t = np.arange(int(dur * SR), dtype=np.float32) / SR
        env = np.exp(-t * decay) * np.minimum(1, t / attack)
        sig = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harm))
        return (vol * env * sig).astype(np.float32)

    def noise(self, dur, vol, decay=20.0, hp=False):
        m = int(dur * SR)
        start = self.r.integers(0, len(self._noise) - m - 1)
        x = self._noise[start:start + m].copy()
        if hp:
            x = np.diff(x, prepend=0)
        t = np.arange(m, dtype=np.float32) / SR
        return (vol * x * np.exp(-t * decay)).astype(np.float32)

    def kick(self, vol=0.9):
        t = np.arange(int(0.3 * SR), dtype=np.float32) / SR
        f = 45 + 90 * np.exp(-t * 30)
        ph = 2 * np.pi * np.cumsum(f) / SR
        return (vol * np.sin(ph) * np.exp(-t * 9)).astype(np.float32)

    # ---------- музыка
    def music_section(self, t0, t1, key=0, bpm=120, energy=1.0, seed=0):
        """Бодрый электро-луп: бочка, хлопок, хэты, бас, арпеджио, пэд. key — сдвиг в полутонах."""
        rr = np.random.default_rng(1000 + seed)
        beat = 60 / bpm
        progs = [[9, 5, 0, 7], [0, 7, 9, 5], [9, 7, 5, 7], [0, 5, 9, 7], [2, 7, 0, 9]]
        prog = progs[seed % len(progs)]
        base = 220.0 * 2 ** (key / 12)       # A3
        major = {0, 5, 7}
        bar = 4 * beat
        t = t0
        bi = 0
        arp_pat = [0, 1, 2, 3, 2, 1, 2, 3] if seed % 2 else [0, 2, 1, 3, 0, 2, 3, 1]
        while t < t1 - 0.05:
            root = prog[bi % 4]
            third = 4 if root in major else 3
            chord = [root, root + third, root + 7, root + 12]
            fr = lambda s, o=0: base * 2 ** ((s + 12 * o) / 12)
            # пэд
            pad_len = min(bar, t1 - t)
            if pad_len > 0.1:
                for s in chord[:3]:
                    sig = self.tone(fr(s, 0), pad_len, 0.035, decay=0.6, harm=(1, 0.15), attack=0.25)
                    sig += self.tone(fr(s, 0) * 1.004, pad_len, 0.03, decay=0.6, harm=(1,), attack=0.3)
                    self.put(self.music, sig, t)
            for b in range(4):
                tb = t + b * beat
                if tb >= t1:
                    break
                if energy > 0.5:
                    self.put(self.music, self.kick(0.55), tb)
                    if b in (1, 3):
                        self.put(self.music, self.noise(0.18, 0.22, 22), tb)
                    for h in range(2):
                        self.put(self.music, self.noise(0.05, 0.07 if h else 0.05, 70, hp=True), tb + h * beat / 2)
                # бас восьмыми
                for h in range(2):
                    tt = tb + h * beat / 2
                    if tt < t1 and energy > 0.3:
                        self.put(self.music, self.tone(fr(root, -1), beat / 2 * 0.9, 0.16 * energy, decay=5,
                                                       harm=(1, 0.5, 0.25, 0.12)), tt)
                # арпеджио шестнадцатыми
                for q in range(4):
                    tt = tb + q * beat / 4
                    if tt >= t1:
                        break
                    idx = arp_pat[(b * 4 + q) % 8]
                    s = chord[idx % 4]
                    self.put(self.music, self.tone(fr(s, 1), 0.18, 0.05 + 0.02 * energy, decay=14,
                                                   harm=(1, 0.0, 0.2)), tt)
            t += bar
            bi += 1

    # ---------- эффекты
    PENTA = [0, 2, 4, 7, 9]

    def hits(self, hits, t_off, ring_bodies):
        """hits: (t, kind, speed, x, y, body). Не больше ~3 звуков на 1/40 c."""
        buckets = {}
        for h in hits:
            k = int((h[0] + t_off) * 40)
            buckets.setdefault(k, []).append(h)
        for k, hs in buckets.items():
            hs.sort(key=lambda h: -h[2])
            for (t, kind, sp, x, y, body) in hs[:3]:
                v = min(1.0, (sp - 120) / 700)
                if v <= 0:
                    continue
                at = t + t_off
                if kind == 2:
                    n = self.PENTA[int(x * 7 + y) % 5] + 12 * (ring_bodies.get(body, 0) % 2)
                    self.put(self.sfx, self.tone(523.25 * 2 ** (n / 12), 0.35, 0.16 * v + 0.04, decay=9,
                                                 harm=(1, 0.0, 0.25, 0.1)), at)
                elif kind == 3:
                    tt = np.arange(int(0.16 * SR), dtype=np.float32) / SR
                    f = 260 + 520 * tt / 0.16
                    sig = 0.2 * v * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14)
                    self.put(self.sfx, sig.astype(np.float32), at)
                elif kind == 1:
                    n = self.PENTA[int(x + y * 3) % 5]
                    self.put(self.sfx, self.tone(1046.5 * 2 ** (n / 12), 0.09, 0.07 * v + 0.02, decay=40), at)
                elif kind == 9:
                    self.put(self.sfx, self.tone(2400, 0.035, 0.06 * v + 0.02, decay=90, harm=(1, 0.4)), at)
                    self.put(self.sfx, self.noise(0.02, 0.05 * v, 150, hp=True), at)
                elif kind == 4:
                    self.put(self.sfx, self.tone(420, 0.07, 0.1 * v + 0.03, decay=45, harm=(1, 0.6, 0.3)), at)
                else:
                    self.put(self.sfx, self.tone(700 + (y % 97), 0.05, 0.06 * v + 0.02, decay=60, harm=(1, 0.5)), at)
                    self.put(self.sfx, self.noise(0.03, 0.05 * v, 100), at)

    def shatter(self, at):
        self.put(self.sfx, self.noise(0.7, 0.45, 7, hp=True), at)
        for i, s in enumerate((24, 19, 16, 12, 7)):
            self.put(self.sfx, self.tone(523.25 * 2 ** (s / 12), 0.5, 0.06, decay=7, harm=(1, 0.2)), at + i * 0.035)

    def finish_ding(self, at, place, qualified=True):
        if qualified:
            s = [12, 7, 4][place] if place < 3 else 0
            vol = 0.22 if place < 3 else 0.12
            self.put(self.sfx, self.tone(784.0 * 2 ** (s / 12), 0.6, vol, decay=4.5, harm=(1, 0.0, 0.3, 0.15)), at)
        else:
            self.put(self.sfx, self.tone(196.0, 0.35, 0.18, decay=6, harm=(1, 0.6, 0.4, 0.3)), at)

    def buzzer(self, at):
        t = np.arange(int(0.55 * SR), dtype=np.float32) / SR
        sq = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.6 + np.sin(2 * np.pi * 55 * t)
        self.put(self.sfx, (0.16 * sq * np.exp(-t * 3)).astype(np.float32), at)
        self.put(self.sfx, self.kick(0.6), at)

    def beep(self, at, high=False):
        self.put(self.sfx, self.tone(1320 if high else 880, 0.5 if high else 0.18, 0.25, decay=5 if high else 12,
                                     harm=(1, 0.0, 0.2)), at)

    def fanfare(self, at):
        for i, s in enumerate((0, 4, 7, 12, 16, 19, 24)):
            self.put(self.sfx, self.tone(523.25 * 2 ** (s / 12), 2.4 - i * 0.15, 0.13, decay=1.8, harm=(1, 0.35, 0.15)),
                     at + i * 0.09)
        self.put(self.sfx, self.noise(1.2, 0.15, 3, hp=True), at)

    def whoosh(self, at):
        m = int(0.6 * SR)
        x = np.cumsum(self.r.uniform(-1, 1, m)).astype(np.float32)
        x -= np.convolve(x, np.ones(200) / 200, mode="same")
        t = np.arange(m) / SR
        env = np.sin(np.pi * t / 0.6) ** 2
        self.put(self.sfx, (0.02 * x * env).astype(np.float32), at)

    def final(self):
        mus = self.music / max(1e-6, float(np.abs(self.music).max())) * 0.42
        sfx = self.sfx
        # мягкий лимитер эффектов
        sfx = np.tanh(sfx * 1.6) / 1.6
        a = mus + sfx
        return a / max(1e-6, float(np.abs(a).max())) * 0.9
