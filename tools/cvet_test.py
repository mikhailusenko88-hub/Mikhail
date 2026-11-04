"""Замер: сколько цвета теряет сборка видео. Кадры (таблица цветов + кадры героев) → кодирование → декодирование
«как плеер/YouTube» (BT.709 для HD) → ΔE2000 к оригиналу.

python3 cvet_test.py <папка_кадров_png> <папка_вывода>
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

W, H, FPS = 1920, 1080, 25
SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# имя, цвет sRGB — то, что важно в «Мультиках»
PATCHES = [
    ("лоб Барсика", (152, 126, 84)), ("рыжая шерсть", (205, 120, 52)), ("тёмная шерсть", (92, 48, 22)), ("белая грудка", (236, 226, 208)),
    ("шарф синий", (28, 92, 222)), ("трава", (96, 152, 54)), ("трава в тени", (38, 78, 30)), ("глаза зелёные", (70, 170, 60)),
    ("небо", (168, 200, 232)), ("ошейник Рона", (196, 28, 32)), ("кепка Рона", (246, 246, 244)), ("нос розовый", (238, 150, 160)),
    ("туман леса", (150, 168, 160)), ("закат", (250, 150, 70)), ("жёлтый", (240, 210, 40)), ("фиолетовый", (120, 60, 170)),
    ("бирюза", (40, 170, 170)), ("кожа", (230, 180, 150)), ("серый 18%", (118, 118, 118)), ("почти чёрный", (18, 16, 14)),
]


def chart():
    im = np.zeros((H, W, 3), np.uint8)
    cols, rows = 5, 4
    pw, ph = W // cols, (H - 180) // rows
    for k, (_, c) in enumerate(PATCHES):
        r, q = divmod(k, cols)
        im[r * ph:(r + 1) * ph, q * pw:(q + 1) * pw] = c
    # полоска «шерсть на траве»: волоски 1 px рыжие на зелёном, и наоборот
    y0 = rows * ph
    band = np.zeros((H - y0, W, 3), np.uint8)
    band[:] = (96, 152, 54)
    band[:, ::2] = (205, 120, 52)
    band[:, W // 2:] = (205, 120, 52)
    band[:, W // 2::3] = (96, 152, 54)
    im[y0:] = band
    return im, (cols, rows, pw, ph, y0)


def frames():
    """Кадры теста: таблица + кадры героев (1280×720 → 1920×1080). Чтобы кодер работал как на живом ролике,
    кадр каждый раз чуть сдвигается (панорама 2 px/кадр) — сравнение идёт с тем же сдвинутым оригиналом."""
    ch, geo = chart()
    srcs = [("таблица", Image.fromarray(ch))]
    for p in sorted(SRC.glob("*.png")):
        srcs.append((p.stem, Image.open(p).convert("RGB").resize((int(W * 1.03), int(H * 1.03)), Image.LANCZOS)))
    seq, names = [], []
    for name, im in srcs:
        for i in range(FPS):
            if name == "таблица":
                seq.append(np.asarray(im)); names.append(name); continue
            dx = 2 * i
            seq.append(np.asarray(im.crop((dx, 10, dx + W, 10 + H)))); names.append(name)
    return seq, names, geo


def enc(seq, path, args):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-"] + args + [str(path)], stdin=subprocess.PIPE)
    for f in seq:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
    p.stdin.close(); p.wait()


def dec(path, matrix="bt709"):
    """Как плеер: HD-видео без меток и с меткой 709 — матрица BT.709, ограниченный диапазон."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf",
                        f"scale=in_color_matrix={matrix}:in_range=tv:flags=bicubic+accurate_rnd+full_chroma_int",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3)


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=pix_fmt,color_space,color_primaries,color_transfer,color_range,bit_rate", "-of", "json", str(path)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]


def de(a, b):
    return deltaE_ciede2000(rgb2lab(a / 255.0), rgb2lab(b / 255.0))


def measure(seq, names, geo, got):
    cols, rows, pw, ph, y0 = geo
    res = {"патчи": {}, "кадры": {}}
    k = FPS // 2
    a, b = seq[k].astype(np.float64), got[k].astype(np.float64)
    for j, (nm, _) in enumerate(PATCHES):
        r, q = divmod(j, cols)
        sl = (slice(r * ph + 20, (r + 1) * ph - 20), slice(q * pw + 20, (q + 1) * pw - 20))
        res["патчи"][nm] = round(float(de(a[sl].mean((0, 1))[None, None], b[sl].mean((0, 1))[None, None])[0, 0]), 2)
    sl = (slice(y0 + 10, H - 10), slice(10, W // 2 - 10))
    res["волоски 1px"] = round(float(de(a[sl], b[sl]).mean()), 2)
    for nm in dict.fromkeys(names):
        if nm == "таблица":
            continue
        idx = [i for i, n in enumerate(names) if n == nm]
        d = np.concatenate([de(seq[i].astype(np.float64), got[i].astype(np.float64)).ravel() for i in idx[5::6]])
        res["кадры"][nm] = {"среднее": round(float(d.mean()), 2), "95%": round(float(np.percentile(d, 95)), 2)}
    return res


if __name__ == "__main__":
    seq, names, geo = frames()
    VARIANTS = {
        # как сейчас: fastvid.Writer (Shorts, акварель, шарики) — матрица по умолчанию (BT.601), меток нет
        "сейчас_fastvid": ["-c:v", "libx264", "-preset", "fast", "-b:v", "5500k", "-maxrate", "7150k", "-bufsize", "11000k",
                           "-pix_fmt", "yuv420p"],
        # как сейчас: Honeycomb / soty — то же, 10 Мбит/с
        "сейчас_honeycomb": ["-c:v", "libx264", "-preset", "medium", "-b:v", "10000k", "-maxrate", "13000k", "-bufsize", "20000k",
                             "-pix_fmt", "yuv420p"],
        # исправлено: матрица BT.709 + метки 709 + точное округление
        "стало_709": ["-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=bicubic+accurate_rnd+full_chroma_int,format=yuv420p",
                      "-c:v", "libx264", "-preset", "fast", "-b:v", "5500k", "-maxrate", "7150k", "-bufsize", "11000k",
                      "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"],
    }
    report = {}
    for nm, args in VARIANTS.items():
        p = OUT / f"{nm}.mp4"
        enc(seq, p, args)
        got = dec(p)
        report[nm] = {"метки": probe(p), "МБ": round(p.stat().st_size / 1e6, 1), **measure(seq, names, geo, got)}
        Image.fromarray(got[FPS + FPS // 2]).save(OUT / f"{nm}_кадр.png")
        print(nm, json.dumps(report[nm], ensure_ascii=False), flush=True)
    Image.fromarray(seq[FPS + FPS // 2]).save(OUT / "оригинал_кадр.png")
    Image.fromarray(seq[FPS // 2]).save(OUT / "таблица.png")
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
