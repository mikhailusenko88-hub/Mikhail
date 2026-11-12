"""Свои мелодии с низким голосом для роликов (чистый движок из studio/): стили golos_*.
Звук стерео, −14 LUFS, без лимитера; темп подгоняется так, чтобы финальный аккорд и хвост зала легли точно в длину ролика."""
import sys
from pathlib import Path

import numpy as np

STUDIO = str(Path(__file__).parent / "studio")
STYLES = {
    "golos_rassvet": "rassvet_s",          # «Рассвет»: фа мажор, струнные, арфа, фортепиано
    "golos_doroga": "doroga_s",            # «Дорога»: ми мажор, фортепиано, мягкий бит
    "golos_prostor": "prostor_s",          # «Простор»: соль мажор, пентатоника, хор, большие барабаны
    "golos_gimn": "gimn_s",                # «Гимн»: си-бемоль мажор, орган, хор, колокол
    "golos_kolybelnaya": "kolybelnaya_s",  # «Колыбельная»: ре мажор, 3/4, арфа и челеста
}
ORDER = list(STYLES)


def make_music(style, total, seed=0, line_times=()):
    """-> массив (n, 2): готовый стереозвук длиной ровно total секунд"""
    if STUDIO not in sys.path:
        sys.path.insert(0, STUDIO)
    import golos
    L, R, bpm = golos.render(STYLES[style], float(total))
    print(f"музыка {style}: {total:.2f} с, {bpm:.1f} уд/мин", flush=True)
    return np.stack([L, R], axis=1)
