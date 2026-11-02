# Проверяет домены из request.txt через whois и пишет status/result.md
import subprocess, re, datetime, time
FREE = [r'No entries found', r'No match for', r'NOT FOUND', r'No Data Found',
        r'Domain not found', r'is available', r'Status:\s*free', r'The queried object does not exist']
def server(a):
    return 'whois.tcinet.ru' if a.rsplit('.', 1)[-1] in ('ru', 'su', 'xn--p1ai') else None
def check(d):
    a = d.encode('idna').decode() if not d.isascii() else d
    cmd = ['whois'] + (['-h', server(a)] if server(a) else []) + [a]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout
    except Exception as e:
        return a, '?', f'ошибка whois: {e}'
    if any(re.search(p, out, re.I) for p in FREE):
        return a, 'свободен', ''
    if re.search(r'^\s*(domain|Domain Name):', out, re.I | re.M):
        info = []
        for k in ('registrar', 'Registrar', 'created', 'Creation Date', 'paid-till', 'Registry Expiry Date'):
            m = re.search(rf'^\s*{k}:\s*(.+)$', out, re.M)
            if m: info.append(f'{k}: {m.group(1).strip()}')
        return a, 'занят', '; '.join(info[:3])
    tail = out.strip().splitlines()[-1][:120] if out.strip() else 'пустой ответ'
    return a, '?', tail
rows = []
for line in open('request.txt', encoding='utf-8'):
    d = line.strip().lower()
    if not d or d.startswith('#'): continue
    rows.append((d,) + check(d))
    time.sleep(1.5)
now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
md = [f'# Проверка доменов — {now}', '', '| Домен | Статус | Подробности |', '|---|---|---|']
for d, a, st, info in sorted(rows, key=lambda r: (r[2] != 'свободен', r[0])):
    md.append(f"| {d if d == a else f'{d} ({a})'} | {st} | {info} |")
open('status/result.md', 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('\n'.join(md))
