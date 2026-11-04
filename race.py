"""Ролик гонки 32 стран (выбывание за 7 этапов) + таблица месяца.

python3 race.py --date 2026-11-05 --state league_state.json --out race.mp4 [--preview SECONDS] [--no-save]
"""
import argparse
import bisect
import datetime as dt
import json
import math
import os
import random
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import audio
import countries
import fastvid
import league
import render
import track
from render import (H, MAX_S, MIN_S, PANEL_X, VIEW_W, W, ball_sprite, flag_rect, font, mix, paste_center,
                    text_center)

FPS = 30
CHANNEL = "FLAGBALL ARENA"
FRAMES_MODE = False
STAGES = [(32, 26), (26, 20), (20, 15), (15, 10), (10, 6), (6, 3), (3, 3)]
TARGETS = [66, 64, 62, 60, 58, 56, 60]
A3 = countries.A3
WHITE = (255, 255, 255)
GREEN = (60, 220, 120)
RED = (235, 60, 70)
GOLD = (255, 205, 70)
SILVER = (200, 210, 225)
BRONZE = (215, 140, 80)


def log(*a):
    print(*a, flush=True)


# ============================================================ планирование этапов
def plan_stage(k, nb, q, seed0):
    target = TARGETS[k]
    nm = max(4, round(target / 5.4))
    best = None
    for attempt in range(80):
        seed = seed0 * 1000 + k * 100 + attempt
        rng = random.Random(seed)
        T = track.build_stage(rng, nb, nm)
        res = track.run_stage(T, q, seed)
        f = [t for t, i in res["fins"]]
        if len(f) < q:
            nm = max(4, nm - 1)
            continue
        qt = f[q - 1]
        ok = len(res["kicks"]) <= 3 and not res["outs"]
        err = abs(qt - target)
        if ok and (best is None or err < best[0]):
            best = (err, T, res, seed)
        if ok and err <= 4:
            break
        if qt < target - 4:
            nm += 1
        elif qt > target + 4:
            nm = max(4, nm - 1)
    return best


def stage_order(res, nb):
    fins = sorted(res["fins"])
    order = [i for t, i in fins]
    last = res["pos"][-1]
    rest = sorted([i for i in range(nb) if i not in order], key=lambda i: -last[i, 1])
    return order + rest


# ============================================================ камера
def camera_path(T, res, q, cy0, s0):
    pos = res["pos"]
    nf, nb = pos.shape[0], pos.shape[1]
    fin_t = sorted(t for t, i in res["fins"])
    cams = np.zeros((nf, 2))
    cy, s = cy0, s0
    cy_t, s_t = cy0, s0
    a = 1 - math.exp(-1 / FPS / 0.45)
    b = 1 - math.exp(-1 / FPS / 0.9)
    for f in range(nf):
        t = f / FPS
        stt = pos[f, :, 3]
        act = [i for i in range(nb) if stt[i] == 0]
        nfin = bisect.bisect_right(fin_t, t)
        qrem = q - nfin
        if act and qrem > 0:
            act.sort(key=lambda i: -pos[f, i, 1])
            kc = min(qrem, len(act)) - 1
            if nfin == 0:
                ys = [pos[f, act[0], 1], pos[f, act[min(qrem, len(act) - 1)], 1]]
            else:
                ys = [pos[f, act[j], 1] for j in range(max(0, kc - 2), min(len(act), kc + 3))]
            top, bot = min(ys), max(ys)
            if T.finish_y - bot < (700 if nfin == 0 else 900):
                bot = max(bot, T.finish_y + 70)
            need = bot - top + 560
            s_t = min(MAX_S, max(MIN_S, H / need))
            vh = H / s_t
            if need <= vh:
                cy_t = (top + bot) / 2
            elif nfin == 0:
                cy_t = bot + 280 - vh / 2
            else:
                cy_t = pos[f, act[kc], 1]
        cy += (cy_t - cy) * a
        s += (s_t - s) * b
        vh = H / s
        cy = min(max(cy, render.Y_TOP + vh / 2), T.height + 200 - vh / 2)
        cams[f] = cy, s
    return cams


