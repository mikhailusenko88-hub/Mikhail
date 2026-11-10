# Ветка outbox — исходящие письма «Наш декор» с zapros@

Здесь лежат только **зашифрованные** письма (`outbox/<id>.json`). Прочитать их может лишь сервер магазина:
закрытый ключ хранится в базе CRM, открытый — `KEY.pub` (он же https://crm.nashdekor.ru/api/outbox/key).

Сервер раз в минуту забирает ветку и отправляет новые письма от «Наш декор <zapros@nashdekor.ru>»,
ответы приходят в info@. Каждое письмо уходит один раз. Статус — https://crm.nashdekor.ru/api/outbox/status/<id>,
список и настройки — CRM → Ещё → Исходящие.

Написать письмо:

    python3 tools/send.py --to lab@example.ru --subject "Тема" --body-file письмо.txt [--attach файл.docx]
    git add outbox && git commit -m "письмо" && git push origin outbox

Паролей и открытого текста писем в этой ветке нет и быть не должно.
