import json,sys
d=json.load(open(sys.argv[1]))
for k,m in d['movers'].items():
    ps=[p for p in d['panels'] if p.get('mv')==int(k)]
    if not ps: continue
    box=[p for p in ps if p['n']!='Фасад']
    blo=[min(p['bb'][0][i] for p in box) for i in range(3)]; bhi=[max(p['bb'][1][i] for p in box) for i in range(3)]
    fa=[p['size'] for p in ps if p['n']=='Фасад']
    print(k,m['code'],m['name'][:30],'фасад',fa,'короб',[bhi[i]-blo[i] for i in range(3)])
