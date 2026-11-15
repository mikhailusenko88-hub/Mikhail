import random, struct, subprocess, sys
import numpy as np
import layout as L

def run(n=1000, T=24.0, seed=1, hz=600, fps=30):
    rnd = random.Random(seed)
    pts = L.balls(n, rnd)
    lines = [f"{n} {L.R} 1500 {hz} {fps} {T}"] + [f"{x:.2f} {y:.2f}" for x, y in pts]
    P = L.pegs(); lines += [str(len(P))] + [f"{a} {b} {c}" for a, b, c in P]
    S = L.segs(); lines += [str(len(S))] + [" ".join(f"{v}" for v in s) for s in S]
    K = L.spinners(); lines += [str(len(K))] + [" ".join(f"{v}" for v in k) for k in K]
    lines += [" ".join(str(v) for v in L.CUP)]
    p = subprocess.run(["./mass_sim"], input="\n".join(lines).encode(), capture_output=True, check=True)
    frames = int(T * fps); per = n * 8 + 2
    buf = p.stdout
    assert len(buf) == frames * per, (len(buf), frames * per)
    pos = np.empty((frames, n, 2), np.float32); hits = np.empty(frames, np.int32)
    for f in range(frames):
        o = f * per
        pos[f] = np.frombuffer(buf, np.float32, n * 2, o).reshape(n, 2)
        hits[f] = struct.unpack_from("<H", buf, o + n * 8)[0]
    return pos, hits

if __name__ == "__main__":
    import time
    t = time.time()
    pos, hits = run(seed=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    print("sim", round(time.time() - t, 1), "s")
    x0, x1, yt, yb = L.CUP
    for f in range(0, len(pos), 60):
        p = pos[f]; alive = (p[:, 0] > -500).sum()
        inc = ((p[:, 0] > x0) & (p[:, 0] < x1) & (p[:, 1] > yt - 4) & (p[:, 1] < yb)).sum()
        hop = ((p[:, 1] < 600) & (p[:, 1] > -500)).sum()
        print(f"t={f/30:4.1f} alive={alive} in_hopper={hop} in_cup={inc} hits={hits[f]}")
