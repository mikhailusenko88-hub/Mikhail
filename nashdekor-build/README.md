# nashdekor-build — сборка страниц сайта «Наш декор»

- `build.py` — из `0f7s1eez/index.html` (CAT, PROF, PHOTO, PAINT, SHOP) собирает страницы товаров `0f7s1eez/p/<артикул>/`,
  разделы `0f7s1eez/catalog/<раздел>/`, `0f7s1eez/assets/p.css|p.js` и `sitemap.xml`. Запуск из корня репозитория:
  `python3 nashdekor-build/build.py`. Цены, размеры, фото и контакты правятся только в index.html, потом пересборка.
- `p.css`, `p.js` — стили и скрипт страниц товаров (3D панели, цвет, фото, количество, заявка в CRM).
- `clean_bg.py <src> <dst>` — единый фон #16233F на фото каталога, без бликов (numpy, scipy).