# ============================================================ таблица справа
class Panel:
    def __init__(self, codes, q, k, race_no, date, fdate, theme, final_race):
        self.codes = codes
        self.nb = len(codes)
        self.q = q
        self.th = theme
        self.two = self.nb > 16
        self.rowh = 56
        self.disp = {}
        self.rows = {}
        img = Image.new("RGBA", (W - PANEL_X, H), (8, 10, 20, 255))
        d = ImageDraw.Draw(img)
        acc = theme["accent"]
        d.rectangle([0, 0, 3, H], fill=acc + (255,))
        title = "FINAL STAGE" if k == len(STAGES) - 1 else f"STAGE {k + 1}/{len(STAGES)}"
        d.text((24, 16), title, font=font(30), fill=acc)
        tag = "FINAL" if final_race else f"#{race_no}"
        tw = d.textlength(tag, font=font(30))
        d.text((W - PANEL_X - 22 - tw, 16), tag, font=font(30), fill=WHITE)
        # 32 → 26
        if k < len(STAGES) - 1:
            s1, s2 = str(self.nb), str(q)
            x = 24
            d.text((x, 54), s1, font=font(40), fill=WHITE)
            x += d.textlength(s1, font=font(40)) + 14
            d.polygon([(x, 78), (x + 30, 78), (x + 30, 68), (x + 48, 84), (x + 30, 100), (x + 30, 90), (x, 90)], fill=GREEN)
            x += 62
            d.text((x, 54), s2, font=font(40), fill=GREEN)
        else:
            d.text((24, 54), "1  2  3", font=font(40), fill=GOLD)
        # места
        for slot in range(self.nb):
            x, y = self.slot_xy(slot)
            if slot >= q:
                d.rounded_rectangle([x - 40, y - 2, x + self.roww() + 2, y + 48], 8, fill=(70, 14, 22, 255))
            num = str(slot + 1)
            nw = d.textlength(num, font=font(22))
            d.text((x - 8 - nw, y + 9), num, font=font(22), fill=(160, 170, 190))
        if q < self.nb:
            x, y = self.slot_xy(q)
            col_x0 = x - 42
            d.line([col_x0, y - 6, col_x0 + self.roww() + 46, y - 6], fill=RED, width=3)
        fd = f"{fdate.day:02d}.{fdate.month:02d}"
        foot = "TODAY: MONTH FINAL" if final_race else f"MONTH FINAL  {fd}"
        fw = d.textlength(foot, font=font(22))
        d.text(((W - PANEL_X - fw) / 2, H - 46), foot, font=font(22), fill=GOLD)
        self.base = img.convert("RGB")

    def roww(self):
        return 186 if self.two else 380

    def slot_xy(self, slot):
        if self.two:
            col, row = divmod(slot, 16)
            return 50 + col * 236, 120 + row * self.rowh
        return 70, 120 + slot * self.rowh

    def row(self, i, status):
        key = (i, status)
        if key not in self.rows:
            w, h = self.roww(), 46
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            bg = {"run": (255, 255, 255, 22), "ok": (40, 200, 110, 120), "out": (220, 40, 55, 150),
                  "lead": (255, 205, 70, 70)}[status]
            d.rounded_rectangle([0, 0, w - 1, h - 1], 9, fill=bg)
            fl = flag_rect(self.codes[i], 48, 36, 5)
            im.paste(fl, (6, 5), fl)
            d.text((64, 6), A3[self.codes[i]], font=font(25), fill=WHITE if status != "out" else (255, 200, 200))
            if status == "ok":
                d.line([(w - 34, 23), (w - 25, 32), (w - 11, 13)], fill=WHITE, width=5)
            elif status == "out":
                d.line([(w - 32, 12), (w - 12, 34)], fill=WHITE, width=5)
                d.line([(w - 12, 12), (w - 32, 34)], fill=WHITE, width=5)
            self.rows[key] = im
        return self.rows[key]

    def draw(self, img, order, status, snap=False):
        pan = self.base.copy()
        for slot, i in enumerate(order):
            tx, ty = self.slot_xy(slot)
            if i not in self.disp or snap:
                self.disp[i] = [tx, ty]
            dp = self.disp[i]
            dp[0] += (tx - dp[0]) * 0.22
            dp[1] += (ty - dp[1]) * 0.22
            r = self.row(i, status[i])
            pan.paste(r, (int(dp[0]), int(dp[1])), r)
        img.paste(pan, (PANEL_X, 0))


