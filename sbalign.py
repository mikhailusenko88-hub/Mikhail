# Склейка дорожки сборника на языке L по образцу английской: места серий ищутся корреляцией огибающей
# английских дорожек серий с английской дорожкой сборника; затем дорожки серий на L кладутся на те же места.
import subprocess, sys, numpy as np
SR=8000
def load(p): return np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',p,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True).stdout,np.float32).astype(np.float64)
def env(x,h=80): n=len(x)//h; return np.sqrt((x[:n*h].reshape(n,h)**2).mean(1))
def main(sb_en, eps_en, eps_l, out, label):
    S=load(sb_en); E=env(S); starts=[]; t=0.0
    for p in eps_en:
        x=load(p); e=env(x[:SR*30])
        c0=int(t*SR/80); lo=max(0,c0-400); hi=c0+400
        best=None
        for k in range(lo,hi):
            seg=E[k:k+len(e)]
            if len(seg)<len(e): break
            v=np.dot(seg-seg.mean(),e-e.mean())/(np.linalg.norm(seg-seg.mean())*np.linalg.norm(e-e.mean())+1e-9)
            if best is None or v>best[0]: best=(v,k)
        st=best[1]*80/SR; starts.append(st); print(label,p,'начало',round(st,3),'сходство',round(best[0],3),'ожидалось',round(t,3))
        t=st+len(x)/SR
    total=len(S)/SR
    # сборка: каждая серия на своё место, обрезка до начала следующей / конца
    parts=[]; 
    for i,p in enumerate(eps_l):
        d=(starts[i+1] if i+1<len(starts) else total)-starts[i]
        parts.append((p,starts[i],d))
    flt=[]; ins=[]
    for i,(p,st,d) in enumerate(parts):
        ins+=['-i',p]; flt.append(f"[{i}:a]aresample=44100,apad,atrim=0:{d:.4f},asetpts=PTS-STARTPTS[a{i}]")
    lead=starts[0]
    pre=f"anullsrc=r=44100:cl=stereo,atrim=0:{lead:.4f}[z];" if lead>0.001 else ""
    cat=("[z]" if pre else "")+"".join(f"[a{i}]" for i in range(len(parts)))
    n=len(parts)+(1 if pre else 0)
    fc=pre+";".join(flt)+f";{cat}concat=n={n}:v=0:a=1[o]"
    subprocess.run(['ffmpeg','-y','-v','error',*ins,'-filter_complex',fc,'-map','[o]','-ac','2','-c:a','libmp3lame','-b:a','192k',out],check=True)
    d=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',out],capture_output=True,text=True).stdout)
    print(label,'итог',out,round(d,3),'англ',round(total,3))
if __name__=='__main__':
    a=sys.argv[1:]; sb=a[0]; n=(len(a)-3)//2; main(sb,a[1:1+n],a[1+n:1+2*n],a[-2],a[-1])
