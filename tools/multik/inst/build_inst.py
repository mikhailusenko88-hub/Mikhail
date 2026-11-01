#!/usr/bin/env python3
"""Собирает Resources/Mebel/multik-inst.js — живые инструменты для музыки мультиков.
Все записи — общественное достояние (CC0), подписывать авторов в роликах не нужно:
  * VS Chamber Orchestra: Community Edition (github.com/sgossner/VSCO-2-CE) — струнные, флейта, кларнет, гобой,
    фагот, валторна, арфа, колокольчики, ксилофон, маримба, литавры, контрабас;
  * Meta Piano и Meta Nylon Guitar (github.com/facebookincubator/Meta-open-sound) — пианино и гитара.
Высоту каждой записи меряем сами (ключ ноты — с десятыми, так строй получается точным).
Моно, 32 кГц, mp3 48 кбит/с; громкость инструментов выровнена.
python3 build_inst.py /путь/к/VSCO-2-CE /путь/к/Meta-open-sound"""
import sys, os, re, glob, subprocess, base64, json, math
import numpy as np
VSCO = sys.argv[1] if len(sys.argv) > 1 else '/tmp/vsco'
META = sys.argv[2] if len(sys.argv) > 2 else '/tmp/mos'
OUT = os.path.join(os.path.dirname(__file__), '../../../Resources/Mebel/multik-inst.js')
SR = 32000
PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

def load(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(r, dtype=np.float32).copy()

def onset(a):
    pk = np.abs(a).max() or 1; i = int(np.argmax(np.abs(a) > pk * .02)); return max(0, i - int(SR * .003))

def f0_of(a, perc):
    """Основной тон: спектр участка после атаки, гармоническое произведение + уточнение по пику."""
    s = onset(a) + int(SR * (.04 if perc else .18)); seg = a[s:s + int(SR * (.25 if perc else .5))]
    if len(seg) < 2048: seg = a[onset(a):onset(a) + 8192]
    n = 1 << 16; w = seg * np.hanning(len(seg)); sp = np.abs(np.fft.rfft(w, n)); f = np.fft.rfftfreq(n, 1 / SR)
    lo, hi = np.searchsorted(f, 25), np.searchsorted(f, 4500)
    hps = np.log(sp[lo:hi] + 1e-9).copy()
    for h in (2, 3, 4):
        idx = (np.arange(lo, hi) * h)
        ok = idx < len(sp); hps[ok] += np.log(sp[idx[ok]] + 1e-9) * .8
    i = lo + int(np.argmax(hps))
    # уточнение: параболой по пику
    if 1 <= i < len(sp) - 1:
        y0, y1, y2 = np.log(sp[i - 1] + 1e-9), np.log(sp[i] + 1e-9), np.log(sp[i + 1] + 1e-9); d = .5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12); i = i + d
    return i * SR / n

def name_pc(fn):
    m = re.search(r'_([A-G])(#|s|b)?(-?\d)(?=[_.])', os.path.basename(fn))
    if not m: return None
    p = PC[m.group(1)] + (1 if m.group(2) in ('#', 's') else -1 if m.group(2) == 'b' else 0); return p % 12

def measure(files, perc=False):
    out = []
    for fn in files:
        a = load(fn); f0 = f0_of(a, perc); mf = 69 + 12 * math.log2(f0 / 440); m = round(mf)
        npc = name_pc(fn)
        if npc is not None and m % 12 != npc:  # спектр поймал не тот тон — верим названию, октаву берём ближайшую
            cand = [k for k in range(m - 7, m + 8) if k % 12 == npc]; k = min(cand, key=lambda k: abs(k - mf))
            # частота уточняется по выбранной ноте только если рядом есть гармоника
            mf = k + (mf - round(mf)) * 0; m = k
        out.append((mf, fn, a))
    return out

def by_name(files, shift=0, tune=0):
    """Высота по названию (до первой октавы = 60), для пианино/гитары и колокольчиков (их звенящие обертоны сбивают замер)."""
    out = []
    for fn in files:
        m = re.search(r'_([A-G])(s|#)?(-?\d)(?=[_.])', os.path.basename(fn))
        if not m: continue
        midi = 12 * (int(m.group(3)) + 1) + PC[m.group(1)] + (1 if m.group(2) else 0) + shift
        out.append((midi + tune, fn, load(fn)))
    return out

def pick(meas, lo, hi, step=3, prefer=None):
    """Набор записей по диапазону: на каждую ступень (через 3 полутона) — ближайшая запись."""
    meas = [x for x in meas if lo - 2 <= x[0] <= hi + 2]; got = {}
    for target in range(lo, hi + 1, step):
        best = min(meas, key=lambda x: (abs(x[0] - target) + (prefer(x) if prefer else 0)), default=None)
        if best is not None and abs(best[0] - target) <= 2.6: got[best[1]] = best
    return sorted(got.values(), key=lambda x: x[0])

def enc(a, gain, maxlen, fade=.3):
    a = a[onset(a):]; n = min(len(a), int(SR * maxlen)); a = a[:n].copy(); fl = int(SR * fade)
    if len(a) >= int(SR * maxlen) - 1: a[-fl:] *= np.linspace(1, 0, fl)
    a = np.clip(a * gain, -1, 1)
    pcm = (a * 32767).astype('<i2').tobytes()
    return subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-b:a', '48k', '-f', 'mp3', '-'], input=pcm, capture_output=True, check=True).stdout

