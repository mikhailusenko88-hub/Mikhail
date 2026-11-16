# Тесты бота — 2026-11-16 21:00 UTC

Коммит бота: 8e1288a (Мини-приложение MAX: кнопки бота открывают са)

TELEGRAM_COLLECT_CONTACTS по умолчанию: 1

```
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/opt/hostedtoolcache/Python/3.12.16/x64/lib/python3.12/asyncio/base_events.py:691: in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

    async def scenario():
        f, h = await make(tmp_path, site_url="https://nashdekor.ru")
        await h.engine.start()
        await h.send(MANAGER, f"/owner {CODE}")
        await h.start(CLIENT)
        n_mgr = len(f.sent(MANAGER))
    
        await h.send(CLIENT, "А907")  # русская «А»
        card = f.last_body(CLIENT)
        assert "<b>A907</b> — Реечная панель A907" in card["text"] and "ширину стены" in card["text"]
>       assert {"type": "link", "text": "Фото и 3D на сайте", "url": "https://nashdekor.ru/p/a907/"} in kb_rows(card)[0]
E       AssertionError: assert {'type': 'link', 'text': 'Фото и 3D на сайте', 'url': 'https://nashdekor.ru/p/a907/'} in [{'type': 'open_app', 'text': 'Фото и 3D на сайте', 'web_app': 'id000000000000_bot', 'payload': 'p-a907'}]

tests/test_max.py:178: AssertionError
------------------------------ Captured log call -------------------------------
WARNING  prostranstvo.catalog:catalog.py:195 каталог: пропущено позиций с ошибками или повторами: 2
=========================== short test summary info ============================
FAILED tests/test_max.py::test_article_in_free_text_in_max - AssertionError: assert {'type': 'link', 'text': 'Фото и 3D на сайте', 'url': 'https://nashdekor.ru/p/a907/'} in [{'type': 'open_app', 'text': 'Фото и 3D на сайте', 'web_app': 'id000000000000_bot', 'payload': 'p-a907'}]
1 failed, 107 passed in 4.73s
код выхода pytest: 1
```
