#!/bin/bash
# Убрать закрытый текст из ВСЕЙ истории одной ветки (файлы и сообщения коммитов) — каждый чат за собой (CLAUDE.md).
#   bash scrub_history.sh <ветка> "старый текст" "новый текст" ["старый 2" "новый 2" …] [--dry]
# Делает: свежий полный клон ветки во временную папку → замена во всех версиях файлов и в сообщениях →
# проверка, что старого текста нигде нет → push --force-with-lease (только если ветку никто не сдвинул за это время).
# --dry — всё, кроме push. Содержимое файлов на верхушке ветки меняется только там, где был старый текст.
# Взять скрипт: git fetch --depth=1 origin main && git show origin/main:.claude/scrub_history.sh > /tmp/scrub_history.sh
set -euo pipefail
B="${1:?ветка}"; shift
DRY=0; ARGS=()
for x in "$@"; do [ "$x" = "--dry" ] && DRY=1 || ARGS+=("$x"); done
[ $(( ${#ARGS[@]} % 2 )) -eq 0 ] && [ ${#ARGS[@]} -gt 0 ] || { echo "нужны пары: «старый» «новый»"; exit 2; }
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
git clone -q --single-branch -b "$B" https://github.com/mikhailusenko88-hub/mikhail "$W/r"
cd "$W/r"; OLD=$(git rev-parse HEAD)
python3 - "$W/pairs.json" "${ARGS[@]}" <<'PY'
import json, sys
a = sys.argv[2:]; json.dump([[a[i], a[i + 1]] for i in range(0, len(a), 2)], open(sys.argv[1], "w"), ensure_ascii=False)
PY
cat > "$W/rep.py" <<PY
import json, sys
P = json.load(open("$W/pairs.json"))
d = sys.stdin.buffer.read()
try:
    s = d.decode("utf-8")
except UnicodeDecodeError:
    sys.stdout.buffer.write(d); sys.exit()
for a, b in P:
    s = s.replace(a, b)
sys.stdout.buffer.write(s.encode("utf-8"))
PY
# какие пути когда-либо содержали старый текст
: > "$W/paths"
python3 - "$W/pairs.json" > "$W/olds" <<'PY'
import json, sys
for a, b in json.load(open(sys.argv[1])): print(a)
PY
while IFS= read -r o; do
  git rev-list HEAD | xargs -n 50 git grep -l -F -e "$o" 2>/dev/null | cut -d: -f2- >> "$W/paths" || true
done < "$W/olds"
sort -u -o "$W/paths" "$W/paths"
git log --format=%B > "$W/msgs"
MSG=0; while IFS= read -r o; do if grep -qF -- "$o" "$W/msgs"; then MSG=1; fi; done < "$W/olds"
echo "файлов со старым текстом: $(wc -l < "$W/paths"); в сообщениях коммитов: $MSG"
[ -s "$W/paths" ] || [ $MSG -eq 1 ] || { echo "старого текста в ветке нет — делать нечего"; exit 0; }
mkdir -p "$W/cache"
cat > "$W/idx.sh" <<SH
while IFS= read -r f; do
  e=\$(git ls-files -s -- "\$f"); [ -z "\$e" ] && continue
  m=\$(echo "\$e" | awk '{print \$1}'); h=\$(echo "\$e" | awk '{print \$2}')
  c="$W/cache/\$h"
  if [ -f "\$c" ]; then n=\$(cat "\$c"); else n=\$(git cat-file blob \$h | python3 "$W/rep.py" | git hash-object -w --stdin); echo \$n > "\$c"; fi
  [ "\$n" != "\$h" ] && git update-index --cacheinfo "\$m,\$n,\$f"
done < "$W/paths"
true
SH
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter "bash $W/idx.sh" --msg-filter "python3 $W/rep.py" HEAD >/dev/null
LEFT=0
while IFS= read -r o; do
  git rev-list HEAD | xargs -n 50 git grep -l -F -e "$o" > "$W/left" 2>/dev/null || true
  git log --format=%B > "$W/msgs2"
  if [ -s "$W/left" ] || grep -qF -- "$o" "$W/msgs2"; then echo "!! остался: $o"; LEFT=1; fi
done < "$W/olds"
[ $LEFT -eq 0 ] || { echo "не всё заменилось — не пушу"; exit 1; }
echo "верхушка ветки: изменённые файлы —"; git diff --stat "$OLD" HEAD | tail -5
if [ $DRY -eq 1 ]; then echo "--dry: не пушу"; exit 0; fi
git push --force-with-lease="$B:$OLD" origin HEAD:"$B"
echo "готово: история $B переписана ($(git rev-parse --short HEAD)). Другим клонам этой ветки — клонировать заново."
