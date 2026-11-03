#!/bin/bash
# Качает файлы и пишет отчёт в status/result.md
set -u
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
R=status/result.md
echo "# ep-mac $(date -u)" > $R
dl() { # url file
  code=$(curl -sSL -A "$UA" --max-time 300 -o "files/$2" -w "%{http_code} %{size_download} %{url_effective}" "$1" 2>&1)
  echo "- $2 ← $1 : $code" >> $R
  [ -s "files/$2" ] && file "files/$2" | sed 's/^/  - /' >> $R
}
links() { # url name
  curl -sSL -A "$UA" --max-time 60 "$1" -o "status/$2.html" -w "" 2>>$R
  echo "## links $2 ($1), size $(wc -c < status/$2.html 2>/dev/null)" >> $R
  grep -oiE '(href|src|data-[a-z-]+)="[^"]+"' "status/$2.html" | grep -iE 'mac|dmg|pkg|tgz|darwin|osx|csp|plugin|download|update\.s|crypto' | sort -u | head -80 >> $R
}
while read -r kind a b; do
  [ -z "${kind:-}" ] && continue
  case "$kind" in
    dl) dl "$a" "$b";;
    links) links "$a" "$b";;
  esac
done < request.txt
ls -la files >> $R
for f in status/*.html; do echo "## urls in $f" >> $R; grep -oiE 'https?://update\.(saby|sbis)\.ru[^"'"'"' <>\\]+' "$f" | grep -iE 'crypt|csp|darwin|mac' | sort -u | head -40 >> $R; done
