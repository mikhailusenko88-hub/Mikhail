# Минимальный разбор ONNX (protobuf) без пакета onnx: где лежат таблицы дикторов.
import struct,sys
def varint(b,i):
    r=s=0
    while True:
        c=b[i]; i+=1; r|=(c&0x7f)<<s; s+=7
        if c<0x80: return r,i
def fields(b,i,end):
    while i<end:
        k,i=varint(b,i); f,t=k>>3,k&7
        if t==0: v,i=varint(b,i); yield f,t,v,None,None
        elif t==1: yield f,t,b[i:i+8],i,i+8; i+=8
        elif t==5: yield f,t,b[i:i+4],i,i+4; i+=4
        elif t==2:
            n,i=varint(b,i); yield f,t,None,i,i+n; i+=n
        else: raise ValueError(t)
def tensors(path):
    b=open(path,'rb').read(); out=[]
    for f,t,v,s,e in fields(b,0,len(b)):
        if f==7 and t==2:   # graph
            for gf,gt,gv,gs,ge in fields(b,s,e):
                if gf==5 and gt==2:   # initializer
                    T={'dims':[],'name':'','dtype':None,'raw':None}
                    for tf,tt,tv,ts,te in fields(b,gs,ge):
                        if tf==1:
                            if tt==0: T['dims'].append(tv)
                            else:
                                j=ts
                                while j<te: d,j=varint(b,j); T['dims'].append(d)
                        elif tf==2: T['dtype']=tv
                        elif tf==8: T['name']=b[ts:te].decode()
                        elif tf==9: T['raw']=(ts,te)
                        elif tf==4: T['float_data']=(ts,te)
                    out.append(T)
    return b,out
if __name__=='__main__':
    for p in sys.argv[1:]:
        b,ts=tensors(p)
        print(p,len(ts),'тензоров')
        for T in ts:
            if T['dims'] and T['dims'][0]==60: print('   ',T['name'],T['dims'],'тип',T['dtype'],'raw' if T['raw'] else 'float_data' if T.get('float_data') else '?')
