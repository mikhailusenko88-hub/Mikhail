#!/usr/bin/env python3
"""Проба героя из настоящего движка: «сейчас → свой голос» по фразам. python3 hero_ab.py <папка dub> <герой> <имя своего> <подпись> <куда.mp4> [eq]"""
import json, subprocess, sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")); os.chdir(sys.path[0])
import svoy_proba as P
SR = 48000
font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def load(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()

def trim(x):
    hop = 480; n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    idx = np.where(e > e.max() * 10 ** (-40 / 20))[0]
    a, b = max(0, idx[0] - 6) * hop, min(n, idx[-1] + 12) * hop
    return x[a:b]

def main(dub, hero, own, label, outp, eq=False, npair=6):
    L = json.load(open(f"{dub}/lines.json", encoding="utf-8"))["lines"]
    by = {}
    for l in L:
        if not l.get("vocal"):
            by.setdefault(l["name"], []).append(l)
    H = [trim(load(f"{dub}/lines/{l['i']:03d}.wav")) for l in by[hero][:7]]
    O = [trim(load(f"{dub}/lines/{l['i']:03d}.wav")) for l in by[own][:7]]
    info = {"bands_before": P.bands(O, H)}
    if eq:
        f0 = 200.0
        cen, gs = P.eq_design(O, H, f0=f0)
        O = [P.eq_apply(o, cen, gs) for o in O]
        info["bands_after"] = P.bands(O, H); info["eq"] = {int(c): round(float(g), 1) for c, g in zip(cen[::4], gs[::4])}
    sil = lambda s: np.zeros(int(SR * s), dtype=np.float32)
    track, marks, t0 = [sil(0.5)], [], 0.5
    for j in range(min(npair, len(H), len(O))):
        a, b = P.level(H[j]), P.level(O[j])
        marks.append((j, "t", t0, t0 + len(a) / SR)); track += [a, sil(0.45)]; t0 += len(a) / SR + 0.45
        marks.append((j, "w", t0, t0 + len(b) / SR)); track += [b, sil(0.9)]; t0 += len(b) / SR + 0.9
    x = np.concatenate(track)
    os.makedirs("/tmp/hab", exist_ok=True)
    x16 = (np.clip(x, -1, 1) * 32767).astype("<i2")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "/tmp/hab/a.wav"], input=x16.tobytes(), check=True)
    total = len(x) / SR
    lab = {"t": f"СЕЙЧАС: {hero}", "w": f"СВОЙ ГОЛОС: {label}"}; col = {"t": "0xbbbbbb", "w": "0x7CFC9A"}
    vf = []
    for j, tag, a, b in marks:
        for nm, text, size, y, c in ((f"l{tag}", lab[tag], 46 if len(lab[tag]) < 26 else 36, "h/2-60", col[tag]), (f"n{j}", f"фраза {j + 1} из {len(marks) // 2}", 30, "h/2+30", "0x8899aa")):
            p = f"/tmp/hab/pt_{nm}.txt"; open(p, "w", encoding="utf-8").write(text)
            vf.append(f"drawtext=fontfile={font}:textfile={p}:fontsize={size}:fontcolor={c}:x=(w-text_w)/2:y={y}:enable='between(t,{a:.3f},{b:.3f})'")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", f"{total:.3f}", "-i", "color=c=0x1e2230:s=1080x1080:r=25", "-i", "/tmp/hab/a.wav", "-vf", ",".join(vf),
                    "-t", f"{total:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-tune", "stillimage", "-af", "volume=5.5dB,alimiter=limit=0.94:level=disabled", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-ac", "1", "-movflags", "+faststart", outp], check=True)
    print(outp, f"{total:.1f} с", info)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], eq=len(sys.argv) > 6 and sys.argv[6] == "eq")
