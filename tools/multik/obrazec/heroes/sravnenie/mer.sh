#!/bin/bash
# mer.sh <герой> <ключ обложки> <cam=...> [мех, м]  — превью с метками и таблица мерок
cd /home/claude/g62/tools/multik/obrazec/heroes
OUT=/home/claude/out/geroi LBL=1 python3 prev_cvet.py $1 mer_$1 "$3" > /dev/null 2>&1 || { echo "ошибка превью"; exit 1; }
python3 sravnenie/mery.py sravnenie/obl.json $2 /home/claude/out/geroi/mer_$1_0_lbl.png /home/claude/out/geroi/mer_$1.json "$3" ${4:-0.012}
