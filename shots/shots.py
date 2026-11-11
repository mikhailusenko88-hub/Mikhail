#!/usr/bin/env python3
"""Скриншоты страниц nashdekor.ru: компьютер 1280×900 (DPR 2) и телефон 390×844 (DPR 3)."""
import os, time
from playwright.sync_api import sync_playwright
from PIL import Image
OUT = 'status/shots'; os.makedirs(OUT, exist_ok=True)
rows = [[c.strip() for c in l.split('|')] for l in open('shots/list.txt', encoding='utf-8') if '|' in l and not l.startswith('#')]
rep = ['# Скриншоты сайта — ' + time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()), '']
with sync_playwright() as p:
    br = p.chromium.launch(channel='chrome', args=['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'])
    for r in rows:
        name, url, mode = r[0], r[1], (r[2] if len(r) > 2 else 'desktop'); js = r[3] if len(r) > 3 else ''
        if mode == 'mobile':
            ctx = br.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                                 user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
        else:
            ctx = br.new_context(viewport={'width': 1280, 'height': 900}, device_scale_factor=2)
        pg = ctx.new_page(); errs, fails = [], []
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.on('requestfailed', lambda q: fails.append(q.url))
        pg.on('response', lambda s: fails.append(f'{s.status} {s.url}') if s.status >= 400 else None)
        try:
            pg.goto(url, wait_until='networkidle', timeout=45000)
            if js: pg.evaluate(js); time.sleep(2.5)
            time.sleep(1.5)
            path = os.path.join(OUT, name + '.png'); pg.screenshot(path=path, full_page=False)
            im = Image.open(path).convert('RGB'); im.save(path.replace('.png', '.jpg'), quality=82); os.remove(path)
            rep.append(f'- **{name}** {mode} {url} — ok' + (f'; ошибки консоли: {errs[:3]}' if errs else '') + (f'; не загрузилось: {fails[:5]}' if fails else ''))
        except Exception as e:
            rep.append(f'- **{name}** {mode} {url} — ОШИБКА {e}')
        ctx.close()
    br.close()
open('status/shots.md', 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
print('\n'.join(rep))
