# Страница CRM «Сервер» — 2026-11-15 21:34 UTC

```
cron: 1 строк
файл отчёта: root 644 2019 байт
/server: 200
строк «Обновлено» на странице: 2
кнопка Обновить: 302
просьба на диске: /var/lib/prostranstvo/server-request
после cron просьба: ls: cannot access '/var/lib/prostranstvo/server-request': No

--- отчёт (начало) ---
Обновлено: 16.11.2026 00:34

=== Сервер «Наш декор», 16.11.2026 00:34 ===
Сайт:   http://nashdekor.ru/  (HTTPS пока нет — команда: prostranstvo-cert)
IP:     40.124.29.228
nginx:  active
Обновление из GitHub: работает (последняя проверка 0 мин назад)
Версия сайта: 46deb4d от 15.11.2026 19:36 — s9kbars: обложки серий 31–33
Firewall ufw:  active
fail2ban SSH:  active, сейчас заблокировано адресов: 0
Автообновления: enabled
Нужна перезагрузка: сделается сама в 04:30 (или сейчас: reboot)
Диск:   85G свободно из 145G

=== Почта ===
почта не установлена

=== CRM ===
CRM nashdekor.ru — проверка (16.11.2026 00:34)
   [да]  служба prostranstvo-crm работает
   [да]  приложение отвечает
   [да]  https://crm.nashdekor.ru/login через nginx
   [НЕТ] сертификат — пока временный (сервер получит сам, когда домен заработает)
   заявки с сайта: включены
   клиентов: 3, заявок: 3, пользователей: 2
   последняя копия: /var/backups/prostranstvo/2026-11-16

=== Нагрузка ===
 00:34:37 up 18 min,  0 user,  load average: 0.65, 0.56, 0.28
               total        used        free      shared  buff/cache   available
Mem:            15Gi       1.1Gi        11Gi        50Mi       3.2Gi        14Gi
Swap:          3.0Gi          0B       3.0Gi
Filesystem      Size  Used Avail Use% Mounted on
/dev/root       145G   61G   85G  42% /

=== Блокировки входа в CRM (fail2ban) ===
   |- Currently banned:	0
   `- Banned IP list:	
Свои адреса (не блокируются): 127.0.0.1/8 ::1 198.51.100.7

=== Вход на сервер по SSH ===
   |- Currently banned:	0
   `- Banned IP list:	
```
