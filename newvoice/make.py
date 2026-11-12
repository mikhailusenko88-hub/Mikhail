# Новые голоса: смесь отпечатков мужских дикторов, вписанная в свободные строки таблиц (дикторы-двойники на других языках).
import json,numpy as np,sys,shutil,os
sys.path.insert(0,'/home/claude/newvoice'); from emb import *
SRC='/home/claude/mv/voice'; DST=sys.argv[1] if len(sys.argv)>1 else '/home/claude/mvx/voice'
recipes=json.load(open(sys.argv[2] if len(sys.argv)>2 else 'recipes.json'))
meta=json.load(open(f'{SRC}/tts.json')); S=meta['speakers']
male=['ru_alexandr','ru_bogdan','ru_dmitriy','ru_eduard','ru_igor','ru_roman']; fem=['ru_albina','ru_zinaida','ru_ekaterina','ru_vika','ru_karina','ru_oksana']
SLOTS=[0,2,4,6,8,10,11,13,15,17,19,21,23,25,27,29]
def mix(tab,r):
    W=r['w']; v=sum(w*tab[S[k]] for k,w in W.items()); src_norm=np.mean([np.linalg.norm(tab[S[k]]) for k in W])
    if r.get('push'): mm=np.mean([tab[S[k]] for k in male],0); fm=np.mean([tab[S[k]] for k in fem],0); v=v+r['push']*(mm-fm)
    if r.get('noise'):
        rng=np.random.default_rng(r['noise']['seed']*1000+tab.shape[1]); z=rng.standard_normal(tab.shape[1])
        Q,_=np.linalg.qr(tab[[S[k] for k in S if k.startswith('ru_')]].T); z=z-Q@(Q.T@z)   # без составляющих реальных дикторов
        v=v/np.linalg.norm(v)+r['noise']['beta']*z/np.linalg.norm(z)
    if r.get('renorm',True): v=v/np.linalg.norm(v)*src_norm*r.get('scale',1.0)
    return v.astype(np.float32)
for fn,tabs in (('front.onnx',F),('enc.onnx',E)):
    b=bytearray(open(f'{SRC}/{fn}','rb').read())
    for name,(tab,off) in tabs.items():
        for slot,r in zip(SLOTS,recipes):
            v=mix(tab,r); D=tab.shape[1]; o=off+slot*D*4; b[o:o+D*4]=v.tobytes()
    open(f'{DST}/{fn}','wb').write(bytes(b))
coef=meta['mean_std_coef']
for slot,r in zip(SLOTS,recipes):
    W=r['w']; coef[slot]=float(sum(w*coef[S[k]] for k,w in W.items())/sum(W.values())); S[r['name']]=slot
if os.path.islink(f'{DST}/tts.json'): os.remove(f'{DST}/tts.json')
json.dump(meta,open(f'{DST}/tts.json','w'),ensure_ascii=False)
print('голоса:',', '.join(f"{r['name']}→{s}" for s,r in zip(SLOTS,recipes)))
