"""Свои мелодии с низким голосом для роликов (чистый движок из studio/): стили golos_*.
Звук стерео, −18 LUFS (как у остальной музыки канала), без лимитера. Под длину ролика выбирается вариант мелодии (с вступлением или без), темп слегка
подгоняется, чтобы финальный аккорд и хвост зала легли точно в ролик."""
import sys
from pathlib import Path

import numpy as np

STUDIO = str(Path(__file__).parent / "studio")
STYLES = {
    "golos_rassvet": "rassvet",            # «Рассвет»: фа мажор, струнные, арфа, фортепиано
    "golos_doroga": "doroga",              # «Дорога»: ми мажор, фортепиано, мягкий бит
    "golos_prostor": "prostor",            # «Простор»: соль мажор, пентатоника, хор, большие барабаны
    "golos_gimn": "gimn",                  # «Гимн»: си-бемоль мажор, орган, хор, колокол
    "golos_kolybelnaya": "kolybelnaya",    # «Колыбельная»: ре мажор, 3/4, арфа и челеста
}
ORDER = list(STYLES)
LUFS = -18.0          # громкость как у прежней оркестровой музыки канала (−17…−19 LUFS); при −14 ролики казались громкими


def make_music(style, total, seed=0, line_times=()):
    """-> массив (n, 2): готовый стереозвук длиной ровно total секунд"""
    if STUDIO not in sys.path:
        sys.path.insert(0, STUDIO)
    import golos
    name = golos.best_variant(STYLES[style], float(total))   # вариант (с вступлением или без), чей темп ближе к родному
    L, R, bpm = golos.render(name, float(total), target=LUFS)
    print(f"музыка {style} ({name}): {total:.2f} с, {bpm:.1f} уд/мин (родной темп {golos.SONGS[name]['bpm']})", flush=True)
    return np.stack([L, R], axis=1)
