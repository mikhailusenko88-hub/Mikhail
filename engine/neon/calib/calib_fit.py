import numpy as np, struct, json, sys
from PIL import Image
W,H=1280,720
b=open('web/scene.bin','rb').read(); n=struct.unpack('<I',b[4:8])[0]; h=json.loads(b[8:8+n])
order=[('p',i,h['patches'][i]['nv']) for i in range(10)]+[('g',10,h['ground']['nv'])]
for t in range(3): order+= [('t',11+t*2,h['trees'][t]['tnv']),('l',12+t*2,h['trees'][t]['lnv'])]
nvs={o[1]:o[2] for o in order}
def lin(a): a=a.astype(np.float32)/255; return np.where(a<=0.04045,a/12.92,((a+0.055)/1.055)**2.4)
train=[20,50,80,110,140,170,200,215,230]; test=[120,210]
indir=sys.argv[1]; outp=sys.argv[2]; prev=sys.argv[3] if len(sys.argv)>3 else None; damp=float(sys.argv[4]) if len(sys.argv)>4 else 0.7
S={o:np.zeros((nv,3),np.float64) for o,nv in nvs.items()}; Wt={o:np.zeros(nv,np.float64) for o,nv in nvs.items()}
def metrics(f,p):
    ref=np.asarray(Image.open(f'calib/ref/f_{f:04d}.ppm').convert('RGB')).astype(float); pr=np.asarray(Image.open(p).convert('RGB')).astype(float)
    d=np.abs(ref-pr); zones={'верх':(slice(0,240)),'середина':(slice(240,480)),'низ':(slice(480,720))}
    return d.mean(), {k:(ref[z].mean()-pr[z].mean()) for k,z in zones.items()}
for f in train:
    ref=lin(np.asarray(Image.open(f'calib/ref/f_{f:04d}.ppm').convert('RGB'))); pr=lin(np.asarray(Image.open(f'{indir}/p_{f}.png').convert('RGB')))
    px=np.frombuffer(open(f'calib/r0/id_{f}.bin','rb').read(),np.uint8).reshape(H,W,4)[::-1]
    obj=px[...,3].astype(int); vid=px[...,0].astype(int)|(px[...,1].astype(int)<<8)|(px[...,2].astype(int)<<16)
    key=obj*(1<<24)+vid
    # вес: доля соседей с тем же диодом (края и тонкие травинки весят меньше)
    same=np.zeros((H,W)); 
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if dy==0 and dx==0: continue
            same+= (np.roll(np.roll(key,dy,0),dx,1)==key)
    w=0.2+0.8*same/8
    r=np.log(np.clip(ref,1e-3,None)/np.clip(pr,1e-3,None)); r=np.clip(r,-1.4,1.4)
    valid=(obj!=255)
    for o,nv in nvs.items():
        m=valid&(obj==o)
        if not m.any(): continue
        v=vid[m]; ww=w[m]; rr=r[m]
        np.add.at(Wt[o],v,ww)
        for c in range(3): np.add.at(S[o][:,c],v,ww*rr[:,c])
out=bytearray()
if prev: P=np.frombuffer(open(prev,'rb').read(),np.uint8)
off=0; seen=0; tot=0
for kind,o,nv in order:
    cur=np.full((nv,3),128.0)
    if prev: cur=P[off:off+nv*3].reshape(nv,3).astype(float)
    off+=nv*3
    good=Wt[o]>=1.5; seen+=good.sum(); tot+=nv
    lr=np.zeros((nv,3)); lr[good]=S[o][good]/Wt[o][good][:,None]
    lr=np.clip(lr*damp,-0.9,0.9)                       # с демпфированием, не больше ×2.5 за круг
    cur=cur+lr/np.log(2)*64                            # код: 128 + 64*log2(ratio)
    cur=np.clip(cur,64,192)                            # итог в пределах ×0.5…×2
    out+=np.round(cur).astype(np.uint8).tobytes()
open(outp,'wb').write(out); print('diodes seen',seen,'of',tot, 'bytes',len(out))
for f in train+test:
    m,z=metrics(f,f'{indir}/p_{f}.png'); print(('TEST ' if f in test else 'train')+f'{f}: средн.|разн.| {m:.2f}  сдвиг по зонам '+', '.join(f'{k} {v:+.1f}' for k,v in z.items()))
