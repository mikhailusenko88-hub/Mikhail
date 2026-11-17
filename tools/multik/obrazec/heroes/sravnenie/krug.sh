#!/bin/bash
# «круг» вокруг головы героя: спереди, 3/4 слева и справа, сбоку, сверху, снизу-спереди
# krug.sh hero_fila тег
cd /home/claude/g62/tools/multik/obrazec/heroes
H=$1; T=$2
read CX CY CZ <<< $(python3 -c "import sys; sys.path.insert(0,'.'); import importlib; h=importlib.import_module('$H').HERO; c=getattr(h,'FORM',{}).get('C', h.H); print(float(c[0]), float(c[1]), float(c[2]))")
D=1.1
python3 - $H $T $CX $CY $CZ $D <<'P'
import sys, math, subprocess, os
H, T, cx, cy, cz, D = sys.argv[1], sys.argv[2], *map(float, sys.argv[3:7])
views = []
for name, yaw, pitch in [('front', 0, 3), ('l34', 35, 5), ('r34', -35, 5), ('side', 90, 0), ('top', 0, 70)]:
    a, b = math.radians(yaw), math.radians(pitch)
    e = (cx - D * math.sin(a) * math.cos(b), cy - D * math.cos(a) * math.cos(b), cz + D * math.sin(b))
    views.append('cam=%.4f,%.4f,%.4f:%.4f,%.4f,%.4f:24' % (e[0], e[1], e[2], cx, cy, cz))
subprocess.run(['python3', 'prev_cvet.py', H, T] + views, env=dict(os.environ, OUT='/home/claude/out/geroi'), check=True)
P
