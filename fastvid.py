"""fastvid — быстрый движок для генерируемых видео (Shorts 1080×1920)."""
import subprocess
import time
import wave

import numpy as np
from PIL import Image


class Writer:
    """Пишет кадры (PIL RGB или uint8 HxWx3) прямо в ffmpeg; звук добавляется в конце."""
    def __init__(self, path, w=1080, h=1920, fps=30, bitrate="5500k", preset="fast"):
        self.path, self.w, self.h, self.fps = path, w, h, fps
        self.tmp = str(path) + ".video.mp4"
        self.t0 = time.time()
        self.n = 0
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
             "-r", str(fps), "-i", "-",
             # цвет: матрица BT.709 + метки — так HD и Shorts читают YouTube и телефоны (без этого ffmpeg писал BT.601: ΔE до 6,5)
             "-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=bicubic+accurate_rnd+full_chroma_int,format=yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
             "-c:v", "libx264", "-preset", preset, "-b:v", bitrate,
             "-maxrate", str(int(bitrate[:-1]) * 13 // 10) + "k", "-bufsize", str(int(bitrate[:-1]) * 2) + "k",
             "-pix_fmt", "yuv420p", self.tmp], stdin=subprocess.PIPE)

    def add(self, frame):
        if isinstance(frame, Image.Image):
            if frame.size != (self.w, self.h):
                frame = frame.resize((self.w, self.h), Image.BILINEAR)
            frame = np.asarray(frame.convert("RGB"))
        self.p.stdin.write(np.ascontiguousarray(frame, np.uint8).tobytes())
        self.n += 1
        if self.n % 150 == 0:
            print(f"кадр {self.n}, {time.time() - self.t0:.0f} с", flush=True)

    def close(self, audio=None, sr=44100):
        """audio — numpy float моно; без него видео без звука."""
        self.p.stdin.close()
        self.p.wait()
        if audio is None:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", self.tmp, "-c", "copy",
                            "-movflags", "+faststart", str(self.path)], check=True)
        else:
            wav = str(self.path) + ".wav"
            a = audio / max(1e-9, float(np.max(np.abs(audio)))) * 0.88
            with wave.open(wav, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
                wf.writeframes((a * 32767).astype(np.int16).tobytes())
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", self.tmp, "-i", wav, "-c:v", "copy",
                            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(self.path)],
                           check=True)
        print(f"готово: {self.n} кадров за {time.time() - self.t0:.0f} с")


def paste(img, sprite, x, y):
    """Вставить RGBA-спрайт в кадр с обрезкой по краям."""
    W, H = img.size
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(sprite.size[0], W - x), min(sprite.size[1], H - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    part = sprite.crop((sx0, sy0, sx1, sy1))
    img.paste(part, (x + sx0, y + sy0), part)


def camera_window(cx, cy, zoom, w=1080, h=1920):
    """Окно камеры (x0, y0, cw, ch) — обсчитывай только его, потом resize."""
    cw, ch = int(w / zoom), int(h / zoom)
    x0 = int(min(max(cx - cw / 2, 0), w - cw))
    y0 = int(min(max(cy - ch / 2, 0), h - ch))
    return x0, y0, cw, ch


class GrainPool:
    """Зерно «камеры»: заготовки по кругу."""
    def __init__(self, w=1080, h=1920, n=6, sigma=3.2):
        self.g = [np.random.default_rng(300 + k).normal(0, sigma, (h // 2, w // 2, 1)).astype(np.int16)
                  .repeat(2, 0).repeat(2, 1) for k in range(n)]

    def apply(self, img, i):
        arr = np.asarray(img, np.int16) + self.g[i % len(self.g)]
        return np.clip(arr, 0, 255).astype(np.uint8)


class Audio:
    """Синтез звука: put(сигнал, время), tone, noise_burst."""
    def __init__(self, seconds, sr=44100, seed=9):
        self.sr = sr
        self.a = np.zeros(int((seconds + 0.5) * sr))
        self.r = np.random.default_rng(seed)

    def put(self, sig, at):
        s = int(at * self.sr)
        if 0 <= s < len(self.a):
            self.a[s:s + len(sig)] += sig[:len(self.a) - s]

    def tone(self, freq, dur, vol, decay=4.0, h2=0.25):
        tt = np.arange(int(dur * self.sr)) / self.sr
        env = np.exp(-tt * decay) * np.minimum(1, tt * 300)
        return vol * env * (np.sin(2 * np.pi * freq * tt) + h2 * np.sin(4 * np.pi * freq * tt))

    def noise_burst(self, dur, vol, decay=8.0, smooth=3):
        m = int(dur * self.sr)
        x = self.r.uniform(-1, 1, m)
        if smooth > 1:
            x = np.convolve(x, np.ones(smooth) / smooth, mode="same")
        tt = np.arange(m) / self.sr
        return vol * x / (np.abs(x).max() + 1e-9) * np.exp(-tt * decay)
