import sys, struct, math, json, base64, re
sys.path.insert(0, sys.argv[2]); from bz import *
hk,he,fk,fe=load_file(sys.argv[1])
K=lambda e: fk[e[0]] if e[0]<len(fk) else '#'
def get(es,name):
    for e in es:
        if K(e)==name: return e[3]
def getall(es,name): return [e[3] for e in es if K(e)==name]
doc=get(fe,'Document'); model=get(doc,'Model'); furn=get(doc,'FurnList')
furnmap={K(e):e[3] for e in furn}
def qmul(a,b):
    ax,ay,az,aw=a; bx,by,bz,bw=b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)
def qrot(q,v):
    x,y,z,w=q; vx,vy,vz=v
    # v' = q v q*
    tx=2*(y*vz-z*vy); ty=2*(z*vx-x*vz); tz=2*(x*vy-y*vx)
    return (vx+w*tx+(y*tz-z*ty), vy+w*ty+(z*tx-x*tz), vz+w*tz+(x*ty-y*tx))
def compose(P,L):  # P parent (q,t), L local
    q=qmul(P[0],L[0]); r=qrot(P[0],L[1]); return (q,(r[0]+P[1][0],r[1]+P[1][1],r[2]+P[1][2]))
def trans(o):
    t=get(o,'Trans')
    if not t: return ((0,0,0,1),(0,0,0))
    g=lambda n: get(t,n) or 0.0
    q=(g('Rx'),g('Ry'),g('Rz'),get(t,'Rw') if get(t,'Rw') is not None else 1.0)
    return (q,(g('X'),g('Y'),g('Z')))
def contour(blob):
    r=R(blob); n=r.u32(); segs=[]; circles=[]
    for _ in range(n):
        t=r.u8()
        if t==0x10:
            x1,y1,x2,y2=[r.f64() for _ in range(4)]; segs.append([(x1,y1),(x2,y2)])
        elif t==0x12:
            cx,cy,sx,sy,ex,ey=[r.f64() for _ in range(6)]; ccw=r.u8()
            rad=math.hypot(sx-cx,sy-cy); a0=math.atan2(sy-cy,sx-cx); a1=math.atan2(ey-cy,ex-cx)
            if ccw:
                while a1<=a0+1e-9: a1+=2*math.pi
            else:
                while a1>=a0-1e-9: a1-=2*math.pi
            m=max(4,int(abs(a1-a0)/(math.pi/24)))
            segs.append([(cx+rad*math.cos(a0+(a1-a0)*i/m), cy+rad*math.sin(a0+(a1-a0)*i/m)) for i in range(m+1)])
        elif t in (0x11,0x14):
            cx,cy,rad=r.f64(),r.f64(),r.f64(); m=48
            circles.append([(cx+rad*math.cos(2*math.pi*i/m), cy+rad*math.sin(2*math.pi*i/m)) for i in range(m)])
        else: raise ValueError('seg type %x'%t)
    # chain into loops
    loops=[]; rest=segs[:]
    near=lambda a,b: abs(a[0]-b[0])<0.05 and abs(a[1]-b[1])<0.05
    while rest:
        cur=list(rest.pop(0))
        changed=True
        while changed and not near(cur[0],cur[-1]):
            changed=False
            for i,s in enumerate(rest):
                if near(s[0],cur[-1]): cur+=s[1:]; rest.pop(i); changed=True; break
                if near(s[-1],cur[-1]): cur+=s[::-1][1:]; rest.pop(i); changed=True; break
        if near(cur[0],cur[-1]): cur=cur[:-1]
        loops.append(cur)
    return loops+circles
def elems(blob):
    r=R(blob); n=r.u32(); out=[]
    for _ in range(n):
        t=r.u8()
        if t==0x10: x1,y1,x2,y2=[r.f64() for _ in range(4)]; out.append([[x1,y1],[x2,y2]])
        elif t==0x12:
            cx,cy,sx,sy,ex,ey=[r.f64() for _ in range(6)]; ccw=r.u8()
            rad=math.hypot(sx-cx,sy-cy); a0=math.atan2(sy-cy,sx-cx); a1=math.atan2(ey-cy,ex-cx)
            if ccw:
                while a1<=a0+1e-9: a1+=2*math.pi
            else:
                while a1>=a0-1e-9: a1-=2*math.pi
            m=max(4,int(abs(a1-a0)/(math.pi/24)))
            out.append([[cx+rad*math.cos(a0+(a1-a0)*i/m), cy+rad*math.sin(a0+(a1-a0)*i/m)] for i in range(m+1)])
        elif t in (0x11,0x14):
            cx,cy,rad=r.f64(),r.f64(),r.f64(); out.append([[cx+rad*math.cos(2*math.pi*i/48), cy+rad*math.sin(2*math.pi*i/48)] for i in range(49)])
    return out
def area(l): return 0.5*sum(l[i][0]*l[(i+1)%len(l)][1]-l[(i+1)%len(l)][0]*l[i][1] for i in range(len(l)))
def tridata(blob):
    r=R(blob); n=r.u32(); out=[]
    for _ in range(n):
        ml=r.u32(); mat=r.raw(2*ml).decode('utf-16le','replace')
        M=[r.f64() for _ in range(16)]; r.u8(); nt=r.u32()
        tris=[]
        for _ in range(nt):
            f=struct.unpack_from('<9f',r.b,r.p); r.p+=112; tris.append(f)
        out.append((mat,M,tris))
    return out
