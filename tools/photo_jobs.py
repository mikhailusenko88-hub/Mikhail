"""Задания для режима «Фото» расчёта стены на сайте: все панели × 3 кадра (tv — ТВ-зона, lv — гостиная, cl — крупно) + маски стены.
    python3 tools/photo_jobs.py > run.txt      затем commit и push — посчитается в GitHub Actions (≈20 мин на кадр, 20 кадров сразу)
Готовые кадры: out/f_<сцена>_<артикул>/…jpg → на сайт их кладёт nashdekor-build/make_int_photos.py (ветка mebel)."""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'cabcol=C9B8A0 sun_az=32 sun_el=52 ev=-0.9 view=Khronos_PBR_Neutral look=None calfile=cal_photo.json res=1500x1000'
Q = 'samples=160 noise=0.04'
SC = {'tv': 'scene=lounge tv=1 cam=angle chair_at=3.9,0.6 ax=3.7 ay=1.9 az=1.25 lx=1.9 lens=26',
      'lv': 'scene=lounge cam=main',
      'cl': 'scene=lounge tv=1 cam=macro fs=0 chair_at=3.9,0.6'}
white = list(json.load(open(f'{R}/profiles_site.json', encoding='utf-8')))
wood = list(json.load(open(f'{R}/tex3/index.json', encoding='utf-8')))
key = lambda a: a.lower().replace(' ', '').replace('/', '-')
print('# имя  аргументы для scene.py (или "py script.py")')
print('# «Фото» для расчёта стены на сайте: %d белых + %d под дерево × 3 кадра, маски стены (tools/photo_jobs.py)' % (len(white), len(wood)))
for sc, cam in SC.items():
    print(f'f_{sc}_mask {cam} decor=A907 mask=1 {B}')
    for a in white:
        print(f'f_{sc}_{key(a)} {cam} decor={key(a).upper()} {B} {Q}')
    for a in wood:
        print(f'f_{sc}_{a} {cam} decor={a} tex=strip {B} {Q}')
