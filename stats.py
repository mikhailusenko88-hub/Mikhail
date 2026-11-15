import sys, numpy as np
L=open(sys.argv[1]).read().split('\n')
S=np.array([float(l.split()[1]) for l in L if l.startswith('S')])
N=len(S)+1
out=[]
for q in (2,4,8,16,64,256,0.5,0.8,0.9,0.95,0.98,0.99,1.0):
    k = int(q*N) if q<=1 else q
    if 2<=k and k-2 < len(S): out.append(f"{q}:{S[k-2]:.1f}")
print(N, ' '.join(out))
