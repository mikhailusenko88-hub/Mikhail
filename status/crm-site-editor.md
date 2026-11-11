# Редактор сайта — 2026-11-11 17:32 UTC

```
ответ /site/edit: HTTP 301
страница: 0 · товаров в списке: 0
первый товар: 
фото: 10814352 байт
новый товар с фото (через nginx): 302
фото 20 МБ (больше 15 — CRM откажет, должно 400): 400 · больше 15 МБ
в другой адрес 2 МБ (должно 413): 413
3 доп. фото сразу (через nginx): 404
скрыть товар: 404
/site/edit/sections=200 /site/edit/section=200 /site/edit/home=200 /site/edit/articles=200 /site/edit/article=200 /site/edit/reviews=200 /site/edit/review=200 /site/edit/recent=200 
API для Actions: [(1, 'product', 'TEST1', ['1.png'])]
фото по API без входа: 200, совпадает: да
на диске: -rw------- prostranstvo:prostranstvo 10814352 1.png
после итога с сайта: на сайте
фото после публикации: 404 (должно 404)
```
