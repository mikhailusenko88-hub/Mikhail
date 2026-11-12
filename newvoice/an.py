import json,glob,numpy as np,re,difflib,statistics as st
E=json.load(open('/home/claude/golos/mk_out/nvs.json'))
d={}
for f in sorted(glob.glob('/home/claude/golos/mk_out/nv_q*.json')): d.update(json.load(open(f,encoding='utf-8')))
def emb(keys): v=np.mean([np.array(E[k]) for k in keys],0); return v/np.linalg.norm(v)
voices=sorted({k.rsplit('_',1)[0] for k in E if not k.startswith('spk_')})
real={k[4:]:np.array(E[k]) for k in E if k.startswith('spk_')}
# один и тот же диктор в разных фразах — уровень «это он»
same=[]
for v in voices:
    if v.startswith('ru_'):
        ks=[f'{v}_{x}' for x in 'abc' if f'{v}_{x}' in E]
        for i in range(len(ks)):
            for j in range(i+1,len(ks)): same.append(float(np.array(E[ks[i]])@np.array(E[ks[j]])))
print(f'один диктор, разные фразы: сходство {min(same):.2f}…{max(same):.2f} (среднее {np.mean(same):.2f})')
def norm(x): return re.sub(r'[^а-яa-z0-9 ]',' ',x.lower().replace('ё','е')).split()
def diffs(t,h):
    a=norm(t); b=norm(h); return [(' '.join(a[i1:i2]),' '.join(b[j1:j2])) for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if tag!='equal' and not re.search(r'\d',' '.join(b[j1:j2]))]
for v in voices:
    ks=[f'{v}_{x}' for x in 'abc' if f'{v}_{x}' in E]; e=emb(ks)
    sims=sorted(((float(e@r),n) for n,r in real.items() if n!=v[3:]),reverse=True)[:3]
    q=[d[k] for k in ks if k in d and 'utmos' in d[k]]
    ut=st.mean(x['utmos'] for x in q) if q else 0; rng=st.mean(x['f0_range'] for x in q) if q else 0
    se=sum(x.get('stress_errors',0) for x in q); df=[dd for x in q for dd in diffs(x['t'],x['heard'])]
    print(f"{v:12s} UTMOS {ut:.2f} | размах {rng:4.1f} пт | ошибок ударения {se} | распознано не так {len(df)} {df[:2]} | ближе всех: "+', '.join(f"{n[3:]} {s:.2f}" for s,n in sims))
