"""Задания для галереи применений на сайте («Примерка в интерьере»): каждая панель × сцены + маски стены.
    python3 tools/photo_jobs.py tv cl tv1 tv2 > run.txt      (без аргументов — все сцены)   затем commit и push — посчитается в GitHub Actions
Сцены (scene=use use=…): tv — ТВ-зона, вся стена; tv1 — одна полоса за экраном; tv2 — две полосы, экран между ними; sofa — за диваном;
bed — спальня; hall — прихожая; cor — коридор; cl — крупно; крупные планы с мебелью — tvd, sofad, bedd, halld, deskd, cord (словарь DET).
Готовые кадры: out/g_<сцена>_<артикул>/…jpg → на сайт их кладёт nashdekor-build/make_int_photos.py (ветка mebel)."""
import json, os, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = 'cabcol=C9B8A0 view=Khronos_PBR_Neutral look=None res=1350x900'
Q = 'samples=120 noise=0.05'
EXP = {'cor': 'ev=-2.3 calfile=cal_cor.json', 'cord': 'ev=-1.1 calfile=cal_cor.json'}      # у коридора своя комната и свой свет
# Крупные планы (17.11: на общих планах рельеф на телефоне не виден): сцена → (комната, своя камера). В кадре ~2 м стены и мебель.
DET = {'tvd': ('tv', 'campos=3.95,3.55,1.25 camto=2.7,5.2,1.05 lens=40'),
       'sofad': ('sofa', 'campos=2.3,3.55,1.15 camto=3.4,5.2,0.95 lens=40'),
       'deskd': ('desk', 'campos=4.05,3.9,1.25 camto=3.0,5.2,1.1 lens=40'),
       'bedd': ('bed', 'campos=3.7,3.5,1.15 camto=2.95,5.2,0.9 lens=40'),
       'halld': ('hall', 'campos=3.95,3.6,1.25 camto=2.9,5.2,1.0 lens=40'),
       'cord': ('cor', 'campos=3.0,0.35,1.35 camto=5.2,1.5,1.05 lens=35')}       # конец коридора: дверь и растение; там темнее, поэтому ev выше
ALL = ['tv', 'cl', 'tv1', 'tv2', 'sofa', 'bed', 'hall', 'cor', 'sofa1', 'sofa2', 'bed1', 'half', 'desk', 'tvc'] + list(DET)
use = [a for a in sys.argv[1:] if a in ALL] or ALL
white = list(json.load(open(f'{R}/profiles_site.json', encoding='utf-8')))
wood = list(json.load(open(f'{R}/tex3/index.json', encoding='utf-8')))
key = lambda a: a.lower().replace(' ', '').replace('/', '-')
print('# имя  аргументы для scene.py (или "py script.py")')
print('# Галерея применений для сайта: %d белых + %d под дерево × сцены %s, маски стены (tools/photo_jobs.py)' % (len(white), len(wood), ' '.join(use)))
done = lambda n: os.path.exists(f'{R}/out/{n}/{n}.jpg')          # готовые кадры повторно не считаем
for sc in use:
    u, cam = DET.get(sc, (sc, ''))
    e = EXP.get(sc, ('ev=-1.1' if sc in DET else 'ev=-0.9') + ' calfile=cal_photo.json')
    if cam:
        e = cam + ' ' + e
    if not done(f'g_{sc}_mask'):
        print(f'g_{sc}_mask scene=use use={u} decor=A907 mask=1 {B} {cam}'.rstrip())
    for a in white:
        if not done(f'g_{sc}_{key(a)}'):
            print(f'g_{sc}_{key(a)} scene=use use={u} decor={key(a).upper()} {B} {e} {Q}')
    for a in wood:
        if not done(f'g_{sc}_{a}'):
            print(f'g_{sc}_{a} scene=use use={u} decor={a} tex=strip {B} {e} {Q}')
