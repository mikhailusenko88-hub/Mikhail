# Склейка кусков анимации + субтитры -> out/barsik_10s.mp4
import subprocess, glob, os
from PIL import Image, ImageDraw, ImageFont
ch = sorted(glob.glob('out/anim/chunk_*.mp4')); print(len(ch), 'кусков')
with open('/tmp/list.txt', 'w') as f:
    for c in ch: f.write("file '%s'\n" % os.path.abspath(c))
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', '/tmp/list.txt', '-c', 'copy', '/tmp/raw.mp4'], check=True)
os.makedirs('/tmp/af', exist_ok=True); [os.remove(p) for p in glob.glob('/tmp/af/*.png')]
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', '/tmp/raw.mp4', '/tmp/af/%04d.png'], check=True)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 36)
SUB = [(0.95, 2.7, 'Привет! Я Барсик.'), (5.7, 7.7, 'Пойдём гулять?')]
fr = sorted(glob.glob('/tmp/af/*.png'))
for i, p in enumerate(fr):
    t = i / 25; txt = next((s for a, b, s in SUB if a <= t < b), None)
    if not txt: continue
    im = Image.open(p); d = ImageDraw.Draw(im); w = d.textlength(txt, font=font); x, y = (1280 - w) / 2, 720 - 80
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2): d.text((x + dx, y + dy), txt, font=font, fill=(20, 20, 20))
    d.text((x, y), txt, font=font, fill=(255, 255, 255)); im.save(p)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '25', '-i', '/tmp/af/%04d.png', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', 'out/barsik_10s.mp4'], check=True)
print('кадров', len(fr), '-> out/barsik_10s.mp4')
