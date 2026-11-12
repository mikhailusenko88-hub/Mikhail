import json,numpy as np,sys
sys.path.insert(0,'/home/claude/newvoice'); from pb import tensors
S=json.load(open('/home/claude/mv/voice/tts.json'))['speakers']; ID={v:k for k,v in S.items()}
def tables(path):
    b,ts=tensors(path); out={}
    for T in ts:
        if T['dims'] and T['dims'][0]==60:
            s,e=T['raw']; out[T['name']]=(np.frombuffer(b[s:e],np.float32).reshape(T['dims']).copy(),s)
    return out
F=tables('/home/claude/mv/voice/front.onnx'); E=tables('/home/claude/mv/voice/enc.onnx')
