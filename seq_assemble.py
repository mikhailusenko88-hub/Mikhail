"""Сборка по своему порядку кадров (H50: разбился → собрался, обратный ход в конце быстрее).
python3 seq_assemble.py <pos.npz> <first_frame> <seg-имена> <выход.mp4> <порядок: a-b, a-b:шаг, a*N через запятую>
Пример: 8-80,80*4,79-45:2,44-9  — вперёд 8..80, пауза 4 кадра, назад 79..45 через кадр, 44..9 подряд."""
import os, subprocess, sys
import numpy as np
posf, F0, segs, OUT, spec = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(','), sys.argv[4], sys.argv[5]
W, H = 1080, 1920
tmp = '/home/claude/work3d/tmp'; os.makedirs(tmp, exist_ok=True)
seq = []
for part in spec.split(','):
    if '*' in part:
        f, n = part.split('*'); seq += [int(f)] * int(n); continue
    rng, _, st = part.partition(':'); a, b = (int(v) for v in rng.split('-')); st = int(st or 1)
    seq += list(range(a, b + 1, st)) if b >= a else list(range(a, b - 1, -st))
lst = os.path.join(tmp, 'list.txt')
with open(lst, 'w') as f:
    for s in segs:
        f.write(f"file '{os.path.abspath(os.path.join('out', s, 'seg.mp4'))}'\n")
raw = os.path.join(tmp, 'raw.mp4')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', raw], check=True)
dec = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', raw, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
frames = {}
mm = np.memmap(os.path.join(tmp, 'frames.dat'), np.uint8, 'w+', shape=(200, H * W * 3))
i = 0
while True:
    buf = dec.stdout.read(W * H * 3)
    if len(buf) < W * H * 3:
        break
    mm[i] = np.frombuffer(buf, np.uint8); frames[F0 + i] = i; i += 1
dec.wait()
enc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                        '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                        '-color_trc', 'bt709', '-color_range', 'tv', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
                        os.path.join(tmp, 'v.mp4')], stdin=subprocess.PIPE)
for f in seq:
    enc.stdin.write(mm[frames[f]].tobytes())
enc.stdin.close(); enc.wait()
dur = len(seq) / 30
d = np.load(posf)
pseq = np.concatenate([d['pos'][[f - 1 for f in seq]], d['pos'][[seq[0] - 1, seq[0], seq[0] + 1]]])
lp = os.path.join(tmp, 'pos_seq.npz')
np.savez_compressed(lp, **{k: (pseq if k == 'pos' else d[k]) for k in d.files})
wav = os.path.join(tmp, 'a.wav')
subprocess.run(['python3', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sound3d.py'), lp, wav, '0', str(dur)], check=True)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'v.mp4'), '-i', wav, '-c:v', 'copy',
                '-af', 'loudnorm=I=-15:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', OUT], check=True)
print('кадров', len(seq), 'длина', round(dur, 2), 'с', OUT)
