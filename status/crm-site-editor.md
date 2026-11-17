# Редактор сайта — 2026-11-17 16:48 UTC

```
ответ /site/edit: HTTP 200
страница: 4 · товаров в списке: 107
первый товар: A902
фото: 10814351 байт
новый товар с фото (через nginx): 400
фото 20 МБ (больше 15 — CRM откажет, должно 400): 400 · больше 15 МБ
в другой адрес 2 МБ (должно 413): 413
3 доп. фото сразу (через nginx): 302
скрыть товар: 302
/site/edit/sections=200 /site/edit/section=200 /site/edit/home=200 /site/edit/articles=200 /site/edit/article=200 /site/edit/reviews=200 /site/edit/review=200 /site/edit/recent=200 
API для Actions: [(1, 'gallery_add', 'A902', ['1-1.png', '1-2.png', '1-3.png']), (2, 'hide', 'A902', [])]
фото по API без входа: 200, совпадает: да
на диске: -rw------- prostranstvo:prostranstvo 10814351 1-1.png
на диске: -rw------- prostranstvo:prostranstvo 10814351 1-2.png
на диске: -rw------- prostranstvo:prostranstvo 10814351 1-3.png
после итога с сайта: на сайте
фото после публикации: 404 (должно 404)
```
