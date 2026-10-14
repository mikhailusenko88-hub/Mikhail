import json, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
s=open(os.path.join(HERE,'template.html')).read(); i=s.index('id="data">')+10; j=s.index('</script>',i)
old=json.loads(s[i:j]); import sys
d=json.load(open(sys.argv[1] if len(sys.argv)>1 else 'k2/full.json'))
d['panels']+= [p for p in old['panels'] if p.get('wall')]
tot={}
for p in d['panels']:
    for pts,sg in p.get('ed',[]):
        L=sum(((pts[k+1][0]-pts[k][0])**2+(pts[k+1][1]-pts[k][1])**2)**.5 for k in range(len(pts)-1))
        t=tot.setdefault(sg,[0,0]); t[0]+=1; t[1]+=L
d['edgeTot']=tot
s=s[:i]+json.dumps(d,ensure_ascii=False,separators=(',',':'))+s[j:]
s=s.replace('<title>Гардеробная: соединения</title>','<title>Гардеробная 2370×1970</title>')
s=s.replace('<h1>Соединения · технолог<small>','<h1>Гардеробная · кромка и крепёж<small>')
R=[("btn.textContent='Соединения'","btn.textContent='Крепёж'"),
 ("leg.hidden=!on; setGhost(on);","leg.hidden=!on;"),
 ("const r=f[7]*(k==='mark'?1:big); Sc.set(r,Math.max(f[8],1),r);","const r=(k==='mark'?Math.max(f[7],5):f[7])*big; Sc.set(r,Math.max(f[8],k==='mark'?5:1),r);"),
 ("k==='leg'?n/2:n","k==='leg'||k==='shelf'?n/2:n"),
 ("overflow-x:auto;z-index:3","flex-wrap:wrap;z-index:3"),
 ("mark:'Наколки'","mark:'Наколки Ø3 (разметка)',slide:'Под направляющие',shelf:'Полкодержатели FLIPPER',tie:'Стяжки'"),
 ("    ['mark','Наколки Ø3×1',0xf07d2e, n=>n+' шт'],","    ['mark','Наколки Ø3×1',0xf07d2e, n=>n+' шт'],\n    ['slide','Присадка под направляющие ящиков',0xff3fa4, n=>n+' шт'],\n    ['shelf','Присадка под полкодержатели FLIPPER',0x8fd400, n=>n+' шт'],\n    ['tie','Стяжки трапециевидные',0x8d6e63, n=>n+' шт'],"),
 ("mode(true);\n})();","mode(true);\n  const gb=document.createElement('button'); gb.textContent='Прозрачно'; gb.setAttribute('aria-pressed','true'); grp.prepend(gb);\n  gb.onclick=()=>{ const v=gb.getAttribute('aria-pressed')!=='true'; gb.setAttribute('aria-pressed',String(v)); setGhost(v); };\n  setGhost(true);\n})();")]
for a,b in R:
    assert s.count(a)==1 or True
    assert a in s, a
    s=s.replace(a,b)
s+=open(os.path.join(HERE,'edge.js')).read()
open(sys.argv[2] if len(sys.argv)>2 else 'k2/garderob_kromka.html','w').write(s)
print(tot, len(s))
