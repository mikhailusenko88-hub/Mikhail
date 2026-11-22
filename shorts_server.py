# Shorts «в формате сервера» (проба H28, 22.11.2026): кадр серии 16:9 посередине на размытом фоне,
# сверху плашка «КОТ БАРСИК» и вопрос серии, снизу «ПОЛНАЯ СЕРИЯ — НА КАНАЛЕ» — как резал сервер до 15.11 (ветка shorts, cut.py).
#   python3 shorts_server.py ep.mp4 начало_с длина_с "ВОПРОС СЕРИИ?" выход.mp4
import sys, os, subprocess, tempfile, glob

src, a, dur, hook, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5]
fonts = glob.glob('/usr/share/fonts/**/Inter-Black.[ot]tf', recursive=True) + glob.glob('/usr/share/fonts/**/DejaVuSans-Bold.ttf', recursive=True)
font = fonts[0]
tmp = tempfile.mkdtemp()


def wrap(s, n=18):
    lines, line = [], ''
    for w in s.split():
        if len(line) + len(w) + 1 > n and line: lines.append(line); line = w
        else: line = (line + ' ' + w).strip()
    if line: lines.append(line)
    return lines[:3]


def txt(name, s):
    p = os.path.join(tmp, name); open(p, 'w', encoding='utf-8').write(s); return p


vf = ('[0:v]split=2[bg0][fg0];'
      '[bg0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=28:luma_power=2,eq=brightness=-0.18:saturation=1.2[bg];'
      '[fg0]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2[v1];')
parts = [f"[v1]drawtext=fontfile={font}:textfile={txt('badge.txt', 'КОТ БАРСИК')}:fontsize=44:fontcolor=white:box=1:boxcolor=0xE8452C@0.95:boxborderw=18:x=(w-tw)/2:y=250"]
for i, ln in enumerate(wrap(hook.upper())):
    parts.append(f"drawtext=fontfile={font}:textfile={txt(f'top{i}.txt', ln)}:fontsize=76:fontcolor=white:borderw=5:bordercolor=black@0.85:x=(w-tw)/2:y={360 + i * 92}")
parts.append(f"drawtext=fontfile={font}:textfile={txt('bot.txt', 'ПОЛНАЯ СЕРИЯ — НА КАНАЛЕ')}:fontsize=46:fontcolor=0xFFE14D:borderw=4:bordercolor=black@0.85:x=(w-tw)/2:y=1440")
parts.append(f"fade=t=in:st=0:d=0.3,fade=t=out:st={dur - 0.5}:d=0.5[v]")
af = f"[0:a]afade=t=in:st=0:d=0.2,afade=t=out:st={dur - 0.5}:d=0.5[a]"
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(a), '-t', str(dur), '-i', src, '-filter_complex', vf + ','.join(parts) + ';' + af,
                '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '25',
                '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out], check=True)
print(out)
