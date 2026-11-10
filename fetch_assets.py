# Скачивает CC0-ассеты Poly Haven из списка assets.txt в папку assets/ (кэшируется между запусками).
# Формат строки: model|texture|hdri  <id>  <разрешение, напр. 1k>
import json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {'User-Agent': 'nashdekor-render/1.0 (github actions)'}
SKIP = {'blend', 'gltf', 'mtlx', 'usd', 'fbx'}
CANON = [('diff', 'diff'), ('col', 'diff'), ('rough', 'rough'), ('nor_gl', 'nor_gl'), ('disp', 'disp'), ('arm', 'arm'), ('ao', 'ao'),
         ('translucent', 'translucent'), ('alpha', 'alpha'), ('mask', 'mask'), ('metal', 'metal'), ('spec', 'spec'), ('bump', 'bump')]


def get(url, tries=5):
    last = None
    for _ in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
        except Exception as e:  # noqa
            last = e
    raise last


def dl(job):
    url, dst = job
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    data = get(url)
    with open(dst + '.part', 'wb') as f:
        f.write(data)
    os.replace(dst + '.part', dst)


def pick(d, res):
    order = [res, '2k', '1k', '4k', '8k']
    for r in order:
        if r in d:
            return r, d[r]
    r = sorted(d.keys())[0]
    return r, d[r]


def plan(kind, aid, res, only=None):
    root = f'assets/{kind}s/{aid}'
    mark = f'{root}/.done_{res}_{"-".join(sorted(only)) if only else "all"}'
    if os.path.exists(mark):
        return [], mark
    fj = json.loads(get(f'https://api.polyhaven.com/files/{aid}'))
    jobs = []
    if kind == 'model':
        r, e = pick(fj['blend'], res)
        b = e['blend']
        jobs.append((b['url'], f'{root}/{aid}.blend'))
        for rel, inf in (b.get('include') or {}).items():
            jobs.append((inf['url'], f'{root}/{rel}'))
    elif kind == 'texture':
        for key, v in fj.items():
            if key in SKIP or not isinstance(v, dict):
                continue
            kl = key.lower()
            name = next((c for p, c in CANON if kl.startswith(p)), None)
            if kl.startswith('nor_dx') or name is None or (only and name not in only):
                continue
            r, e = pick(v, res)
            fmt = 'jpg' if 'jpg' in e else ('png' if 'png' in e else sorted(e.keys())[0])
            jobs.append((e[fmt]['url'], f'{root}/{name}.{fmt}'))
    elif kind == 'hdri':
        r, e = pick(fj['hdri'], res)
        fmt = 'hdr' if 'hdr' in e else 'exr'
        jobs.append((e[fmt]['url'], f'{root}/{aid}.{fmt}'))
    return jobs, mark


def main():
    items = []
    for ln in open('assets.txt', encoding='utf-8'):
        ln = ln.split('#')[0].split()
        if len(ln) >= 2:
            items.append((ln[0], ln[1], ln[2] if len(ln) > 2 else '1k', set(ln[3].split(',')) if len(ln) > 3 else None))
    bad = 0
    for kind, aid, res, only in items:
        try:
            jobs, mark = plan(kind, aid, res, only)
            if jobs:
                with ThreadPoolExecutor(8) as ex:
                    list(ex.map(dl, jobs))
                open(mark, 'w').write('ok')
                print('fetched', kind, aid, res, len(jobs), 'files')
        except Exception as e:  # noqa
            bad += 1
            print('FAILED', kind, aid, res, repr(e))
    print('assets ready:', len(items) - bad, 'of', len(items))


if __name__ == '__main__':
    main()