def G(*pat): return sorted(sum((glob.glob(os.path.join(VSCO, p)) for p in pat), []))
def section(fn):
    return 0 if 'Cello' in fn else 1 if 'Viola' in fn else 2

INST = {}
SUS = {'strings', 'flute', 'clarinet', 'oboe', 'horn'}
def add(name, chosen, maxlen):
    if not chosen: print('нет записей:', name); return
    # громкость: у тянущихся — по середине звука (атака у смычка медленная), у ударных — по первым полсекунды
    w0, w1 = (int(SR * .3), int(SR * 1.3)) if name in SUS else (0, SR // 2)
    rms = sorted(float(np.sqrt(np.mean(a[onset(a) + w0:onset(a) + w1] ** 2))) for _, _, a in chosen)
    pk = max(float(np.abs(a).max()) for _, _, a in chosen); med = rms[len(rms) // 2] or 1e-3
    want = .12 / med; gain = min(want, .95 / max(pk, 1e-3)); rest = want / gain
    rnd = name in ('bass', 'timp')  # низкие ноты меряются неточно — записи и так строят ровно по полутонам
    INST[name] = {'g': round(rest, 3), 'n': {('%.1f' % (round(mf) if rnd else mf)): base64.b64encode(enc(a, gain, maxlen)).decode() for mf, fn, a in chosen}}
    print('%-9s %2d нот %s  ×%.2f/×%.2f' % (name, len(chosen), ' '.join('%.1f' % x[0] for x in chosen), gain, rest))

if __name__ == '__main__':
    # струнные смычком: виолончели внизу, альты в середине, скрипки наверху
    strs = measure(G('Strings/Cello Section/susvib/*_v1_1.wav', 'Strings/Viola Section/susvib/*_v1_1.wav', 'Strings/Violin Section/susVib/*_v1.wav'))
    add('strings', pick(strs, 36, 84, prefer=lambda x: .8 * abs(section(x[1]) - (0 if x[0] < 53 else 1 if x[0] < 65 else 2))), 4.0)
    pz = measure(G('Strings/Cello Section/pizzT/*_v2_RR1.wav', 'Strings/Violin Section/Pizz/*_v2_rr1.wav'), True)
    add('pizz', pick(pz, 36, 84, prefer=lambda x: .8 * abs(section(x[1]) / 2 - (0 if x[0] < 56 else 1))), 2.5)
    add('bass', pick(measure(G('Strings/Solo Contrabass/Pizz/*_v1_rr1.wav'), True), 27, 57), 2.5)
    add('harp', pick(measure(G('Strings/Harp/*_mf.wav'), True), 36, 96), 3.5)
    fl = measure(G('Woodwinds/Flute/susNV/*.wav'))
    add('flute', pick(fl, 60, 96, prefer=lambda x: 0 if '_v3_' in x[1] or '_v2_' in x[1] else .5), 4.0)
    add('clarinet', pick(measure(G('Woodwinds/Clarinet/susLong/*_v2_rr1_sum.wav')), 48, 86), 4.0)
    add('oboe', pick(measure(G('Woodwinds/Oboe/Sus/*_v1_Main.wav')), 58, 90), 4.0)
    bs = measure(G('Woodwinds/Bassoon/stac/*_rr1.wav'), True)
    add('bassoon', pick(bs, 34, 72, prefer=lambda x: 0 if '_v2_' in x[1] else .4), 1.5)
    add('horn', pick(measure(G('Brass/F Horn/sus/*_v2_1.wav')), 40, 76), 4.0)
    add('glock', pick(by_name(G('Percussion/Glock/*.wav'), 12, .15), 67, 108, step=5), 3.0)  # звучат на октаву выше написанного
    add('xylo', pick(by_name(G('Percussion/Xylo/*.wav'), 12, .14), 55, 103, step=5), 2.0)
    add('marimba', pick(measure(G('Percussion/Marimba/*.wav'), True), 41, 96, step=5), 2.5)
    add('timp', pick([x for x in measure(G('Percussion/Timpani/*_v3_rr1_Sum.wav'), True) if x[0] > 38], 38, 57, step=2), 3.0)  # самые низкие замеры — ошибка (обертон ниже тона)
    # пианино и гитара (Meta, CC0) — ноты подписаны точно
    pia = by_name(sorted(glob.glob(os.path.join(META, 'systems/instruments/meta-piano/ogg/INSPiano_Vel02_*.ogg'))))
    add('piano', pick(pia, 36, 96), 3.5)
    gt = by_name(sorted(glob.glob(os.path.join(META, 'systems/instruments/meta-nylon-guitar/ogg/*Vel01Finger*.ogg'))))
    add('guitar', pick(gt, 40, 79), 2.5)
    with open(OUT, 'w') as fo:
        fo.write('// Живые инструменты для музыки мультиков. Все записи — общественное достояние (CC0), подписывать не нужно:\n')
        fo.write('// VS Chamber Orchestra: Community Edition (VSCO-2-CE) и Meta Piano / Meta Nylon Guitar (Meta-open-sound).\n')
        fo.write('// Собрано tools/multik/inst/build_inst.py. Ключ — высота записи в полутонах (MIDI, с десятыми).\n')
        fo.write('window.MK_INST = ' + json.dumps(INST, separators=(',', ':')) + ';\n')
    print('файл', round(os.path.getsize(OUT) / 1e6, 2), 'МБ')
