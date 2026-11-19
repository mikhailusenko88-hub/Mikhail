"""Сборка 3D-ролика: отрезки seg.mp4 → один ролик + счётчик шаров в кадре + звук из физики.
python3 assemble.py <out_dir_ветки> <pos.npz> <first_frame> <seg-имена через запятую> <выход.mp4> [подпись]"""
import subprocess, sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

base, posf, F0, segs, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4].split(','), sys.argv[5]
LABEL = sys.argv[6] if len(sys.argv) > 6 else "BALLS IN THE BOX"
S, E = (int(v) for v in (sys.argv[7] if len(sys.argv) > 7 else f"{F0}-99999").split('-'))   # какие кадры взять в ролик
ZC = float(os.environ.get('ZC', '0.30'))      # шар «в коробке», когда ниже этой высоты (выше — ещё в ведре)
W, H = 1080, 1920
tmp = '/home/claude/work3d/tmp'; os.makedirs(tmp, exist_ok=True)
lst = os.path.join(tmp, 'list.txt')
with open(lst, 'w') as f:
    for s in segs:
        f.write(f"file '{os.path.abspath(os.path.join(base, s, 'seg.mp4'))}'\n")
raw = os.path.join(tmp, 'raw.mp4')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', raw], check=True)
# сколько кадров
nf = int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                         'stream=nb_read_frames', '-of', 'csv=p=0', raw], capture_output=True, text=True).stdout.strip())
d = np.load(posf)
pos = d['pos'].astype(np.float32)
GW, GD, GH, T = (float(v) for v in d['glass'])
inside = (np.abs(pos[..., 0]) < GW / 2 + 0.003) & (np.abs(pos[..., 1]) < GD / 2 + 0.003) & (pos[..., 2] < ZC)
cnt = inside.sum(1)                                    # по кадрам 1..N (индекс f-1)
cnt = np.maximum.accumulate(cnt)                       # счётчик не идёт назад (шар, отскочивший вверх, не «убывает»)
TOTAL = pos.shape[1]
print('кадров', nf, 'шаров всего', TOTAL, 'в кубе к концу', int(cnt[min(len(cnt) - 1, F0 - 1 + nf - 1)]))
fb = ImageFont.truetype('/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', 150)
fs = ImageFont.truetype('/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', 40)
HOLD = 12                                              # 0,4 с на последнем кадре
dec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', raw, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                        '-color_trc', 'bt709', '-color_range', 'tv', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                        os.path.join(tmp, 'v.mp4')], stdin=subprocess.PIPE)
COL = tuple(json.loads(os.environ.get('CCOL', '[28,32,44]')))
last = None
used = 0
for i in range(nf):
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    fr = F0 + i
    if fr < S or fr > E:
        continue
    used += 1
    im = Image.frombytes('RGB', (W, H), buf)
    k = min(len(cnt) - 1, fr - 1)
    n = int(cnt[k])
    dr = ImageDraw.Draw(im)
    txt = f"{n:,}"
    tw = dr.textlength(txt, font=fb)
    dr.text(((W - tw) / 2, 170), txt, font=fb, fill=COL)
    lw = dr.textlength(LABEL, font=fs)
    dr.text(((W - lw) / 2, 350), LABEL, font=fs, fill=COL)
    enc.stdin.write(im.tobytes())
    last = im
for _ in range(HOLD):
    enc.stdin.write(last.tobytes())
enc.stdin.close(); enc.wait(); dec.wait()
dur = (used + HOLD) / 30
wav = os.path.join(tmp, 'a.wav')
subprocess.run(['python3', '/home/claude/s3d/sound3d.py', posf, wav, str((max(S, F0) - 1) / 30), str(dur)], check=True)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'v.mp4'), '-i', wav, '-c:v', 'copy',
                '-af', 'loudnorm=I=-15:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', OUT], check=True)
print('готово', OUT, round(dur, 2), 'с')
