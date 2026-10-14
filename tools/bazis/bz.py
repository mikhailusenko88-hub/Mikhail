import struct, zlib, sys, math, json
class R:
    def __init__(s,b,p=0): s.b=b; s.p=p
    def u8(s): v=s.b[s.p]; s.p+=1; return v
    def u32(s): v=struct.unpack_from('<I',s.b,s.p)[0]; s.p+=4; return v
    def i32(s): v=struct.unpack_from('<i',s.b,s.p)[0]; s.p+=4; return v
    def f64(s): v=struct.unpack_from('<d',s.b,s.p)[0]; s.p+=8; return v
    def raw(s,n): v=s.b[s.p:s.p+n]; s.p+=n; return v
def read_keys(r):
    n=r.u32(); return [r.raw(r.u32()).decode('cp1251') for _ in range(n)]
def read_entry(r, keys):
    k=r.u32(); c=r.u32(); t=r.u8()
    if t==0: v=[read_entry(r,keys) for _ in range(c)]
    elif t in (1,2,8): v=None
    elif t==3: v=r.u8()
    elif t==4: v=r.i32()
    elif t==5: v=r.f64()
    elif t==9: v=r.f64()
    elif t==6: n=r.u32(); v=r.raw(2*n).decode('utf-16le','replace')
    elif t==7: n=r.u32(); v=r.raw(n)
    else: raise ValueError(f'unknown type {t} at {r.p-1}')
    return [k,c,t,v]
def parse_block(b):
    r=R(b); keys=read_keys(r); es=[]
    while r.p<len(b): es.append(read_entry(r,keys))
    return keys,es
def load_file(path):
    d=open(path,'rb').read()
    assert d[:4]==b'BZ85' and d[4:9]==b'\x01\x00\x00\xff\x00'
    r=R(d,9); hk=read_keys(r); he=[]
    i=d.index(b'\x01\x00\x00\xff\x01', r.p)
    while r.p<i: he.append(read_entry(r,hk))
    fk,fe=parse_block(zlib.decompress(d[i+5:]))
    return hk,he,fk,fe
