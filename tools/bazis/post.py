import json,sys
d=json.load(open(sys.argv[1]))
def qrot(q,v):
    x,y,z,w=q; vx,vy,vz=v
    tx=2*(y*vz-z*vy); ty=2*(z*vx-x*vz); tz=2*(x*vy-y*vx)
    return (vx+w*tx+(y*tz-z*ty), vy+w*ty+(z*tx-x*tz), vz+w*tz+(x*ty-y*tx))
mods={}
for p in d['panels']:
    P=[]
    for a,b in p['pts']:
        for z in (0,p['th']):
            r=qrot(p['q'],(a,b,z)); P.append([r[i]+p['t'][i] for i in range(3)])
    p['bb']=[[round(min(x[i] for x in P)) for i in range(3)],[round(max(x[i] for x in P)) for i in range(3)]]
    xs=[a for a,b in p['pts']]; ys=[b for a,b in p['pts']]
    dims=sorted([max(xs)-min(xs),max(ys)-min(ys)],reverse=True)
    p['size']=f"{dims[0]:.0f} × {dims[1]:.0f} × {p['th']:.0f}"
    if p['code']:
        m=mods.setdefault(p['code'],[[1e9]*3,[-1e9]*3])
        for i in range(3): m[0][i]=min(m[0][i],p['bb'][0][i]); m[1][i]=max(m[1][i],p['bb'][1][i])
for p in d['panels']:
    if not p['code'] and not p['wall']:
        c=[(p['bb'][0][i]+p['bb'][1][i])/2 for i in range(3)]
        for k,m in mods.items():
            if all(m[0][i]-1<=c[i]<=m[1][i]+1 for i in range(3)): p['code']=k; break
for pr in d['procs']:
    c=qrot(pr['q'],(332,-60,256)); c=[c[i]+pr['t'][i] for i in range(3)]
    pr['code']=next((k for k,m in mods.items() if all(m[0][i]-1<=c[i]<=m[1][i]+1 for i in range(3))),'')
for k,mv in d['movers'].items():
    cs=[p['code'] for p in d['panels'] if p.get('mv')==int(k)]+[pr['code'] for pr in d['procs'] if pr['mv']==int(k)]
    mv['code']=cs[0] if cs else ''
d['mods']={k:[[round(v) for v in m[0]],[round(v) for v in m[1]]] for k,m in mods.items()}
for p in d['panels']: p.pop('id',None)
json.dump(d,open(sys.argv[2],'w'),ensure_ascii=False,separators=(',',':'))
print(d['mods']); print(sum(1 for p in d['panels'] if not p['code']))
