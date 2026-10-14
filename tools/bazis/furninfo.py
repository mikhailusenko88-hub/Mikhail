import sys,re
src=sys.argv[1]; pat=sys.argv[2]; sys.argv=[sys.argv[0],src,'.','/dev/null']
exec(open('extract.py').read().split("walk(model")[0])
seen=set()
def show(es,ind=0):
    for e in es:
        k=K(e); v=e[3]
        if isinstance(v,list):
            if k in('TriData','Holes'): print(' '*ind+k,'[...]'); continue
            print(' '*ind+k); show(v,ind+2)
        elif isinstance(v,(bytes,bytearray)): print(' '*ind+k,'<blob>')
        else: print(' '*ind+k,'=',repr(v)[:120])
def tree(objs):
    for e in objs:
        if K(e)!='Obj': continue
        o=e[3]; t=get(o,'Type'); n=(get(o,'Name') or '')
        if t==3001 and re.search(pat,n) and n not in seen:
            seen.add(n); print('### OBJ',n); show([x for x in o if K(x) not in('Objs',)])
            f=furnmap.get('F%d'%get(o,'FastID')); print('### FURN'); show(f)
        sub=get(o,'Objs')
        if sub: tree(sub)
tree(model)
