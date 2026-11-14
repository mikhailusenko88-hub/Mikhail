"""Звук для Shorts с арены Flagball Arena: своя музыка (audio.py с канала) + звуки поеданий,
отсчёт последних секунд раунда и фанфары победы. Вход — events.json от записи, выход — wav."""
import json
import sys
import wave

import numpy as np

from audio import Mix, SR


def main(events_path, out_wav):
    ev = json.load(open(events_path, encoding='utf-8'))
    dur = float(ev['duration'])
    seed = int(ev.get('seed', 1))
    mx = Mix(dur, seed=seed)
    win_at = ev.get('round_at')
    # музыка: до конца раунда — бодро, после — спокойнее (финальная заставка)
    end_music = win_at if win_at else dur
    mx.music_section(0, end_music, key=seed % 5, bpm=128, energy=1.0, seed=seed)
    if win_at and dur - win_at > 0.5:
        mx.music_section(win_at, dur, key=seed % 5, bpm=128, energy=0.4, seed=seed + 1)
    # поедания: «чпок» — чем больше съеденный шарик, тем ниже и громче звук
    for e in ev.get('eats', []):
        t, m = float(e['t']), float(e.get('m', 10))
        if 0 <= t < dur:
            f = max(220.0, 900.0 - min(600.0, m * 6))
            vol = min(0.32, 0.12 + m / 400)
            mx.put(mx.sfx, mx.tone(f, 0.22, vol, decay=16, harm=(1, 0.4, 0.1)), t)
            mx.put(mx.sfx, mx.tone(f * 1.5, 0.12, vol * 0.5, decay=24, harm=(1,)), t + 0.03)
    # последние секунды раунда — пики
    for t, high in ev.get('beeps', []):
        if 0 <= t < dur:
            mx.beep(t, high=bool(high))
    if win_at and 0 <= win_at < dur:
        mx.fanfare(win_at)
    a = mx.final()[: int(dur * SR)]
    pcm = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    st = np.stack([pcm, pcm], axis=1)
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
