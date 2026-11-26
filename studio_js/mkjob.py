# mkjob.py <ep> <build> <perevod> <coverbuild> <videoid> <out.json> [langs]
import json, subprocess, sys
ep, build, pv, cb, vid, out = sys.argv[1:7]
langs = (sys.argv[7] if len(sys.argv) > 7 else 'en es pt hi de fr ar').split()
NM = dict(en='English', es='Spanish', pt='Portuguese', hi='Hindi', de='German', fr='French', ar='Arabic')
R = 'mikhailusenko88-hub/Mikhail'
def sha(path):
    try:
        s = subprocess.run(['gh', 'api', f'repos/{R}/commits?sha=dub-files&path={path}&per_page=1', '--jq', '.[0].sha'], capture_output=True, text=True).stdout.strip()
        return s or None
    except Exception: return None
p = json.load(open(f'/home/claude/golos-en/perevod/{pv}.json'))
jobs = []; rep = []
for l in langs:
    y = p['yt'][l]; j = {'lang': NM[l], 'title': y['title'], 'desc': y['desc']}
    for cpath in (f'{build}/cover_{l}.jpg', f'{cb}/cover_{l}.jpg'):
        s = sha(cpath)
        if s: j['cover'] = f'https://raw.githubusercontent.com/{R}/{s}/{cpath}'; j['cname'] = f'Barsik-{ep}-{l}.jpg'; break
    s = sha(f'{build}/dub_{l}.mp3')
    if s: j['audio'] = f'https://raw.githubusercontent.com/{R}/{s}/{build}/dub_{l}.mp3'; j['aname'] = f'Barsik-{ep}-{l}.mp3'
    rep.append(f"{l}:{'обл' if 'cover' in j else '-'}/{'звук' if 'audio' in j else '-'}")
    jobs.append(j)
json.dump({ep: {'id': vid, 'jobs': jobs}}, open(out, 'w'), ensure_ascii=False, indent=0)
print(' '.join(rep))
