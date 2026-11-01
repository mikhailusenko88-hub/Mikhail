#!/usr/bin/env python3
"""Собирает Resources/Mebel/multik-laugh.js — записи настоящего смеха для героев.
Источник: "Oculus Audio Pack 01" by Oculus VR, LLC (https://developers.meta.com/vr/downloads/package/oculus-audio-pack-1/),
CC BY 4.0, из github.com/facebookincubator/Meta-open-sound (corpora/oculus-audio-pack/ogg/VOXLaff_*).
python3 build_laugh.py /путь/к/Meta-open-sound"""
import sys, os, subprocess, base64, json
SRC = os.path.join(sys.argv[1] if len(sys.argv) > 1 else '/tmp/mos', 'corpora/oculus-audio-pack/ogg')
OUT = os.path.join(os.path.dirname(__file__), '../../../Resources/Mebel/multik-laugh.js')
SETS = {'f1': 'Female01Laugh', 'f2': 'Female02Laugh', 'm1': 'Male01Laugh', 'm2': 'Male02Laugh', 'evil': 'EvilLaugh'}
out = {}
for k, nm in SETS.items():
    out[k] = []
    for i in (1, 2, 3):
        f = os.path.join(SRC, 'VOXLaff_%s_OS_%02d.ogg' % (nm, i))
        if not os.path.exists(f): continue
        mp3 = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-af', 'silenceremove=start_periods=1:start_threshold=-55dB,areverse,silenceremove=start_periods=1:start_threshold=-55dB,areverse,loudnorm=I=-18:TP=-2',
                              '-ac', '1', '-ar', '44100', '-b:a', '96k', '-f', 'mp3', '-'], capture_output=True, check=True).stdout
        out[k].append(base64.b64encode(mp3).decode())
    print(k, len(out[k]))
with open(OUT, 'w') as fo:
    fo.write('// Настоящий смех для героев мультиков (женский, мужской, злодейский; под каждого героя подстраивается высота).\n')
    fo.write('// "Oculus Audio Pack 01" by Oculus VR, LLC (https://developers.meta.com/vr/downloads/package/oculus-audio-pack-1/), licensed under CC BY 4.0.\n')
    fo.write('// Собрано tools/multik/laugh/build_laugh.py (обрезана тишина, ровная громкость, mp3).\n')
    fo.write('window.MK_LAUGH = ' + json.dumps(out, separators=(',', ':')) + ';\n')
print(round(os.path.getsize(OUT) / 1e3), 'КБ')