SKIP=re.compile(r'Отв|Евровинт|Конфирмат|Шкант|Саморез|винт|Rastex|DU ?232|Клипса|Эксцентрик|^\d+$|^\d+x\d+',re.I)
panels=[]; meshes={}; walls=[]; stats={}
def addtris(key, tris, X):
    buf=meshes.setdefault(key,[])
    for f in tris:
        for i in range(3):
            p=compose(X,((0,0,0,1),(f[3*i],f[3*i+1],f[3*i+2])))[1]; buf.extend(p)
def matkey(mat,name):
    s=(mat or '')+' '+(name or '')
    if re.search('хром|Труба|Направл|Брючница|Корзина|сталь|металл',s,re.I): return 'metal'
    if re.search('антрацит|Пластик|Ножк|База',s,re.I): return 'plastic'
    return 'metal'
movers={}; procs=[]
def walk(objs, X, mod, depth=0):
    for e in objs:
        if K(e)!='Obj': continue
        o=e[3]; t=get(o,'Type'); name=get(o,'Name') or ''
        stats[t]=stats.get(t,0)+1
        LX=compose(X,trans(o))
        mv=mod; childmod=mod
        if t==1005 and re.match(r'(Ящик|Корзина|Брючница)',name):
            kind='drawer' if name.startswith('Ящик') else ('basket' if name.startswith('Корзина') else 'trousers')
            mid=len(movers); movers[mid]=dict(kind=kind,name=name.split('\r')[0],dir=[round(v,4) for v in qrot(LX[0],(0,0,1))],dist=400 if kind=='drawer' else 420,pos=LX[1])
            if kind!='drawer': mv=mid
            else: childmod=('pending',mid)
        if t==1005 and name=='Анимация' and isinstance(mod,tuple): mv=mod[1]; childmod=mv
        if isinstance(mv,tuple): mv=None
        if childmod==mod and mv!=mod: childmod=mv
        if t==4002:
            loops=contour(get(o,'Contour')); loops.sort(key=lambda l:-abs(area(l)))
            mat=get(o,'Mat') or ''
            m=re.match(r'^([А-ЯA-Z]+\d+):\s*(.*)',name)
            code=m.group(1) if m else ''
            panels.append(dict(n=name,code=code,mat=mat.split('\r')[0],th=get(o,'Thick'),q=LX[0],t=LX[1],
                pts=[[round(a,2),round(b,2)] for a,b in loops[0]],holes=[[[round(a,2),round(b,2)] for a,b in l] for l in loops[1:]],
                wall=name.startswith('Стена'), mv=mv, id=get(o,'ID'), art=get(o,'ArtPos'), ne=len(elems(get(o,'Contour'))),
                ed=[[[[round(a,1),round(b,1)] for a,b in elems(get(o,'Contour'))[get(bt,'Elem')]], get(bt,'Sign') or '%gмм'%(get(bt,'Thick') or 0)]
                    for bt in getall(get(o,'Butts') or [],'Butt') if get(bt,'Elem') is not None and get(bt,'Elem')<len(elems(get(o,'Contour')))]))
        elif t==2004:
            loops=contour(get(o,'Contour')); loops.sort(key=lambda l:-abs(area(l)))
            panels.append(dict(n=name,code='',mat=(get(o,'Mat') or '').split('\r')[0],th=get(o,'Thickness'),q=LX[0],t=LX[1],
                pts=[[round(a,2),round(b,2)] for a,b in loops[0]],holes=[[[round(a,2),round(b,2)] for a,b in l] for l in loops[1:]],prof=True,wall=False,mv=mv))
        elif t==3001:
            if SKIP.search(name) or get(o,'Color')==255: continue
            f=furnmap.get('F%d'%get(o,'FastID'))
            if not f: continue
            td=get(f,'TriData')
            if not td: continue
            for mat,M,tris in tridata(td):
                MX=((0,0,0,1),(M[12],M[13],M[14]))  # assume rotation identity in mesh matrix
                addtris((matkey(mat,name),mv), tris, compose(LX,MX))
        elif t==10000:
            procs.append(dict(kind=movers[mv]['kind'] if mv is not None else 'box',mv=mv,q=LX[0],t=LX[1],n=name.split('\r')[0]))
        if t in (1005,4001,10000,3001):
            sub=get(o,'Objs')
            if sub: walk(sub, LX, childmod, depth+1)
walk(model,((0,0,0,1),(0,0,0)),None)
print(stats, len(panels), {k:len(v)//9 for k,v in meshes.items()}, file=sys.stderr)
# check mesh matrices rotation
out=dict(panels=panels, movers=movers, procs=procs, meshes=[dict(k=k[0],mv=k[1],b=base64.b64encode(struct.pack('<%df'%len(v),*v)).decode()) for k,v in meshes.items()])
json.dump(out,open(sys.argv[3],'w'),ensure_ascii=False)
