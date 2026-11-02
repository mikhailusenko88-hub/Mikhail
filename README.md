# domain-check — проверка свободных доменов

Служебная ветка. Когда меняется `request.txt`, GitHub Actions проверяет каждый домен через whois
(.ru и .рф — через реестр whois.tcinet.ru) и кладёт таблицу в `status/result.md`. Ничего не регистрирует.