# ============================================================ кадр гонки
class StageView:
    def __init__(self, k, T, res, codes, q, theme, panel):
        self.k, self.T, self.res, self.codes, self.q, self.th, self.panel = k, T, res, codes, q, theme, panel
        self.art = render.StageArt(T, theme)
        self.nb = len(codes)
        self.pos = res["pos"]
        self.fin = {i: t for t, i in res["fins"]}
        self.fin_rank = {i: n for n, (t, i) in enumerate(sorted(res["fins"]))}
        self.dyn = [bi for bi, b in enumerate(T.bodies) if b.dynamic]
        # разрушение колец: событие или запасной срок
        self.gone = {}
        for bi, b in enumerate(T.bodies):
            if b.look == "ring" and b.hp > 0:
                tb = res["breaks"].get(bi, None)
                tt = b.toff if b.toff < 1e8 else None
                cands = [v for v in (tb, tt) if v is not None]
                if cands:
                    self.gone[bi] = min(cands)
        self.dmg = {}
        for (t, body) in res["dmg"]:
            self.dmg.setdefault(body, []).append(t)
        rr = random.Random(k * 77)
        self.shards = []
        for bi, tb in self.gone.items():
            b = T.bodies[bi]
            th = b.angle(tb)
            col = theme["rings"][b.ring_idx % len(theme["rings"])]
            for j in range(44):
                a = rr.uniform(0, 2 * math.pi)
                R0 = b.ring_r
                px, py = b.px + R0 * math.cos(a + th), b.py + R0 * math.sin(a + th)
                sp = rr.uniform(120, 460)
                vx = math.cos(a + th) * sp - math.sin(a + th) * b.w * R0
                vy = math.sin(a + th) * sp + math.cos(a + th) * b.w * R0 - 150
                self.shards.append((tb, px, py, vx, vy, rr.uniform(0, 6.28), rr.uniform(-9, 9), rr.uniform(24, 46),
                                    mix(col, WHITE, rr.uniform(0, 0.5))))

    def _orders(self):
        """Порядок для таблицы на каждый кадр: сглаженный прогресс + гистерезис, обновление 6 раз в секунду."""
        nf = len(self.pos)
        ring_exit = self.T.ring_center[1] + 420
        y0 = self.pos[0, :, 1].astype(np.float64)
        sm = np.where(y0 < ring_exit, ring_exit, y0)
        a = 1 - math.exp(-1 / FPS / 0.35)
        cur = sorted(range(self.nb), key=lambda i: -sm[i])
        out = []
        for f in range(nf):
            t = f / FPS
            yf = self.pos[f, :, 1]
            sm += (np.where(yf < ring_exit, ring_exit, yf) - sm) * a

            def key(i):
                if i in self.fin and self.fin[i] <= t:
                    return 1e7 - self.fin[i] * 1000
                return sm[i]
            if f % 12 == 0:
                for _ in range(self.nb):
                    sw = False
                    for j in range(self.nb - 1):
                        x, y = cur[j], cur[j + 1]
                        kx, ky = key(x), key(y)
                        if ky > kx + (0 if ky > 1e6 else 35):
                            cur[j], cur[j + 1] = y, x
                            sw = True
                    if not sw:
                        break
            out.append(list(cur))
        return out

    def order_status(self, f, final=False):
        t = f / FPS
        if not hasattr(self, "orders"):
            self.orders = self._orders()
        order = self.orders[min(f, len(self.orders) - 1)]
        done = [i for i in order if i in self.fin and self.fin[i] <= t]
        status = {}
        for slot, i in enumerate(order):
            if i in done:
                status[i] = "ok" if self.fin_rank[i] < self.q else "out"
            else:
                status[i] = "out" if final else "run"
        if not final and order and status[order[0]] == "run":
            status[order[0]] = "lead"
        return order, status

    def frame(self, f, cy, s, extra=None, snap=False, final_status=False):
        t = f / FPS
        T, art = self.T, self.art
        bg, x0, y0 = art.background(cy, s)
        # вращающиеся тела
        for bi in self.dyn:
            b = T.bodies[bi]
            if bi in self.gone and t >= self.gone[bi]:
                continue
            px, py = b.offset(t)
            sx, sy = (px - x0) * s, (py - y0) * s
            lvl = 0
            if bi in self.gone:
                hp0 = art.ring_hp0.get(bi, 1)
                n = bisect.bisect_right(self.dmg.get(bi, []), t)
                frac = n / max(1, hp0)
                lvl = 0 if frac < 0.3 else 1 if frac < 0.6 else 2 if frac < 0.85 else 3
                if self.gone[bi] - t < 0.6:
                    lvl = max(lvl, 3 if int(t * 12) % 2 else 2)
            spr, halfs = art.body_sprite_scaled(bi, lvl, s)
            if sy + halfs < -20 or sy - halfs > H + 20:
                continue
            rot = spr.rotate(-math.degrees(b.angle(t)), Image.BILINEAR)
            paste_center(bg, rot, sx, sy)
        # осколки
        d = ImageDraw.Draw(bg)
        for (tb, px, py, vx, vy, a0, wa, ln, col) in self.shards:
            age = t - tb
            if age < 0 or age > 1.7:
                continue
            X = px + vx * age
            Y = py + vy * age + 0.5 * 1100 * age * age
            a = a0 + wa * age
            k = 1 - age / 1.7
            hx, hy = math.cos(a) * ln / 2, math.sin(a) * ln / 2
            c = mix(self.th["bg1"], col, k)
            d.line([((X - hx - x0) * s, (Y - hy - y0) * s), ((X + hx - x0) * s, (Y + hy - y0) * s)], fill=c,
                   width=max(2, int(9 * s)))
        # шарики
        p = self.pos[min(f, len(self.pos) - 1)]
        order, status = self.order_status(f, final_status)
        rpx = max(8, int(round(track.R_BALL * s)))
        lead = order[0] if order and status.get(order[0]) == "lead" else None
        for i in range(self.nb):
            if p[i, 3] >= 2:
                continue
            sx, sy = (p[i, 0] - x0) * s, (p[i, 1] - y0) * s
            if sy < -40 or sy > H + 40:
                continue
            spr = ball_sprite(self.codes[i], rpx, p[i, 2])
            paste_center(bg, spr, sx, sy)
            if i == lead:
                d.ellipse([sx - rpx - 4, sy - rpx - 4, sx + rpx + 4, sy + rpx + 4], outline=GOLD, width=3)
        img = Image.new("RGB", (W, H))
        img.paste(bg, (0, 0))
        self.panel.draw(img, order, status, snap)
        if extra:
            extra(img)
        return img


