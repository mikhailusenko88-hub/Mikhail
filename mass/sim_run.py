import random
import struct
import subprocess
from pathlib import Path

import numpy as np

import layout as L

HERE = Path(__file__).resolve().parent


def run(scene, n=1000, T=24.0, seed=1, hz=600, fps=30):
    rnd = random.Random(seed)
    pts = scene.balls(n, rnd)
    lines = [f"{n} {L.R} 1500 {hz} {fps} {T}"] + [f"{x:.2f} {y:.2f}" for x, y in pts]
    P = scene.pegs(); lines += [str(len(P))] + [f"{a} {b} {c}" for a, b, c in P]
    S = scene.segs(); lines += [str(len(S))] + [" ".join(f"{v:.2f}" for v in s) for s in S]
    K = scene.spinners(); lines += [str(len(K))] + [" ".join(f"{v:.3f}" for v in k) for k in K]
    lines += [" ".join(str(v) for v in scene.cup)]
    p = subprocess.run([str(HERE / "mass_sim")], input="\n".join(lines).encode(), capture_output=True, check=True)
    frames, per = int(T * fps), n * 8 + 2
    buf = p.stdout
    assert len(buf) == frames * per, (len(buf), frames * per)
    pos = np.empty((frames, n, 2), np.float32)
    hits = np.empty(frames, np.int32)
    for f in range(frames):
        o = f * per
        pos[f] = np.frombuffer(buf, np.float32, n * 2, o).reshape(n, 2)
        hits[f] = struct.unpack_from("<H", buf, o + n * 8)[0]
    return pos, hits
