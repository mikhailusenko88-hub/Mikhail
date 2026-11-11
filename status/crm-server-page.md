# Страница CRM «Сервер» — 2026-11-11 20:33 UTC

```
cron: 1 строк
файл отчёта: root 644 1983 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 11.11.2026 23:33

=== Сервер «Наш декор», 11.11.2026 23:33 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     68.154.55.104
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: 831fb9c от 11.11.2026 20:56 — Фиды Авито и Яндекс Товаров: цены и наличие из CRM (2026-11-11 17:56 UTC)
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Диск:   86G свободно из 145G

=== Почта ===
почта не установлена

=== CRM ===
CRM nashdekor.ru — проверка (11.11.2026 23:33)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 3, заявок: 3, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-11

=== Нагрузка ===
 23:33:41 up 57 min,  0 user,  load average: 0.58, 0.43, 0.24
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.2Gi        12Gi        52Mi       1.8Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       145G   59G   86G  41% /

=== Блокировки входа в CRM (fail2ban) ===
   |- Currently banned:	0
   `- Banned IP list:	
Свои адреса (не блокируются): 127.0.0.1/8 ::1 198.51.100.7

=== Вход на сервер по SSH ===
   |- Currently banned:	0
   `- Banned IP list:	
```
