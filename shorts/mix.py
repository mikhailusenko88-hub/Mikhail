"""Звук для Shorts с арены Flagball Arena: своя напряжённая музыка (минор, пульсирующий бас,
нарастание к концу раунда, «подъём» в последние секунды), звуки поеданий, отсчёт и фанфары победы
(разрешение в мажор). Инструменты — audio.py канала (свой синтез, без чужих прав).
Вход — events.json от записи, выход — wav."""
import json
import sys
import wave

import numpy as np

from audio import Mix, SR


def tense_section(mx, t0, t1, key=0, bpm=140, e0=0.35, e1=1.0):
    """Напряжённый луп: минор, бас восьмыми (к концу шестнадцатыми), бочка, хэты, тревожное остинато.
    Энергия растёт от e0 к e1 — к концу раунда музыка плотнее и громче."""
    beat = 60 / bpm
    bar = 4 * beat
    base = 110.0 * 2 ** (key / 12)          # A2
    prog = [0, 0, 8, 7]                     # i — i — VI — V (гармонический минор: V мажорная, тянет к развязке)
    fr = lambda s, o=0: base * 2 ** ((s + 12 * o) / 12)
    t, bi = t0, 0
    span = max(0.1, t1 - t0)
    while t < t1 - 0.05:
        root = prog[bi % 4]
        third = 4 if root == 7 else 3
        e = e0 + (e1 - e0) * min(1.0, (t - t0) / span)
        plen = min(bar, t1 - t)
        # тёмный пэд
        for s in (root, root + third, root + 7):
            mx.put(mx.music, mx.tone(fr(s, 1), plen, 0.028, decay=0.25, harm=(1, 0.35, 0.1), attack=0.35), t)
        # тревожное остинато: полутон над тоникой (b2) — «саспенс»
        motif = [0, 1, 0, third, 0, 1, 7, third] if root != 7 else [0, 1, 0, 4, 0, 1, 7, 4]
        for b in range(4):
            tb = t + b * beat
            if tb >= t1:
                break
            if b % 2 == 0 or e > 0.7:
                mx.put(mx.music, mx.kick(0.45 + 0.35 * e), tb)
            if b in (1, 3) and e > 0.45:
                mx.put(mx.music, mx.noise(0.16, 0.22 * e, 24), tb)
            sub = 4 if e > 0.8 else 2
            for h in range(sub):
                tt = tb + h * beat / sub
                if tt < t1:
                    mx.put(mx.music, mx.tone(fr(root, 0), beat / sub * 0.55, 0.17, decay=11, harm=(1, 0.7, 0.35, 0.15)), tt)
            for h in range(4):
                tt = tb + h * beat / 4
                if tt < t1:
                    mx.put(mx.music, mx.noise(0.035, (0.025 + 0.05 * e) * (1.5 if h == 2 else 1), 85, hp=True), tt)
            for h in range(2):
                tt = tb + h * beat / 2
                if tt < t1 and e > 0.3:
                    s = motif[(b * 2 + h) % 8]
                    mx.put(mx.music, mx.tone(fr(root + s, 2), 0.16, 0.035 + 0.03 * e, decay=12, harm=(1, 0.25)), tt)
        t += bar
        bi += 1


def riser(mx, t_end, length=7.0):
    """Нарастающий шум + свип вверх перед итогом раунда."""
    t0 = max(0.0, t_end - length)
    n = int((t_end - t0) * SR)
    if n <= 0:
        return
    x = np.linspace(0, 1, n, dtype=np.float32)
    amp = (x ** 2.2) * 0.2
    noise = mx.r.uniform(-1, 1, n).astype(np.float32)
    noise = np.diff(noise, prepend=0)              # светлее
    f = 180 * (1200 / 180) ** x
    sweep = np.sin(2 * np.pi * np.cumsum(f) / SR).astype(np.float32)
    mx.put(mx.music, amp * noise + amp * 0.5 * sweep, t0)


def heartbeat(mx, t0, t1):
    """Сердцебиение в последние секунды — тук-тук раз в секунду."""
    t = t0
    while t < t1 - 0.2:
        mx.put(mx.sfx, mx.kick(0.35), t)
        mx.put(mx.sfx, mx.kick(0.22), t + 0.22)
        t += 1.0


def outro(mx, t0, t1, key=0):
    """После победы — светлый мажор (снятие напряжения): аккорд, лёгкое арпеджио и мягкая бочка."""
    base = 220.0 * 2 ** (key / 12)
    for s in (0, 4, 7, 12):
        mx.put(mx.music, mx.tone(base * 2 ** (s / 12), t1 - t0, 0.08, decay=0.15, harm=(1, 0.3, 0.1), attack=0.08), t0)
    mx.put(mx.music, mx.kick(1.0), t0)
    beat = 60 / 140
    t, i = t0 + beat, 0
    arp = [0, 4, 7, 12, 16, 12, 7, 4]
    while t < t1 - 0.1:
        mx.put(mx.music, mx.tone(base * 2 * 2 ** (arp[i % 8] / 12), 0.25, 0.06, decay=8, harm=(1, 0.2)), t)
        if i % 2 == 0:
            mx.put(mx.music, mx.kick(0.35), t)
        t += beat / 2
        i += 1


def main(events_path, out_wav):
    ev = json.load(open(events_path, encoding='utf-8'))
    dur = float(ev['duration'])
    seed = int(ev.get('seed', 1))
    key = seed % 5
    mx = Mix(dur, seed=seed)
    win_at = ev.get('round_at')
    end = win_at if win_at else dur
    tense_section(mx, 0, end, key=key, bpm=140, e0=0.35, e1=1.0)
    if win_at:
        riser(mx, win_at, 7.0)
        heartbeat(mx, max(0.0, win_at - 10), win_at - 5.2)
        if dur - win_at > 0.3:
            outro(mx, win_at, dur, key=key)
    # поедания: «чпок» — чем больше съеденный, тем ниже и громче
    for e in ev.get('eats', []):
        t, m = float(e['t']), float(e.get('m', 10))
        if 0 <= t < dur:
            f = max(220.0, 900.0 - min(600.0, m * 6))
            vol = min(0.32, 0.12 + m / 400)
            mx.put(mx.sfx, mx.tone(f, 0.22, vol, decay=16, harm=(1, 0.4, 0.1)), t)
            mx.put(mx.sfx, mx.tone(f * 1.5, 0.12, vol * 0.5, decay=24, harm=(1,)), t + 0.03)
    for t, high in ev.get('beeps', []):
        if 0 <= t < dur:
            mx.beep(t, high=bool(high))
    if win_at and 0 <= win_at < dur:
        mx.fanfare(win_at)
    a = mx.final()[: int(dur * SR)]
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], axis=1)
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
