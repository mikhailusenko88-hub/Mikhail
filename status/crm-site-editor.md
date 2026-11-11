# Редактор сайта — 2026-11-11 20:34 UTC

```
ответ /site/edit: HTTP 200
страница: 4 · товаров в списке: 107
первый товар: A902
фото: 10814353 байт
новый товар с фото (через nginx): 302
фото 20 МБ (больше 15 — CRM откажет, должно 400): 400 · больше 15 МБ
в другой адрес 2 МБ (должно 413): 413
3 доп. фото сразу (через nginx): 302
скрыть товар: 302
/site/edit/sections=200 /site/edit/section=200 /site/edit/home=200 /site/edit/articles=200 /site/edit/article=200 /site/edit/reviews=200 /site/edit/review=200 /site/edit/recent=200 
API для Actions: [(1, 'product', 'TEST1', ['1.png']), (2, 'gallery_add', 'A902', ['2-1.png', '2-2.png', '2-3.png']), (3, 'hide', 'A902', [])]
фото по API без входа: 200, совпадает: да
на диске: -rw------- prostranstvo:prostranstvo 10814353 1.png
на диске: -rw------- prostranstvo:prostranstvo 10814353 2-1.png
на диске: -rw------- prostranstvo:prostranstvo 10814353 2-2.png
на диске: -rw------- prostranstvo:prostranstvo 10814353 2-3.png
после итога с сайта: на сайте
фото после публикации: 404 (должно 404)
```
