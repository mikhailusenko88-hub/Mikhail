# Образцы-записи для подбора своего голоса (26.11.2026): образец, которого нет в моделях Silero, — готовые записи по тексту.
# Пик: голос Apple (женский) — ТОЛЬКО МЕРКА (правило Михаила: несвободный голос в ролики не идёт, клонировать по записи нельзя);
# записи делает apple-ref.yml на Маке (cast11/apple_jobs.json → cast11/apple/p100/<sha1[:12]>.flac).
import hashlib, os, subprocess

import numpy as np

REC = {"pik": "cast11/apple/p100"}


def key(text):
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def rec(target, text, sr=48000):
    """Запись образца для фразы (float32, sr, моно, тишина по краям срезана) или None, если образец — диктор модели."""
    if target not in REC:
        return None
    p = os.path.join(REC[target], key(text) + ".flac")
    if not os.path.exists(p):
        raise FileNotFoundError(f"нет записи образца {target} для фразы: {text}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    fr = sr // 100
    e = np.array([np.sqrt(np.mean(a[i:i + fr] ** 2) + 1e-12) for i in range(0, max(1, len(a) - fr), fr)])
    on = np.where(20 * np.log10(e / (e.max() + 1e-12)) > -45)[0]
    if len(on):
        a = a[max(0, on[0] * fr - sr // 20): min(len(a), (on[-1] + 1) * fr + sr // 20)]
    return a
