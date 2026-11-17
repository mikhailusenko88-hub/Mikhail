#!/bin/bash
# tri.sh <hero> <ключи…> — подбор ракурса и мерки по нескольким обложкам, сводка «между глазами / глаз / нос / рот»
cd /home/claude/g62/tools/multik/obrazec/heroes; H=$1; shift
for k in "$@"; do python3 sravnenie/poza.py $H $k > /tmp/pz_$k.log 2>&1 & done; wait
for k in "$@"; do echo "== $k"; sed -n 1p /tmp/pz_$k.log | cut -c1-40; grep "←" /tmp/pz_$k.log; done
