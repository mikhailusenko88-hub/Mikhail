"""Подмешать музыку под звук ударов: python3 mix_music.py sfx.wav music.wav out.wav [на_сколько_дБ_тише]
Громкость сравнивается по EBU R128 (ffmpeg ebur128), музыка ставится на N дБ ниже звука ударов (по умолчанию 7)."""
import re
import subprocess
import sys
import wave

import numpy as np

sfx_p, mus_p, out_p = sys.argv[1:4]
DB = float(sys.argv[4]) if len(sys.argv) > 4 else 7.0


def lufs(p):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", p, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


def read(p):
    w = wave.open(p)
    ch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), {2: np.int16, 4: np.int32}[sw]).astype(np.float64) / (2 ** (8 * sw - 1))
    x = x.reshape(-1, ch)
    if ch == 1:
        x = np.repeat(x, 2, 1)
    return x, sr


a, sr = read(sfx_p)
m, sr2 = read(mus_p)
assert sr == sr2, (sr, sr2)
la, lm = lufs(sfx_p), lufs(mus_p)
g = 10 ** ((la - DB - lm) / 20)
n = len(a)
mm = np.zeros_like(a)
mm[:min(n, len(m))] = m[:n] * g
y = a + mm
pk = np.abs(y).max()
if pk > 0.97:
    y *= 0.97 / pk
with wave.open(out_p, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes((y * 32767).astype(np.int16).tobytes())
print(f"удары {la:.1f} LUFS, музыка {lm:.1f} → {lm + 20 * np.log10(g):.1f} LUFS ({DB:.0f} дБ тише), пик {pk:.2f}")
