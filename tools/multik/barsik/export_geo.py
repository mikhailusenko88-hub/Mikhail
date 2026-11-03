# geo_<var>.npz -> out/geo_<var>/<имя>.bin (float32/int32/int8) + manifest.txt
import numpy as np, sys, os
var = sys.argv[1] if len(sys.argv) > 1 else 'base'
G = np.load('out/geo_%s.npz' % var); d = 'out/geo_%s' % var; os.makedirs(d, exist_ok=True)
man = []
for k in G.keys():
    a = G[k]
    if a.dtype.kind == 'U': continue
    if a.dtype in (np.float16, np.float64): a = a.astype(np.float32)
    if a.dtype == np.int64: a = a.astype(np.int32)
    code = {np.dtype('float32'): 'f', np.dtype('int32'): 'i', np.dtype('int8'): 'b'}[a.dtype]
    np.ascontiguousarray(a).tofile('%s/%s.bin' % (d, k))
    man.append('%s %s %d %s' % (k, code, a.ndim, ' '.join(map(str, a.shape))))
open('%s/manifest.txt' % d, 'w').write('\n'.join(man) + '\n'); print('\n'.join(man))
