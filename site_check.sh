#!/usr/bin/env bash
# Проверка сайта nashdekor.ru снаружи: индексация, SEO-теги, файлы, форма заявки (без создания заявки).
set -u
O=status/site.md; mkdir -p status
U=https://nashdekor.ru
{
echo "# Сайт снаружи — $(date -u '+%F %H:%M') UTC"
echo
echo '```'
for p in / /robots.txt /sitemap.xml /favicon.ico /apple-touch-icon.png /og.jpg /oferta.html /privacy.html /consent.html /avito.xml /pochta/yulia.mobileconfig /pochta/mikhail.mobileconfig; do
  printf '%-34s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$U$p")"
done
curl -s "$U/" -o /tmp/i.html
echo
echo "noindex в главной: $(grep -c -i noindex /tmp/i.html)"
echo "lang=ru: $(grep -c '<html lang="ru">' /tmp/i.html)"
echo "title: $(grep -o '<title>[^<]*</title>' /tmp/i.html | head -1)"
echo "description: $(grep -c 'name="description"' /tmp/i.html), canonical: $(grep -o 'rel="canonical" href="[^"]*"' /tmp/i.html | head -1)"
echo "og:image: $(grep -o 'og:image" content="[^"]*"' /tmp/i.html | head -1)"
echo "ld+json: $(grep -c 'application/ld+json' /tmp/i.html)"
echo "адрес формы в сайте: $(grep -o 'https://crm\.[a-z.]*/api/lead' /tmp/i.html | head -1)"
echo "форма — ответ «Спасибо… Заявка отправлена» и кнопка «ещё одна»: $(grep -c 'id="lAgain"' /tmp/i.html), версия сайта: $(grep -c 'openLeadForm' /tmp/i.html)"
echo
echo "--- robots.txt"; curl -s "$U/robots.txt"
echo "--- заголовки X-Robots-Tag главной: $(curl -sI "$U/" | grep -i x-robots || echo нет)"
echo
echo "--- форма: CORS preflight"
curl -s -o /dev/null -D - -X OPTIONS https://crm.nashdekor.ru/api/lead -H 'Origin: https://nashdekor.ru' -H 'Access-Control-Request-Method: POST' | grep -i -E '^HTTP|access-control-allow-origin'
echo "--- форма: проверочная отправка-ловушка (заявку НЕ создаёт)"
curl -s -w '  HTTP %{http_code}\n' -X POST https://crm.nashdekor.ru/api/lead -H 'Origin: https://nashdekor.ru' -H 'Content-Type: application/json' \
  -d '{"website":"проверка","name":"проверка","contact":"проверка","consent":true}'
echo "--- CRM health: $(curl -s https://crm.nashdekor.ru/api/health)"
echo "--- robots на crm/mail: crm $(curl -s -o /dev/null -w '%{http_code}' https://crm.nashdekor.ru/robots.txt), mail $(curl -s -o /dev/null -w '%{http_code}' https://mail.nashdekor.ru/robots.txt)"
echo '```'
} > "$O" 2>&1
cat "$O"
