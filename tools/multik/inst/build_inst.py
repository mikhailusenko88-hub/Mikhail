#!/usr/bin/env python3
"""Собирает Resources/Mebel/multik-inst.js — живые инструменты для музыки мультиков.
Сэмплы: FluidR3 GM (Frank Wen), из github.com/gleitz/midi-js-soundfonts, лицензия CC BY 3.0.
Берём каждую 3-ю ноту (до, ми-бемоль, фа-диез, ля) — остальные получаются лёгкой подстройкой.
Моно, 32 кГц, mp3 48 кбит/с; громкость инструментов выровнена.
python3 build_inst.py /путь/к/midi-js-soundfonts  (папка с FluidR3_GM, можно sparse-клон)"""
import sys, os, subprocess, base64, json, math, struct
SF = sys.argv[1] if len(sys.argv) > 1 else '/tmp/sf'
OUT = os.path.join(os.path.dirname(__file__), '../../../Resources/Mebel/multik-inst.js')
INST = {  # имя: (папка GM, нижняя нота, верхняя нота)
  'piano': ('acoustic_grand_piano', 36, 96), 'pizz': ('pizzicato_strings', 36, 84), 'strings': ('string_ensemble_1', 36, 84),
  'flute': ('flute', 60, 96), 'clarinet': ('clarinet', 48, 84), 'oboe': ('oboe', 57, 90), 'bassoon': ('bassoon', 33, 69),
  'horn': ('french_horn', 39, 75), 'glock': ('glockenspiel', 72, 105), 'celesta': ('celesta', 60, 102), 'mbox': ('music_box', 60, 96),
  'marimba': ('marimba', 48, 90), 'xylo': ('xylophone', 60, 99), 'harp': ('orchestral_harp', 36, 96), 'bass': ('acoustic_bass', 27, 57),
  'guitar': ('acoustic_guitar_nylon', 39, 78), 'timp': ('timpani', 36, 57), 'choir': ('choir_aahs', 48, 78), 'wood': ('woodblock', 72, 78),
}
NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
def nm(m): return NAMES[m % 12] + str(m // 12 - 1)
def notes(lo, hi): return [m for m in range(lo - lo % 3, hi + 1, 3) if m >= lo - 2]
def pcm(path, extra=[]):
  r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path] + extra + ['-ac', '1', '-ar', '32000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
  return struct.unpack('<%dh' % (len(r) // 2), r)
def rms(a, n): s = a[:n]; return math.sqrt(sum(x * x for x in s) / max(1, len(s))) / 32768
if __name__ == '__main__':
  if len(sys.argv) > 2 and sys.argv[2] == '--list':  # список файлов для sparse-checkout
    for k, (d, lo, hi) in INST.items():
      for m in notes(lo, hi): print('/FluidR3_GM/%s-mp3/%s.mp3' % (d, nm(m)))
    sys.exit()
  out = {}; tot = 0
  for k, (d, lo, hi) in INST.items():
    ns = [m for m in notes(lo, hi) if os.path.exists(os.path.join(SF, 'FluidR3_GM', d + '-mp3', nm(m) + '.mp3'))]
    A = [pcm(os.path.join(SF, 'FluidR3_GM', d + '-mp3', nm(m) + '.mp3')) for m in ns]
    lv = sorted(rms(a, 16000) for a in A); pk = max(max(abs(x) for x in a) for a in A) / 32768
    med = lv[len(lv) // 2] or 1e-3; want = .12 / med        # громкость инструмента — к одной мерке
    gain = min(want, .95 / max(pk, 1e-3)); rest = want / gain  # без перегруза в файле; остаток — при игре
    ent = {}
    for m in ns:
      src = os.path.join(SF, 'FluidR3_GM', d + '-mp3', nm(m) + '.mp3')
      mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-af', 'silenceremove=start_periods=1:start_threshold=-60dB,volume=%.3f' % gain,
                            '-ac', '1', '-ar', '32000', '-b:a', '48k', '-f', 'mp3', '-'], capture_output=True, check=True).stdout
      ent[str(m)] = base64.b64encode(mp3).decode(); tot += len(mp3)
    out[k] = {'g': round(rest, 3), 'n': ent}
    print(k, len(ns), 'нот, громкость ×%.2f, при игре ×%.2f' % (gain, rest))
  with open(OUT, 'w') as f:
    f.write('// Живые инструменты для музыки мультиков (оркестр, пианино, колокольчики…).\n')
    f.write('// Сэмплы: FluidR3 GM, автор Frank Wen; через github.com/gleitz/midi-js-soundfonts; лицензия CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/).\n')
    f.write('// Собрано tools/multik/inst/build_inst.py. Каждая 3-я нота, моно 32 кГц.\n')
    f.write('window.MK_INST = ' + json.dumps(out, separators=(',', ':')) + ';\n')
  print('итого', round(tot / 1e6, 2), 'МБ mp3 →', round(os.path.getsize(OUT) / 1e6, 2), 'МБ js')
