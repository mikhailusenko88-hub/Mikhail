#!/bin/bash
# Читает dns.txt: строки «домен [ip-сервера]». Пишет status/dns.md.
out=status/dns.md
echo "# Проверка DNS — $(date -u '+%Y-%m-%d %H:%M UTC')" > "$out"
grep -v '^\s*#' dns.txt | while read -r d ip; do
  [ -z "$d" ] && continue
  {
    echo; echo "## $d"; echo '```'
    echo "--- whois (реестр)"
    whois -h whois.tcinet.ru "$d" 2>&1 | grep -Ei '^(domain|nserver|state|registrar|created|paid-till|Last updated)' | head -12
    echo "--- зона .ru (a.dns.ripn.net), NS"
    dig +norec +noall +comments +authority NS "$d" @a.dns.ripn.net 2>&1 | grep -E 'status:|IN\s+NS' | head -5
    for ns in ns1.firstvds.ru ns2.firstvds.ru; do
      echo "--- $ns: A $d / A www.$d"
      echo "  $(dig +short +time=5 +tries=2 A "$d" @"$ns" 2>&1 | tr '\n' ' ') / $(dig +short +time=5 +tries=2 A "www.$d" @"$ns" 2>&1 | tr '\n' ' ')"
    done
    for r in 8.8.8.8 1.1.1.1 77.88.8.8; do
      echo "--- публичный DNS $r: A $d -> $(dig +short +time=5 +tries=2 A "$d" @"$r" 2>&1 | tr '\n' ' ')"
    done
    for u in "http://$d/" "https://$d/" "http://www.$d/"; do
      code=$(curl -s -o /dev/null -m 15 -w '%{http_code} %{remote_ip}' "$u" 2>&1)
      echo "--- $u -> ${code:-нет ответа}"
    done
    if [ -n "$ip" ]; then
      echo "--- напрямую по IP с именем $d (http://$ip/)"
      echo "  $(curl -s -m 15 -H "Host: $d" "http://$ip/" 2>&1 | grep -o '<title>[^<]*' | head -1)"
    fi
    echo '```'
  } >> "$out"
done
cat "$out"
