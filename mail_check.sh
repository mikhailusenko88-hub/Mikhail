#!/usr/bin/env bash
# Проверка почты и CRM снаружи: записи DNS (SPF, DKIM, DMARC, MX, PTR), сертификаты
# и порты почты, веб-почта и CRM по https, статус домена в whois. Результат — status/mail.md
set -u
D=nashdekor.ru; IP=185.60.134.150; OUT=status/mail.md
mkdir -p status
ok(){ echo "- [да] $*"; }; no(){ echo "- [НЕТ] $*"; }
{
echo "# Проверка почты и CRM — $(date -u '+%F %H:%M') UTC"; echo
echo "## DNS (публичный 8.8.8.8 и сервер хостинга ns1.firstvds.ru)"
for S in 8.8.8.8 ns1.firstvds.ru; do
  echo "### $S"
  spf=$(dig +short TXT $D @$S | tr -d '"' | grep -i 'v=spf1' || true)
  [[ -n $spf ]] && ok "SPF: $spf" || no "SPF нет"
  dm=$(dig +short TXT _dmarc.$D @$S | tr -d '"' || true)
  [[ $dm == *DMARC1* ]] && ok "DMARC: $dm" || no "DMARC нет"
  dk=$(dig +short TXT mail._domainkey.$D @$S | sed 's/" "//g' | tr -d '"' || true)
  if [[ $dk == *DKIM1* ]]; then ok "DKIM есть, длина ${#dk}, sha256 $(printf %s "$dk" | sha256sum | cut -c1-16)"; else no "DKIM нет"; fi
  mx=$(dig +short MX $D @$S | tr '\n' ' '); [[ -n $mx ]] && ok "MX: $mx" || no "MX нет"
  a=$(dig +short A mail.$D @$S | tr '\n' ' '); [[ $a == *$IP* ]] && ok "mail.$D → $a" || no "mail.$D → '$a'"
done
echo; echo "## PTR (обратная запись)"
ptr=$(dig +short -x $IP @8.8.8.8 | tr '\n' ' ')
[[ $ptr == *mail.$D* ]] && ok "PTR $IP → $ptr" || no "PTR $IP → '$ptr' (нужно mail.$D.; может обновиться не сразу)"
echo; echo "## Порты почты (сертификат)"
for p in 993 465; do
  sub=$(echo | timeout 15 openssl s_client -connect $IP:$p -servername mail.$D 2>/dev/null | openssl x509 -noout -subject -enddate 2>/dev/null | tr '\n' ' ')
  [[ -n $sub ]] && ok "порт $p: $sub" || no "порт $p не отвечает"
done
sub=$(echo | timeout 15 openssl s_client -starttls smtp -connect $IP:587 -servername mail.$D 2>/dev/null | openssl x509 -noout -subject -enddate 2>/dev/null | tr '\n' ' ')
[[ -n $sub ]] && ok "порт 587 (STARTTLS): $sub" || no "порт 587 не отвечает"
echo "- порт 25 из GitHub не проверить (у раннеров закрыт исходящий 25)"
echo; echo "## Сайты"
for u in https://$D/ https://mail.$D/ https://crm.$D/login https://mail.$D/pochta-dns.txt; do
  c=$(curl -sS -o /dev/null -m 20 -w '%{http_code}' "$u" 2>/dev/null || echo ERR)
  [[ $c =~ ^(200|301|302)$ ]] && ok "$u → $c" || no "$u → $c"
done
echo; echo "## Домен в реестре"
st=$(whois -h whois.tcinet.ru $D 2>/dev/null | grep -iE '^state:' | head -1)
echo "- ${st:-whois не ответил}"
} > "$OUT" 2>&1
cat "$OUT"
