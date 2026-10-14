#!/bin/bash
# Использование: tools/bazis/run.sh файл.b3d папка_вывода "Заголовок"
# Делает: разбор → данные (панели, кромка, ящики/корзины, крепёж и присадка) → HTML-артефакт.
set -e
H="$(cd "$(dirname "$0")" && pwd)"; F="$1"; O="${2:-out}"; T="${3:-Гардеробная}"
mkdir -p "$O"; cd "$H"
python3 extract.py "$F" . "$O/raw.json"
python3 post.py "$O/raw.json" "$O/base.json" >/dev/null
python3 fastjson.py "$F" . "$O/base.json" "$O/full.json"
python3 list_hw.py "$F" > "$O/hardware.txt"
python3 drw.py "$O/full.json" > "$O/drawers.txt"
python3 build.py "$O/full.json" "$O/view.html"
sed -i "s#<title>[^<]*</title>#<title>$T</title>#" "$O/view.html"
echo "Готово: $O/view.html  (фурнитура: $O/hardware.txt, ящики: $O/drawers.txt)"
