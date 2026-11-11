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

## Ответы на письма — Claude читает сам

`READER.pub` — открытый ключ Claude для чтения ответов (меняется с каждым его сеансом: `python3 tools/replies.py key --new`).
Сервер отдаёт по адресу https://crm.nashdekor.ru/api/outbox/replies только письма в info@, которые пришли в ответ
на письма с zapros@ (ссылаются на них, с тех же адресов или доменов, кроме бесплатных почт, с той же темой) —
и только шифром для этого ключа. Письма клиентов и zakaz@ — никогда. Выключается в CRM → Ещё → Исходящие.
Из облака шифр снимает workflow `replies-fetch` (ветка domain-check, файл pages/replies.txt) → ветка `replies`.

    python3 tools/replies.py read replies.json --out ответы/

## Документы в CRM

`python3 tools/doc.py --folder "Сертификаты и ТУ" --title "Название" [--until ГГГГ-ММ-ДД] [--note "…"] файл` →
`docs/<id>.json` (шифр). Сервер кладёт файл в CRM → Ещё → Документы (один раз), статус по id — saved.