# ============================================================ карточки
def card_bg(theme):
    g = np.linspace(0, 1, H)[:, None, None]
    a = np.array(theme["bg0"], np.float32) * 0.8
    b = np.array(theme["bg1"], np.float32) * 1.2
    arr = a + (b - a) * g
    arr = np.repeat(arr, W, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.45 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    arr = arr * vig[..., None]
    dots = ((yy % 48) < 3) & ((xx % 48) < 3)
    arr[dots] += 14
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def dim(img, k=0.45, region=None):
    arr = np.asarray(img).astype(np.float32)
    if region:
        x0, y0, x1, y1 = region
        arr[y0:y1, x0:x1] *= k
    else:
        arr *= k
    return Image.fromarray(arr.astype(np.uint8))


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def pop(x):
    """0→1 с небольшим перелётом."""
    x = max(0.0, min(1.0, x))
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if x < 1 else 1.0


def big_ball(a2, rpx):
    return ball_sprite(a2, rpx, 0.0)


def next_card_frames(cbg, nkind, nparts, race_no, secs):
    """Конечная заставка: флаги следующей гонки в верхней половине, низ свободен под элементы YouTube."""
    for j in range(int(secs * FPS)):
        tt = j / FPS
        img = cbg.copy()
        dd = ImageDraw.Draw(img)
        ttl = "NEXT RACE: MONTH FINAL" if nkind == "final" else f"NEXT RACE  #{race_no + 1}"
        text_center(dd, W / 2, 26, ttl, font(56), GOLD, 5)
        for n, c in enumerate(nparts):
            r, cc = divmod(n, 8)
            ap = ease((tt - 0.2 - n * 0.03) / 0.3)
            if ap <= 0:
                continue
            fx = W / 2 + (cc - 3.5) * 150
            fy = 150 + r * 112
            fl = flag_rect(c, 92, 69, 7)
            paste_center(img, fl, fx, fy + (1 - ap) * 30)
            text_center(dd, fx, fy + 38, A3[c], font(22), WHITE, 3)
        text_center(dd, W / 2, 590, "3 RACES EVERY DAY  ·  IS YOUR COUNTRY NEXT?", font(38), WHITE, 4)
        yield img


class _NoMix:
    def __getattr__(self, name):
        return lambda *a, **k: None


# ============================================================ сборка ролика
def build(args):
    t_start = time.time()
    d = dt.date.fromisoformat(args.date)
    state = league.load(args.state)
    slot = args.slot
    kind, parts = league.take_participants(state, d, slot)
    race_no = state["race_no"] + 1
    fdate = league.final_date(d)
    final_race = kind == "final"
    seed0 = state["seed"] * 7 + race_no * 131
    rng = random.Random(seed0)
    log(f"гонка #{race_no} {d} ({kind}), участники: {' '.join(A3[c] for c in parts)}")

    # ---- физика всех этапов
    stages = []
    alive = list(parts)
    elim_blocks = []
    themes = list(range(len(render.THEMES) - 1))
    rng.shuffle(themes)
    themes = themes[:len(STAGES) - 1] + [len(render.THEMES) - 1]
    for k, (nb, q) in enumerate(STAGES):
        assert len(alive) == nb, (len(alive), nb)
        codes = list(alive)
        rng.shuffle(codes)
        best = plan_stage(k, nb, q, seed0)
        err, T, res, seed = best
        order = stage_order(res, nb)
        qual = [codes[i] for i in order[:q]]
        out = [codes[i] for i in order[q:]]
        fins = sorted(t for t, i in res["fins"])
        log(f"  этап {k + 1}: {nb}→{q}, блоков {len(T.order)} {T.order}, Q-финиш {fins[q - 1]:.1f} c, кадров {len(res['pos'])}")
        stages.append(dict(k=k, nb=nb, q=q, T=T, res=res, codes=codes, order=order, qual=qual, out=out,
                           theme=render.THEMES[themes[k]]))
        if out:
            elim_blocks.append(out)
        alive = qual
    final_order = stages[-1]["qual"]
    ranking = list(final_order)
    for blk in reversed(elim_blocks):
        ranking += blk
    assert len(ranking) == 32 and len(set(ranking)) == 32
    prev_table = json.loads(json.dumps(state["table"]))
    gained = league.apply_result(state, d, kind, ranking, slot)
    nd, nslot = league.next_slot(d, slot)
    nkind, nparts = league.peek_participants(state, nd, nslot)

    # ---- длительность и звук
    INTRO0 = 4.2       # открытие (флаги всех участников)
    INTRO = 3.6        # «этап N» + 3-2-1
    OUTC = 3.6
    POD, TAB, NXT = 7.0, 10.0, 12.0
    total = INTRO0 + sum(INTRO + len(s["res"]["pos"]) / FPS + OUTC for s in stages) - OUTC + POD + TAB + NXT
    if args.preview:
        total = min(total, args.preview)
    log(f"длительность ролика ≈ {total / 60:.1f} мин")
    mixer = audio.Mix(total + 1, seed=seed0)
    if args.frames:
        mixer = _NoMix()
    global FRAMES_MODE
    FRAMES_MODE = bool(args.frames)
    out = None if FRAMES_MODE else fastvid.Writer(args.out, w=W, h=H, fps=FPS, bitrate="4500k", preset="veryfast")
    gt = 0.0          # глобальное время, с
    nframes = [0]

    want = set()
    if FRAMES_MODE:
        want = {int(float(x) * FPS) for x in args.frames.split(",")}

    def emit(img):
        n = nframes[0]
        if FRAMES_MODE:
            if n in want:
                im = img() if callable(img) else img
                im.save(f"/tmp/fr_{n / FPS:07.2f}.png")
                log("кадр", n / FPS)
        else:
            out.add(img() if callable(img) else img)
        nframes[0] += 1

    def done():
        return args.preview and nframes[0] / FPS >= args.preview

    key_base = rng.randint(0, 11)
    for st in stages:
        if done():
            break
        k, T, res, codes, q = st["k"], st["T"], st["res"], st["codes"], st["q"]
        theme = st["theme"]
        panel = Panel(codes, q, k, race_no, d, fdate, theme, final_race)
        view = StageView(k, T, res, codes, q, theme, panel)
        cx, cy0 = T.ring_center
        s0 = 0.92
        cams = camera_path(T, res, q, cy0 + 30, s0)
        nf = len(res["pos"])
        # музыка этапа
        sec = INTRO + nf / FPS + OUTC + (INTRO0 if k == 0 else 0)
        mixer.music_section(gt, gt + sec, key=(key_base + 2 * k) % 12 - 5, energy=1.0 if k < 6 else 1.15, seed=k)

        # --- открытие
        if k == 0:
            n0 = int(INTRO0 * FPS)
            mixer.whoosh(gt + 0.1)
            for j in range(n0):
                tt = j / FPS

                def ov(img, tt=tt):
                    reg = dim(img, 0.35, (0, 0, VIEW_W, H))
                    img.paste(reg)
                    dd = ImageDraw.Draw(img)
                    e = ease(tt / 0.5)
                    title = f"{CHANNEL}  ·  MONTH FINAL" if final_race else f"{CHANNEL}  ·  RACE #{race_no}"
                    text_center(dd, VIEW_W / 2, 40 - 30 * (1 - e), title, font(44), GOLD, 4)
                    text_center(dd, VIEW_W / 2, 98, "32 COUNTRIES  ·  1 WINNER", font(64), WHITE, 5)
                    # сетка флагов 8×4
                    for n, c in enumerate(parts):
                        r, cc = divmod(n, 8)
                        appear = ease((tt - 0.25 - n * 0.045) / 0.35)
                        if appear <= 0:
                            continue
                        fx = VIEW_W / 2 + (cc - 3.5) * 165
                        fy = 300 + r * 170
                        fl = flag_rect(c, 120, 90, 8)
                        if appear < 1:
                            sz = max(4, int(120 * appear))
                            fl = fl.resize((sz, max(3, int(90 * appear))), Image.BILINEAR)
                        paste_center(img, fl, fx, fy)
                        if appear >= 1:
                            text_center(dd, fx, fy + 50, A3[c], font(26), WHITE, 3)
                    if tt > 2.6:
                        text_center(dd, VIEW_W / 2, 975, "FIND YOUR COUNTRY", font(40), GOLD, 4)
                emit(lambda ov=ov, j=j: view.frame(0, cy0 + 30, s0, ov, snap=(j == 0) or FRAMES_MODE))
                if done():
                    break
            gt += n0 / FPS
        # --- заставка этапа + 3-2-1
        ni = int(INTRO * FPS)
        mixer.whoosh(gt)
        for j in range(ni):
            if done():
                break
            tt = j / FPS

            def ov(img, tt=tt):
                dd = ImageDraw.Draw(img)
                if tt < 1.2:
                    e = pop(tt / 0.35)
                    title = "FINAL STAGE" if k == len(STAGES) - 1 else f"STAGE {k + 1}"
                    f1 = font(max(10, int(110 * e)))
                    text_center(dd, VIEW_W / 2, 330, title, f1, WHITE, 7)
                    if k < len(STAGES) - 1:
                        sub = f"{st['nb']}  →  {q}"
                        text_center(dd, VIEW_W / 2, 470, f"TOP {q} GO ON", font(54), GREEN, 5)
                    else:
                        text_center(dd, VIEW_W / 2, 470, "WHO WINS?", font(54), GOLD, 5)
                else:
                    n = 3 - int((tt - 1.2) / 0.8)
                    loc = ((tt - 1.2) % 0.8) / 0.8
                    sz = int(220 * (1.25 - 0.35 * ease(loc / 0.4)))
                    col = [GREEN, GOLD, RED][max(0, min(2, n - 1))]
                    text_center(dd, VIEW_W / 2, 360 - sz * 0.3, str(max(1, n)), font(sz), col, 9)
            if tt >= 1.2 and abs(((tt - 1.2) % 0.8)) < 1e-6 + 1 / FPS / 2 and tt < 3.6:
                pass
            emit(lambda ov=ov, j=j: view.frame(0, cy0 + 30, s0, ov, snap=(j == 0) or FRAMES_MODE))
        for b in range(3):
            mixer.beep(gt + 1.2 + b * 0.8)
        gt += ni / FPS
        mixer.beep(gt, high=True)
        # --- гонка
        hits_ring = {bi: T.bodies[bi].ring_idx for bi in view.dyn if T.bodies[bi].look == "ring"}
        mixer.hits(res["hits"], gt, hits_ring)
        for bi, tb in view.gone.items():
            mixer.shatter(gt + tb)
        for n, (tf, i) in enumerate(sorted(res["fins"])):
            mixer.finish_ding(gt + tf, n, n < q)
        for f in range(nf):
            if done():
                break
            tt = f / FPS

            def ov(img, tt=tt):
                if tt < 0.7:
                    dd = ImageDraw.Draw(img)
                    e = pop(tt / 0.3)
                    text_center(dd, VIEW_W / 2, 330, "GO!", font(max(10, int(170 * e))), GREEN, 8)
            emit(lambda f=f, ov=ov: view.frame(f, cams[f, 0], cams[f, 1], ov, snap=FRAMES_MODE))
        gt += nf / FPS
        # --- выбывшие
        if st["out"] and not done():
            mixer.buzzer(gt + 0.15)
            no = int(OUTC * FPS)
            lastf = nf - 1
            outs = st["out"]
            place0 = 32 - sum(len(b) for b in elim_blocks[:k + 1]) + 1
            for j in range(no):
                if done():
                    break
                tt = j / FPS

                def ov(img, tt=tt):
                    reg = dim(img, 0.38, (0, 0, VIEW_W, H))
                    img.paste(reg)
                    dd = ImageDraw.Draw(img)
                    e = pop(tt / 0.3)
                    text_center(dd, VIEW_W / 2, 150, "OUT", font(max(10, int(150 * e))), RED, 8)
                    n = len(outs)
                    per = min(n, 6)
                    rows = math.ceil(n / per)
                    for m, c in enumerate(outs):
                        r, cc = divmod(m, per)
                        cnt = min(per, n - r * per)
                        ap = ease((tt - 0.25 - m * 0.1) / 0.3)
                        if ap <= 0:
                            continue
                        fx = VIEW_W / 2 + (cc - (cnt - 1) / 2) * 210
                        fy = 470 + r * 250 - (rows - 1) * 110
                        rp = max(6, int(70 * ap))
                        paste_center(img, big_ball(c, rp), fx, fy)
                        if ap >= 1:
                            dd.line([fx - 52, fy - 52, fx + 52, fy + 52], fill=RED, width=12)
                            dd.line([fx + 52, fy - 52, fx - 52, fy + 52], fill=RED, width=12)
                            text_center(dd, fx, fy + 80, A3[c], font(34), WHITE, 4)
                            text_center(dd, fx, fy + 122, f"#{place0 + m}", font(26), (200, 170, 170), 3)
                emit(lambda ov=ov: view.frame(lastf, cams[lastf, 0], cams[lastf, 1], ov, final_status=True, snap=FRAMES_MODE))
            gt += no / FPS

    # ---- пьедестал
    th = render.THEMES[-1]
    cbg = card_bg(th)
    conf_r = random.Random(seed0 + 5)
    confetti = [(conf_r.uniform(0, W), conf_r.uniform(-H, 0), conf_r.uniform(-60, 60), conf_r.uniform(160, 320),
                 conf_r.uniform(0, 6.28), conf_r.uniform(-6, 6),
                 conf_r.choice([GOLD, (255, 90, 120), (90, 200, 255), (120, 255, 150), WHITE])) for _ in range(220)]
    if not done():
        mixer.fanfare(gt + 0.2)
        mixer.music_section(gt, gt + POD + TAB + NXT, key=(key_base + 7) % 12 - 5, energy=0.8, seed=11)
    top3 = ranking[:3]
    for j in range(int(POD * FPS)):
        if done():
            break
        tt = j / FPS
        img = cbg.copy()
        dd = ImageDraw.Draw(img)
        title = f"{league.MONTHS_EN[d.month - 1]} CHAMPION" if final_race else f"RACE #{race_no} · WINNER"
        text_center(dd, W / 2, 40, title, font(60), GOLD, 5)
        spots = [(0, W / 2, 470, 150, GOLD, 260), (1, W / 2 - 520, 560, 110, SILVER, 170), (2, W / 2 + 520, 600, 100, BRONZE, 130)]
        for (pi, fx, fy, rp, col, ph) in spots:
            ap = pop((tt - 0.3 - [0.6, 0.3, 0][pi]) / 0.4)
            # ступень
            dd.rectangle([fx - 190, fy + rp + 40, fx + 190, H], fill=mix(col, (0, 0, 0), 0.55))
            dd.rectangle([fx - 190, fy + rp + 40, fx + 190, fy + rp + 52], fill=col)
            text_center(dd, fx, fy + rp + 70, str([1, 2, 3][pi]), font(90), col, 4)
            if ap <= 0:
                continue
            paste_center(img, big_ball(top3[pi], max(6, int(rp * ap))), fx, fy)
            if ap >= 0.99:
                text_center(dd, fx, fy - rp - 70, A3[top3[pi]], font(52), WHITE, 5)
                if not final_race:
                    text_center(dd, fx, fy + rp + 175, f"+{league.POINTS[pi]}", font(40), GREEN, 4)
        for (x, y, vx, vy, a, wa, col) in confetti:
            Y = y + vy * tt
            if Y < -20 or Y > H + 20 or tt < 0.9:
                continue
            X = x + vx * tt + 30 * math.sin(tt * 2 + a)
            an = a + wa * tt
            hx, hy = 9 * math.cos(an), 5 * math.sin(an)
            dd.polygon([(X - hx, Y - hy), (X + hy, Y - hx), (X + hx, Y + hy), (X - hy, Y + hx)], fill=col)
        emit(img)
    gt += POD

    # ---- таблица месяца
    if final_race:
        tab_rows = [(c, {"pts": state["alltime"][c].get("titles", 0)}) for c in [ch["code"] for ch in state["champions"]][-16:]]
        tab_title = "CHAMPIONS"
    else:
        tab_rows = league.sorted_table(state["table"])[:16]
        tab_title = f"{league.MONTHS_EN[d.month - 1]}  ·  TABLE"
    old_rank = {c: n for n, (c, _) in enumerate(league.sorted_table(prev_table))}
    days_left = (fdate - d).days
    for j in range(int(TAB * FPS)):
        if done():
            break
        tt = j / FPS
        img = cbg.copy()
        dd = ImageDraw.Draw(img)
        text_center(dd, W / 2, 34, tab_title, font(62), WHITE, 5)
        for n, (c, row) in enumerate(tab_rows):
            col, r = divmod(n, 8)
            ap = ease((tt - 0.2 - n * 0.06) / 0.35)
            if ap <= 0:
                continue
            x = 170 + col * 820 - (1 - ap) * 80
            y = 150 + r * 96
            fill = (255, 205, 70, 60) if n == 0 else (255, 255, 255, 18)
            ov = Image.new("RGBA", (760, 82), fill)
            img.paste(ov, (int(x), y), ov)
            dd.text((x + 18, y + 14), f"{n + 1}", font=font(40), fill=GOLD if n < 3 else WHITE)
            fl = flag_rect(c, 84, 63, 6)
            img.paste(fl, (int(x + 96), y + 10), fl)
            dd.text((x + 200, y + 12), A3[c], font=font(42), fill=WHITE)
            pts = str(row["pts"])
            pw = dd.textlength(pts, font=font(44))
            dd.text((x + 740 - pw, y + 12), pts, font=font(44), fill=GOLD)
            g = gained.get(c, 0)
            if g and not final_race:
                gs = f"+{g}"
                dd.text((x + 560, y + 22), gs, font=font(30), fill=GREEN)
            if not final_race and c in old_rank and old_rank[c] > n:
                dd.polygon([(x + 330, y + 50), (x + 346, y + 26), (x + 362, y + 50)], fill=GREEN)
        if final_race:
            foot = f"{league.MONTHS_EN[nd.month - 1]} STARTS TOMORROW"
        elif days_left == 0:
            foot = "MONTH FINAL TODAY"
        else:
            foot = f"MONTH FINAL  {fdate.day:02d}.{fdate.month:02d}  ·  TOP 32  ·  {days_left} DAYS LEFT"
        text_center(dd, W / 2, 940, foot, font(44), GOLD, 4)
        emit(img)
    gt += TAB

    # ---- следующая гонка (конечная заставка)
    for img in next_card_frames(cbg, nkind, nparts, race_no, NXT):
        if done():
            break
        emit(img)
    gt += NXT

    if FRAMES_MODE:
        log("всего секунд", nframes[0] / FPS)
        return
    out.close(mixer.final()[: int(nframes[0] / FPS * audio.SR) + 1000], sr=audio.SR)
    log(f"кадров {nframes[0]}, {nframes[0] / FPS / 60:.2f} мин, рендер {time.time() - t_start:.0f} с")

    # ---- описание и сохранение лиги
    a3w = A3[ranking[0]]
    if final_race:
        title = f"{league.MONTHS_EN[d.month - 1].title()} FINAL 🏆 32 Best Countries Marble Race – Who Is the Champion?"
    else:
        variants = [
            f"32 Countries Marble Race 🌍 Elimination #{race_no} – Who Wins?",
            f"Marble Race of 32 Countries #{race_no} 🏁 Only One Survives the Rings",
            f"Country Marble Elimination #{race_no} 🌍 7 Stages, 1 Winner",
            f"Which Country Wins? 32 Nations Marble Race #{race_no} 🔥",
            f"32 Flags, 7 Stages, 1 Champion 🏆 Country Marble Race #{race_no}",
        ]
        title = variants[race_no % len(variants)]
    desc = (f"Race #{race_no}: 32 countries, 7 stages, only one winner. 3 new races every day — the top 32 of the month "
            f"meet in the MONTH FINAL on {fdate.day:02d}.{fdate.month:02d}. Find your country and write in the comments "
            f"who you were cheering for! 👇\n\n#marblerace #countryballs #marblerun #satisfying #elimination #countries")
    meta = {"title": title, "description": desc, "race_no": race_no, "date": d.isoformat(), "kind": kind,
            "ranking": [A3[c] for c in ranking]}
    json.dump(meta, open(os.path.splitext(args.out)[0] + ".json", "w"), ensure_ascii=False, indent=1)
    if not args.no_save:
        league.save(state, args.state)
    log("победитель:", a3w)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--state", default="league_state.json")
    ap.add_argument("--out", default="race.mp4")
    ap.add_argument("--preview", type=float, default=0)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--frames", default="")
    ap.add_argument("--slot", type=int, default=1)
    build(ap.parse_args())
