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
if 'vessel' in d.files:                                # сосуд-зверь: внутри = SDF < 0 и ниже края отверстия
    from scipy.ndimage import map_coordinates, median_filter
    vs = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vessels', str(d['vessel']) + '_sdf.npz'))
    D, O, HH = vs['d'].astype(np.float32), vs['o'], float(vs['h'])
    rimz = (float(vs['rimmax']) if 'rimmax' in vs.files else float(vs['mouth'][3])) + float(d['lift'])
    P = pos.reshape(-1, 3) - np.array([0, 0, float(d['lift'])])
    sd = map_coordinates(D, ((P - O) / HH).T, order=1, mode='nearest').reshape(pos.shape[:2])
    inside = (sd < 0) & (pos[..., 2] < rimz + 0.004)
    cnt = median_filter(inside.sum(1), size=5, mode='nearest')
    cnt = np.maximum.accumulate(cnt) if os.environ.get('MONO') else cnt
else:
    GW, GD, GH, T = (float(v) for v in d['glass'])
    inside = (np.abs(pos[..., 0]) < GW / 2 + 0.003) & (np.abs(pos[..., 1]) < GD / 2 + 0.003) & (pos[..., 2] < ZC)
    cnt = inside.sum(1)                                    # по кадрам 1..N (индекс f-1)
    cnt = np.maximum.accumulate(cnt)                       # счётчик не идёт назад (шар, отскочивший вверх, не «убывает»)
TOTAL = pos.shape[1]
print('кадров', nf, 'шаров всего', TOTAL, 'в кубе к концу', int(cnt[min(len(cnt) - 1, F0 - 1 + nf - 1)]))
fb = ImageFont.truetype('/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', 150)
fs = ImageFont.truetype('/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf', 40)
dec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', raw, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                        '-color_trc', 'bt709', '-color_range', 'tv', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                        os.path.join(tmp, 'v.mp4')], stdin=subprocess.PIPE)
COL = tuple(json.loads(os.environ.get('CCOL', '[28,32,44]')))
CX = W * float(os.environ.get('TX', '0.5'))              # центр счётчика по ширине (доля кадра)
TY = int(os.environ.get('TY', '170'))                  # верх счётчика, px (подпись — на 180 px ниже)
SW = int(os.environ.get('SW', '0'))                    # обводка цифр, px (0 — без обводки)
SCOL = tuple(json.loads(os.environ.get('SCOL', '[245,245,247]')))
last = None
used = 0
LOOP = bool(os.environ.get('LOOP'))                    # петля «туда и обратно»: вперёд, пауза, те же кадры назад — конец стыкуется с началом
HOLD = int(os.environ.get('HOLD', '8' if LOOP else '12'))
mm = np.memmap(os.path.join(tmp, 'frames.dat'), np.uint8, 'w+', shape=(max(1, min(E, F0 + nf - 1) - max(S, F0) + 1), H * W * 3)) if LOOP else None
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
    dr.text((CX - tw / 2, TY), txt, font=fb, fill=COL, stroke_width=SW, stroke_fill=SCOL)
    lw = dr.textlength(LABEL, font=fs)
    dr.text((CX - lw / 2, TY + 180), LABEL, font=fs, fill=COL, stroke_width=max(0, SW // 2), stroke_fill=SCOL)
    enc.stdin.write(im.tobytes())
    if LOOP:
        mm[used - 1] = np.frombuffer(im.tobytes(), np.uint8)
    last = im
for _ in range(HOLD):
    enc.stdin.write(last.tobytes())
back = 0
if LOOP:                                               # обратный ход: кадры n-2 … 1 (без повторов на стыках)
    for j in range(used - 2, 0, -1):
        enc.stdin.write(mm[j].tobytes())
        back += 1
enc.stdin.close(); enc.wait(); dec.wait()
dur = (used + HOLD + back) / 30
wav = os.path.join(tmp, 'a.wav')
snd = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sound3d.py')
if LOOP:                                               # звук — из той же траектории, пройденной вперёд, с паузой и назад
    a, b = max(S, F0) - 1, max(S, F0) - 1 + used       # индексы кадров в pos
    seq = np.concatenate([d['pos'][a:b], np.repeat(d['pos'][b - 1:b], HOLD, 0), d['pos'][a + 1:b - 1][::-1], d['pos'][a:a + 3]])
    lp = os.path.join(tmp, 'pos_loop.npz')
    np.savez_compressed(lp, **{k: (seq if k == 'pos' else d[k]) for k in d.files})
    subprocess.run(['python3', snd, lp, wav, '0', str(dur)], check=True)
else:
    subprocess.run(['python3', snd, posf, wav, str((max(S, F0) - 1) / 30), str(dur)], check=True)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'v.mp4'), '-i', wav, '-c:v', 'copy',
                '-af', 'loudnorm=I=-15:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', OUT], check=True)
print('готово', OUT, round(dur, 2), 'с')
