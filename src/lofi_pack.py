#!/usr/bin/env python3
"""Ещё лоу-фай и бум-бэп треки со своими мелодиями (для «Почему так?»).
Инструменты — из skazka_remix.py. Запуск: python3 lofi_pack.py OUT_DIR [фильтр]
"""
import os
import sys

from scipy.signal import sosfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kz_music import Mix, _sos, finish, flute, master_mp3  # noqa: E402
from ru_music import gusli  # noqa: E402
from skazka_remix import bass_808, clap, glock, hat, kick909, rhodes, snare, vinyl  # noqa: E402


def lp(x, f):
    return sosfilt(_sos("low", f), x)


def lofi_track(chords, mel, bpm, nb, seed, lead="glock"):
    """chords: 8 × (корень, аккорд-септаккорд); mel: 4 фразы по 2 такта в восьмых."""
    beat = 60 / bpm
    e8, bar = beat / 2, 4 * beat
    M = Mix(nb * bar, seed)
    rng = M.rng
    M.add(vinyl(nb * bar + 2, rng), 0.0, 0.03, rev=0.0)
    sw = e8 * 0.18
    for b in range(nb):
        t0 = b * bar
        root, v = chords[b % 8]
        last = b == nb - 1
        M.add(lp(rhodes(v, bar * (0.6 if last else 0.95), rng), 3500), t0, 0.22, pan=-0.1, rev=0.35)
        M.add(bass_808(root, beat * 1.6 if not last else 2.5, rng, drive=1.3), t0, 0.32, rev=0.05)
        if last:
            break
        M.add(bass_808(root, beat * 0.8, rng, drive=1.3), t0 + 2.5 * beat, 0.24, rev=0.05)
        if b >= 2:
            M.add(lp(kick909(rng, punch=0.3), 2500), t0, 0.40)
            M.add(lp(kick909(rng, punch=0.3), 2500), t0 + 2.5 * beat, 0.30)
            for k in (1, 3):
                M.add(snare(rng, tone=200, dec=18, lp=4500), t0 + k * beat, 0.20, rev=0.25)
            for i in range(8):
                M.add(lp(hat(rng), 9000), t0 + i * e8 + (sw if i % 2 else 0), 0.07 if i % 2 else 0.09, pan=0.3)
        if b >= 4 and b % 2 == 0 and not (12 <= b < 14):
            for m, s, l in mel[(b % 8) // 2]:
                ts = t0 + s * e8 + rng.uniform(0, 0.015)
                if lead == "glock":
                    M.add(lp(glock(m, rng), 5000), ts, 0.20, pan=0.2, rev=0.45)
                else:
                    M.add(lp(rhodes([m], l * e8, rng, rel=0.5), 4000), ts, 0.20, pan=0.2, rev=0.4)
                if b >= 14:
                    M.add(lp(flute(m - 12, l * e8 * 0.9, rng), 3500), ts, 0.10, pan=-0.25, rev=0.45)
    return M


def boombap_track(chords, mel, bpm, nb, seed, sample="gusli", lead="glock"):
    """chords: 8 × (корень, трезвучие); mel: 4 фразы по 2 такта в восьмых."""
    beat = 60 / bpm
    e8, bar = beat / 2, 4 * beat
    M = Mix(nb * bar, seed)
    rng = M.rng
    M.add(vinyl(nb * bar + 2, rng), 0.0, 0.022, rev=0.0)
    sw = e8 * 0.12
    for b in range(nb):
        t0 = b * bar
        root, v = chords[b % 8]
        last = b == nb - 1
        if sample == "gusli":
            for pos, m in ((0, v[0] + 12), (3, v[2] + 12), (6, v[1] + 12)):
                M.add(lp(gusli(m, 1.4, 0.7, rng=rng), 4500), t0 + pos * e8, 0.16, pan=-0.2, rev=0.35)
        else:
            for pos in (0, 3, 6):
                M.add(lp(rhodes([m - 12 for m in v], e8 * 1.5, rng, rel=0.3), 3000), t0 + pos * e8, 0.15,
                      pan=-0.2, rev=0.3)
        M.add(lp(rhodes([m - 12 for m in v], bar * 0.9, rng), 2200), t0, 0.08, rev=0.3)
        M.add(bass_808(root, beat * 1.4 if not last else 2.5, rng, drive=1.6), t0, 0.34)
        if last:
            M.add(kick909(rng, punch=0.6), t0, 0.5)
            break
        M.add(bass_808(root, beat * 0.9, rng, drive=1.6), t0 + 2.5 * beat, 0.26)
        if b >= 2:
            for tb, g in ((0, 0.5), (1.5, 0.34), (2.5, 0.42)):
                M.add(lp(kick909(rng, punch=0.8, dist=1.5), 3500), t0 + tb * beat, g)
            for k in (1, 3):
                M.add(snare(rng, tone=190, dec=12, lp=7000), t0 + k * beat, 0.30, rev=0.2)
                M.add(clap(rng), t0 + k * beat, 0.08, rev=0.2)
            for i in range(8):
                M.add(hat(rng), t0 + i * e8 + (sw if i % 2 else 0), 0.08 if i % 2 else 0.11, pan=0.3)
        if b >= 8 and b % 2 == 0 and not (16 <= b < 18):
            for m, s, l in mel[(b % 8) // 2]:
                ts = t0 + s * e8
                if lead == "glock":
                    M.add(lp(glock(m, rng), 6000), ts, 0.17, pan=0.25, rev=0.4)
                else:
                    M.add(lp(flute(m, l * e8 * 0.9, rng), 5000), ts, 0.16, pan=0.25, rev=0.4)
    return M


def dbl(four):
    return four + four


def vechernij_chaj():
    """Лоу-фай «Вечерний чай», 78 BPM, до мажор: Fmaj7 Em7 Dm7 Cmaj7."""
    ch = dbl([(41, [53, 57, 60, 64]), (40, [52, 55, 59, 62]), (38, [50, 53, 57, 60]), (36, [48, 52, 55, 59])])
    mel = [
        [(76, 0, 3), (74, 3, 1), (72, 4, 4), (71, 8, 6), (67, 14, 2)],
        [(69, 0, 3), (72, 3, 1), (74, 4, 4), (71, 8, 8)],
        [(72, 0, 2), (76, 2, 2), (79, 4, 4), (74, 8, 4), (71, 12, 4)],
        [(69, 0, 4), (65, 4, 2), (69, 6, 2), (67, 8, 8)],
    ]
    return lofi_track(ch, mel, 78, 21, 41, lead="glock")


def dozhd():
    """Лоу-фай «Дождь», 74 BPM, ля минор: Am9 Fmaj7 Cmaj7 G6."""
    ch = dbl([(45, [55, 59, 60, 64]), (41, [53, 57, 60, 64]), (36, [48, 52, 55, 59]), (43, [50, 55, 59, 64])])
    mel = [
        [(72, 0, 4), (71, 4, 2), (69, 6, 2), (64, 8, 8)],
        [(67, 0, 4), (71, 4, 4), (74, 8, 6), (71, 14, 2)],
        [(76, 0, 2), (72, 2, 2), (71, 4, 2), (69, 6, 2), (72, 8, 4), (69, 12, 4)],
        [(67, 0, 6), (64, 6, 2), (62, 8, 8)],
    ]
    return lofi_track(ch, mel, 74, 20, 42, lead="rhodes")


def staryj_dvor():
    """Бум-бэп «Старый двор», 88 BPM, ре минор: Dm Bb Gm A7."""
    ch = dbl([(38, [62, 65, 69]), (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 67])])
    mel = [
        [(74, 0, 2), (77, 2, 2), (76, 4, 2), (74, 6, 2), (70, 8, 6), (69, 14, 2)],
        [(67, 0, 4), (70, 4, 2), (74, 6, 2), (73, 8, 8)],
        [(81, 0, 4), (77, 4, 4), (74, 8, 4), (77, 12, 4)],
        [(79, 0, 2), (74, 2, 2), (70, 4, 4), (69, 8, 4), (73, 12, 4)],
    ]
    return boombap_track(ch, mel, 88, 24, 43, sample="gusli", lead="glock")


def motor():
    """Бум-бэп «Мотор», 94 BPM, ми минор: Em C G D."""
    ch = dbl([(40, [64, 67, 71]), (36, [64, 67, 72]), (43, [62, 67, 71]), (38, [62, 66, 69])])
    mel = [
        [(79, 0, 3), (76, 3, 1), (71, 4, 4), (72, 8, 4), (76, 12, 4)],
        [(74, 0, 3), (71, 3, 1), (67, 4, 4), (69, 8, 6), (66, 14, 2)],
        [(71, 0, 2), (74, 2, 2), (76, 4, 4), (79, 8, 4), (76, 12, 4)],
        [(74, 0, 4), (79, 4, 4), (78, 8, 8)],
    ]
    return boombap_track(ch, mel, 94, 25, 44, sample="rhodes", lead="flute")


TRACKS = [
    ("lofi_01_Vecherniy_chay", vechernij_chaj),
    ("lofi_02_Dozhd", dozhd),
    ("bit_01_Staryy_dvor", staryj_dvor),
    ("bit_02_Motor", motor),
]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2:]
    for name, fn in TRACKS:
        if only and not any(o in name for o in only):
            continue
        M = fn()
        wav = os.path.join(out, name + ".wav")
        finish(M, wav, t60=2.0)
        master_mp3(wav, os.path.join(out, name + ".mp3"))
        os.remove(wav)
        print("ok", name, round(M.len, 1), "s", flush=True)
