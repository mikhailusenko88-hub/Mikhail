"""Свои звуковые акценты для роликов «Почему так» (синтез numpy, без чужих библиотек).
make(kind, path) -> wav 44100 Гц: whoosh (крючок), heartbeat (жуткое), alarm (нельзя), buzz (это миф),
rise (рекорд), ding (концовка), tick (смена фразы)."""
import math
import wave

import numpy as np

SR = 44100


def _env(n, a=0.01, r=0.2):
    e = np.ones(n)
    ia, ir = int(SR * a), int(SR * r)
    if ia:
        e[:ia] = np.linspace(0, 1, ia)
    if ir:
        e[-ir:] *= np.linspace(1, 0, ir)
    return e


def _save(x, path):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def whoosh(d=0.7):
    n = int(SR * d); t = np.arange(n) / SR
    noise = np.random.default_rng(1).standard_normal(n)
    # полосовой «свист» с подъёмом частоты: простой резонатор
    y = np.zeros(n); b1 = b2 = 0.0
    for i in range(n):
        f = 300 + 2500 * (i / n) ** 2
        r = 0.985
        c = 2 * r * math.cos(2 * math.pi * f / SR)
        y[i] = noise[i] * 0.05 + c * b1 - r * r * b2
        b2, b1 = b1, y[i]
    y /= (np.abs(y).max() + 1e-9)
    return y * _env(n, 0.05, 0.35) * 0.5


def heartbeat():
    def thump(t0, amp):
        n = int(SR * 0.18); t = np.arange(n) / SR
        f = 55 * np.exp(-t * 6) + 35
        return t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * amp
    total = int(SR * 1.2); y = np.zeros(total)
    for t0, s in (thump(0.0, 0.9), thump(0.22, 0.6), thump(0.75, 0.9), thump(0.97, 0.6)):
        i = int(t0 * SR); y[i:i + len(s)] += s
    return y


def alarm():
    n = int(SR * 0.45); t = np.arange(n) / SR
    y = np.sign(np.sin(2 * np.pi * 440 * t)) * 0.25 + np.sin(2 * np.pi * 880 * t) * 0.2
    gate = (np.sin(2 * np.pi * 7 * t) > 0).astype(float)
    return y * gate * _env(n, 0.005, 0.1)


def buzz():
    n = int(SR * 0.35); t = np.arange(n) / SR
    y = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.3 + np.sin(2 * np.pi * 165 * t) * 0.15
    return y * _env(n, 0.005, 0.12)


def rise():
    n = int(SR * 0.9); t = np.arange(n) / SR
    f = 200 * (2 ** (t / 0.9 * 2))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * 0.12
    return y * _env(n, 0.05, 0.15) * np.linspace(0.3, 1, n)


def ding():
    n = int(SR * 0.9); t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * t) * a * np.exp(-t * k) for f, a, k in ((880, 0.4, 4), (1320, 0.2, 6), (1760, 0.12, 8)))
    return y * _env(n, 0.002, 0.3)


def tick():
    n = int(SR * 0.08); t = np.arange(n) / SR
    return np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 60) * 0.35


KINDS = {"whoosh": whoosh, "heartbeat": heartbeat, "alarm": alarm, "buzz": buzz, "rise": rise, "ding": ding, "tick": tick}


def make(kind, path):
    _save(KINDS[kind](), path)
    return path


def for_format(fmt):
    """Акцент под ответную (вторую) фразу по рубрике."""
    return {"Жуткий факт": "heartbeat", "Нельзя": "alarm", "Миф или правда": "buzz", "Самый": "rise"}.get(fmt, "tick")


if __name__ == "__main__":
    import sys
    for k in KINDS:
        make(k, f"/tmp/sfx_{k}.wav")
    print("ok")
