# Список CC0-ассетов Poly Haven + контактные листы превью, чтобы выбрать мебель и текстуры глазами.
import io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

OUT = 'out/probe'
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'nashdekor-render/1.0 (github actions)'}


def get(url, tries=4):
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception as e:  # noqa
            last = e
    raise last


def font(sz):
    try:
        return ImageFont.load_default(sz)
    except Exception:
        return ImageFont.load_default()


F = font(12)


def thumb(a):
    aid, d = a
    url = (d.get('thumbnail_url') or f'https://cdn.polyhaven.com/asset_img/thumbs/{aid}.png').split('?')[0] + '?width=150&height=150'
    try:
        im = Image.open(io.BytesIO(get(url))).convert('RGBA')
        bg = Image.new('RGBA', im.size, (245, 245, 245, 255))
        bg.alpha_composite(im)
        im = bg.convert('RGB')
        im.thumbnail((150, 150))
        return aid, im
    except Exception as e:  # noqa
        print('thumb fail', aid, e)
        return aid, Image.new('RGB', (150, 150), (200, 60, 60))


def sheets(prefix, items, per=80, cols=10):
    with ThreadPoolExecutor(16) as ex:
        th = dict(ex.map(thumb, items))
    for s in range(0, len(items), per):
        part = items[s:s + per]
        rows = (len(part) + cols - 1) // cols
        sh = Image.new('RGB', (cols * 156, rows * 186), 'white')
        dr = ImageDraw.Draw(sh)
        for i, (aid, d) in enumerate(part):
            x, y = (i % cols) * 156, (i // cols) * 186
            im = th[aid]
            sh.paste(im, (x + 3 + (150 - im.width) // 2, y + 2 + (150 - im.height) // 2))
            dr.text((x + 3, y + 153), aid[:24], fill='black', font=F)
            if len(aid) > 24:
                dr.text((x + 3, y + 167), aid[24:48], fill='black', font=F)
        fn = f'{OUT}/{prefix}_{s // per + 1:02d}.jpg'
        sh.save(fn, quality=82)
        print('sheet', fn, len(part))


def has(d, words):
    blob = ' '.join(d.get('categories', []) + d.get('tags', [])).lower() + ' ' + d.get('name', '').lower()
    return any(w in blob for w in words)


allm = json.loads(get('https://api.polyhaven.com/assets?t=models'))
allt = json.loads(get('https://api.polyhaven.com/assets?t=textures'))
allh = json.loads(get('https://api.polyhaven.com/assets?t=hdris'))
print('models', len(allm), 'textures', len(allt), 'hdris', len(allh))
k0 = next(iter(allm))
print('model keys', sorted(allm[k0].keys()))
print('texture keys', sorted(allt[next(iter(allt))].keys()))

for nm, dd in (('models', allm), ('textures', allt), ('hdris', allh)):
    with open(f'{OUT}/{nm}.tsv', 'w', encoding='utf-8') as f:
        for aid, d in sorted(dd.items()):
            f.write('\t'.join([aid, d.get('name', ''), ','.join(d.get('categories', [])), ','.join(d.get('tags', [])[:10]),
                               str(d.get('dimensions', '')), str(d.get('polycount', '')), str(d.get('max_resolution', '')),
                               str(d.get('download_count', ''))]) + '\n')

cats = {}
for d in allm.values():
    for c in d.get('categories', []):
        cats[c] = cats.get(c, 0) + 1
print('model categories', sorted(cats.items(), key=lambda t: -t[1]))
cats = {}
for d in allt.values():
    for c in d.get('categories', []):
        cats[c] = cats.get(c, 0) + 1
print('texture categories', sorted(cats.items(), key=lambda t: -t[1]))

W_FURN = ['furniture', 'seating', 'sofa', 'couch', 'armchair', 'chair', 'table', 'shelf', 'shelves', 'cabinet', 'bed', 'console',
          'lighting', 'lamp', 'decorative', 'appliance', 'potted', 'houseplant', 'indoor', 'vase', 'book', 'rug', 'carpet',
          'television', 'frame', 'painting', 'mirror', 'curtain', 'pillow', 'cushion', 'blanket', 'basket', 'clock', 'candle',
          'bowl', 'plant', 'flower', 'tray', 'ottoman', 'stool', 'bench', 'desk', 'wardrobe', 'dresser', 'nightstand']
W_SKIP = ['tree', 'rock', 'stump', 'weapon', 'vehicle', 'grass', 'ground', 'debris', 'barrel', 'street', 'outdoor']
ms = [(a, d) for a, d in allm.items() if has(d, W_FURN) and not has(d, W_SKIP)]
ms.sort(key=lambda t: (','.join(t[1].get('categories', [])), -int(t[1].get('download_count', 0) or 0)))
print('models chosen', len(ms))
sheets('models', ms)

W_TEX = ['wood', 'floor', 'plaster', 'wall', 'fabric', 'carpet', 'concrete', 'leather', 'paint', 'veneer', 'parquet', 'laminate', 'rug']
T_SKIP = ['terrain', 'rock', 'bark', 'roof', 'aerial', 'sand', 'snow', 'mud', 'cliff', 'forest', 'brick']
ts = [(a, d) for a, d in allt.items() if has(d, W_TEX) and not has(d, T_SKIP)]
ts.sort(key=lambda t: (','.join(t[1].get('categories', [])), -int(t[1].get('download_count', 0) or 0)))
print('textures chosen', len(ts))
sheets('tex', ts)

# структура файлов — для загрузчика
for aid in ['oak_veneer_01', k0]:
    try:
        fj = json.loads(get(f'https://api.polyhaven.com/files/{aid}'))
        print('files', aid, {k: (sorted(v.keys()) if isinstance(v, dict) else v) for k, v in fj.items()})
        for k, v in fj.items():
            if isinstance(v, dict):
                r = v.get('1k') or next(iter(v.values()))
                print('  ', k, json.dumps(r)[:400])
    except Exception as e:  # noqa
        print('files fail', aid, e)
