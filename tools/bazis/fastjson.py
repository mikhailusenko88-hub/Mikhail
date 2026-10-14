import sys, json, re
src, code, base, out = sys.argv[1:5]
sys.argv=[sys.argv[0],src,code,'/dev/null']
exec(open(code+'/extract.py').read().split("walk(model")[0])
def cat(n):
    if re.search('Шкант',n): return 'dowel'
    if re.search('Конфирмат',n): return 'confirmat'
    if re.search('Rastex|Эксцентрик',n,re.I): return 'cam'
    if re.search('Направляющ',n) or n in ('3x3','6x10'): return 'slide'
    if re.search('FLIPPER|полкодерж',n,re.I): return 'shelf'
    if re.search('Стяжка',n): return 'tie'
    if re.search('Саморез|Отв',n): return 'screw'
    if n in ('10','16x3'): return 'leg'
    if n=='3x1': return 'mark'
    return None
F=[]; cnt={}
def tree(objs,X):
    for e in objs:
        if K(e)!='Obj': continue
        o=e[3]; t=get(o,'Type'); n=(get(o,'Name') or '').split('\r')[0]
        LX=compose(X,trans(o))
        if t==3001:
            f=furnmap.get('F%d'%get(o,'FastID')); c=cat(n)
            if f and c:
                cnt[c]=cnt.get(c,0)+1
                for h in get(f,'Holes') or []:
                    hv={K(x):x[3] for x in h[3]}
                    p=compose(LX,((0,0,0,1),(hv.get('X',0),hv.get('Y',0),hv.get('Z',0))))[1]
                    d=qrot(LX[0],(hv.get('DirX',0),hv.get('DirY',0),hv.get('DirZ',0)))
                    F.append([c]+[round(v,1) for v in p]+[round(v,4) for v in d]+[hv.get('Radius',2),hv.get('Depth',5),n])
        sub=get(o,'Objs')
        if sub: tree(sub,LX)
tree(model,((0,0,0,1),(0,0,0)))
d=json.load(open(base)); d['fast']=F; d['fastCount']=cnt
json.dump(d,open(out,'w'),ensure_ascii=False,separators=(',',':'))
print(cnt, len(F))
