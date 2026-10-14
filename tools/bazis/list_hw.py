import sys, re, collections
src=sys.argv[1]; sys.argv=[sys.argv[0],src,'.','/dev/null']
exec(open('extract.py').read().split("walk(model")[0])
c=collections.Counter(); holes=collections.Counter(); diam=collections.defaultdict(set)
def tree(objs):
    for e in objs:
        if K(e)!='Obj': continue
        o=e[3]; t=get(o,'Type'); n=(get(o,'Name') or '').split('\r')[0]
        if t==3001:
            f=furnmap.get('F%d'%get(o,'FastID')); hs=get(f,'Holes') or [] if f else []
            c[n]+=1; holes[n]+=len(hs)
            for h in hs:
                hv={K(x):x[3] for x in h[3]}; diam[n].add((round(2*hv.get('Radius',0),1),round(hv.get('Depth',0),1)))
        sub=get(o,'Objs')
        if sub: tree(sub)
tree(model)
for n,k in c.most_common(): print(k, holes[n], n[:70], sorted(diam[n])[:6])
