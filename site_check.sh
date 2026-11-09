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
echo "телефон на сайте (должно быть 0): $(grep -c '204-10-47\|2041047' /tmp/i.html), класс Г2 (должно быть 0): $(grep -c 'Г2' /tmp/i.html), кнопка «Заказать звонок»: $(grep -c 'id="callMe"' /tmp/i.html)"
echo "контакты: MAX в списке: $(grep -c '\["MAX", SHOP.max' /tmp/i.html), подсказка «позвонить или написать в MAX»: $(grep -c 'написать в MAX' /tmp/i.html), WhatsApp: $(grep -ci whatsapp /tmp/i.html); боты в политике: $(curl -s "$U/privacy.html" | grep -c 'далее — Боты'), в согласии: $(curl -s "$U/consent.html" | grep -c 'MAX, Telegram'), в оферте: $(curl -s "$U/oferta.html" | grep -c 'чат-боте магазина в MAX')"
echo "счётчик на главной: $(grep -c 'crm.nashdekor.ru/api/hit' /tmp/i.html), в политике п. 3.4: $(curl -s "$U/privacy.html" | grep -c 'счётчик посещений'), на документах: $(for f in oferta privacy consent; do curl -s "$U/$f.html" | grep -c api/hit; done | tr '\n' ' ')"
echo
echo "--- страницы товаров и разделов (сборка nashdekor-build/build.py)"
for p in /p/a907/ /p/2-7/ /p/a35/ /p/a002-2/ /p/gs1/ /catalog/reechnye-paneli/ /catalog/paneli-pod-derevo/ /catalog/plintusy/ /assets/p.js /assets/p.css /mebel/_lib/three.min.js /mebel/_lib/OrbitControls.js /img/A907.jpg; do
  printf '%-34s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}' "$U$p")"
done
curl -s "$U/p/a907/" -o /tmp/p.html
echo "товар A907: title: $(grep -o '<title>[^<]*</title>' /tmp/p.html | head -1)"
echo "  canonical: $(grep -o 'rel="canonical" href="[^"]*"' /tmp/p.html | head -1), ld+json: $(grep -c 'application/ld+json' /tmp/p.html), Product: $(grep -c '"@type": "Product"' /tmp/p.html), 3D canvas: $(grep -c 'id="c3"' /tmp/p.html), профиль svg: $(grep -c '<svg viewBox' /tmp/p.html), window.P: $(grep -c 'window.P=' /tmp/p.html)"
echo "  форма A907: «Купить»: $(grep -c 'id="toBuy"' /tmp/p.html), режимы Заявка/Купить/Звонок: $(grep -o 'data-m="[a-z]*"' /tmp/p.html | sort -u | tr '\n' ' '), адрес доставки: $(grep -c 'id="lAddr"' /tmp/p.html), телефон (0): $(grep -c '204-10-47' /tmp/p.html), Г2 (0): $(grep -c 'Г2' /tmp/p.html)"
curl -s "$U/p/a35/" -o /tmp/m.html
echo "молдинг A35: 3D canvas: $(grep -c 'id="c3"' /tmp/m.html), профиль svg: $(grep -c '<svg viewBox' /tmp/m.html), контур poly: $(grep -c '"poly":' /tmp/m.html); счётчик панелей на A907: $(grep -c 'id="nPlus"' /tmp/p.html)"
echo "«моя стена» на A907: блок: $(grep -c 'id="wallBox"' /tmp/p.html), вкладка: $(grep -c 'data-v="wall"' /tmp/p.html); p.js со стеной: $(curl -s "$U/assets/p.js" | grep -c 'function buildWall')"
echo "SEO: title главной: $(grep -o '<title>[^<]*</title>' /tmp/i.html | head -1); FAQ на плинтусах: $(curl -s "$U/catalog/plintusy/" | grep -c FAQPage), title раздела: $(curl -s "$U/catalog/plintusy/" | grep -o '<title>[^<]*</title>'); цена за м² в A907: $(grep -c '₽/м²' /tmp/p.html)"
echo "sitemap: адресов $(curl -s "$U/sitemap.xml" | grep -c '<loc>'), из них /p/: $(curl -s "$U/sitemap.xml" | grep -c '<loc>https://nashdekor.ru/p/'), /catalog/: $(curl -s "$U/sitemap.xml" | grep -c '/catalog/')"
echo "главная: ссылок на p/ в коде карточек: $(grep -c 'href="\${href}"' /tmp/i.html), ссылки на разделы: $(grep -o 'catalog/[a-z-]*/' /tmp/i.html | sort -u | wc -l), ?panel= в расчёт: $(grep -c 'QS.get("panel")' /tmp/i.html)"
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
