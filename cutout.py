"""Вырезать образцы с фото (фон — стол и стена): маска для каждого фото каждой моделью из models.txt.
Результат: cut/<модель>/<имя>.png (RGBA, исходный размер). Пропускает уже сделанные."""
import glob, os, time
from PIL import Image
from rembg import new_session, remove

models = [m.strip() for m in open('models.txt') if m.strip() and not m.startswith('#')]
for m in models:
    t = time.time()
    s = new_session(m)
    os.makedirs(f'cut/{m}', exist_ok=True)
    files = sorted(glob.glob('in/*.jpg'))
    k, n = int(os.environ.get('SHARD', 0)), int(os.environ.get('NSHARD', 1))
    for f in files[k::n]:
        name = os.path.splitext(os.path.basename(f))[0]
        out = f'cut/{m}/{name}.png'
        if os.path.exists(out):
            continue
        im = Image.open(f).convert('RGB')
        res = remove(im, session=s, post_process_mask=True)
        res.save(out)
        print(m, name, 'ok %.1fs' % (time.time() - t), flush=True)
