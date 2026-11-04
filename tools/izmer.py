"""Замер mp4 с Mac: ΔE2000 к оригиналу. Плеер читает матрицу по метке, без метки (HD) — BT.709.
python3 izmer.py <папка_кадров> <папка_mp4> [ещё папки…]"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

W, H, FPS = 1920, 1080, 25
SRC = Path(sys.argv[1])
NAMES = ["лоб Барсика", "рыжая шерсть", "тёмная шерсть", "белая грудка", "шарф синий", "трава", "трава в тени", "глаза зелёные",
         "небо", "ошейник Рона", "кепка Рона", "нос розовый", "туман леса", "закат", "жёлтый", "фиолетовый", "бирюза", "кожа",
         "серый 18%", "почти чёрный"]


def seq():
    out, names = [], []
    for p in sorted(SRC.glob("*.png")):
        im = np.asarray(Image.open(p).convert("RGB"))
        for i in range(FPS):
            out.append(im if im.shape[1] == W else im[10:10 + H, 2 * i:2 * i + W]); names.append(p.stem)
    return out, names


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=pix_fmt,color_space,color_primaries,color_transfer,color_range,bit_rate,profile", "-of", "json", str(p)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]


def dec(p, tags):
    cs = tags.get("color_space", "")
    m = "bt601" if cs in ("smpte170m", "bt470bg") else "bt709"
    rng = "pc" if tags.get("color_range") == "pc" else "tv"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(p), "-vf",
                        f"scale=in_color_matrix={m}:in_range={rng}:flags=bicubic+accurate_rnd+full_chroma_int",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3), m


def de(a, b):
    return deltaE_ciede2000(rgb2lab(a / 255.0), rgb2lab(b / 255.0))


def measure(S, names, got):
    cols, rows = 5, 4
    pw, ph = W // cols, (H - 180) // rows
    y0 = rows * ph
    a, b = S[12].astype(np.float64), got[12].astype(np.float64)
    res = {"патчи": {}}
    for j, nm in enumerate(NAMES):
        r, q = divmod(j, cols)
        sl = (slice(r * ph + 20, (r + 1) * ph - 20), slice(q * pw + 20, (q + 1) * pw - 20))
        res["патчи"][nm] = round(float(de(a[sl].mean((0, 1))[None, None], b[sl].mean((0, 1))[None, None])[0, 0]), 2)
    p = list(res["патчи"].values())
    res["патчи макс"] = max(p); res["патчи средн"] = round(float(np.mean(p)), 2)
    res["волоски 1px"] = round(float(de(a[y0 + 10:H - 10, 10:W // 2 - 10], b[y0 + 10:H - 10, 10:W // 2 - 10]).mean()), 2)
    res["кадры"] = {}
    for nm in dict.fromkeys(names):
        if nm.startswith("00_"):
            continue
        idx = [i for i, n in enumerate(names) if n == nm][5::6]
        d = np.concatenate([de(S[i].astype(np.float64), got[i].astype(np.float64)).ravel() for i in idx])
        res["кадры"][nm] = {"среднее": round(float(d.mean()), 2), "95%": round(float(np.percentile(d, 95)), 2)}
    return res


def jpeg_sampling(p):
    b = Path(p).read_bytes()
    i = 2
    while i < len(b):
        mk, ln = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
        if mk in (0xC0, 0xC1, 0xC2):
            n = b[i + 9]
            f = [(b[i + 11 + 3 * k] >> 4, b[i + 11 + 3 * k] & 15) for k in range(n)]
            return "4:4:4" if f[0] == (1, 1) else "4:2:0" if f[0] == (2, 2) else "4:2:2" if f[0] == (2, 1) else str(f)
        i += 2 + ln
    return "?"


if __name__ == "__main__":
    S, names = seq()
    rep = {}
    for d in sys.argv[2:]:
        d = Path(d)
        for j in sorted(d.glob("*.jpg")):
            rep[f"{d.name}/{j.name}"] = {"JPEG": jpeg_sampling(j), "КБ": j.stat().st_size // 1024}
        for p in sorted(d.glob("*.mp4")):
            t = probe(p)
            got, m = dec(p, t)
            r = {"метки": {k: v for k, v in t.items() if k != "bit_rate"}, "плеер читает как": m,
                 "Мбит/с": round(int(t.get("bit_rate", 0)) / 1e6, 1), **measure(S, names, got)}
            if m == "bt709" and not t.get("color_space"):
                got6, _ = dec(p, {"color_space": "smpte170m"})
                r["если читать как 601"] = measure(S, names, got6)["патчи макс"]
            rep[f"{d.name}/{p.stem}"] = r
            Image.fromarray(got[FPS + 12]).save(d / f"{p.stem}_kadr.png")
            print(p.stem, json.dumps({k: r[k] for k in r if k != "патчи"}, ensure_ascii=False), flush=True)
    Path(sys.argv[2]).parent.joinpath("report_mac.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if "JPEG" in v}, ensure_ascii=False))
