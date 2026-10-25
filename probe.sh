#!/bin/bash
# Только чтение: проверяет, с каких сайтов банков можно взять курсы. Ничего не ставит и не меняет.
D=$(date +%d.%m.%Y)
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
OUT=/tmp/rates-probe; rm -rf $OUT; mkdir -p $OUT
probe() {  # имя url
  f="$OUT/$1.html"
  code=$(curl -sL --max-time 25 -A "$UA" -o "$f" -w '%{http_code}' "$2")
  size=$(wc -c < "$f")
  hits=$(grep -oiE '(USD|доллар)[^0-9]{0,80}[0-9]{3}[.,][0-9]{1,2}' "$f" | head -2 | tr '\n' ' ' | cut -c1-140)
  ul=$(grep -oiE 'юридическ|для бизнеса|безналичн|наличн' "$f" | sort | uniq -c | tr '\n' ' ')
  printf '%-12s %s %7s байт | %s | %s\n' "$1" "$code" "$size" "${hits:-нет цифр в HTML}" "$ul"
}
probe nbk        "https://nationalbank.kz/rss/get_rates.cfm?fdate=$D"
probe kase       "https://kase.kz/ru/currency/"
probe halyk      "https://halykbank.kz/exchange-rates"
probe halyk_api  "https://back.halykbank.kz/common/currency-history"
probe kaspi      "https://kaspi.kz/"
probe freedom    "https://bankffin.kz/ru/exchange-rates"
probe freedomapi "https://bankffin.kz/api/exchange-rates/getRates"
probe bcc        "https://www.bcc.kz/"
probe forte      "https://forte.kz/"
probe jusan      "https://jusan.kz/exchange-rates"
probe bereke     "https://berekebank.kz/"
probe homecredit "https://homecredit.kz/"
echo "Страницы сохранены в $OUT (временная папка, удалится сама при перезагрузке)"
