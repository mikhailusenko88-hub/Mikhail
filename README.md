# DuckDNS для своего сервера

Сервер сам сообщает DuckDNS свой адрес каждые 5 минут (systemd-таймер). После смены IP в панели хостера
постоянное имя через несколько минут начинает указывать на новый адрес — ключи на устройствах, выданные по имени, менять не нужно.

Поставить (на сервере, root):
    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/dns/duckdns-setup.sh | bash -s -- ИМЯ ТОКЕН

Проверить: `duckdns-update`, журнал: `tail /var/log/duckdns.log`.
Убрать: `curl -fsSL .../duckdns-setup.sh | bash -s -- remove`.

Имя и токен в репозиторий не кладутся — только в команду на сервере (/etc/duckdns.conf, права 600).

# Отдельный выход VPN (vpn-exit.sh)

Устройства подключаются к основному адресу сервера, а VPN выходит в интернет со второго адреса (второй сетевой интерфейс у хостера).
Приложения и сайты видят только второй адрес. Сам сервер (SSH, DuckDNS) ходит через основной. На второй адрес снаружи ничего не открыто.

Поставить (root):
    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/dns/vpn-exit.sh | bash -s -- ВТОРОЙ_IP
После установки скрипт сам проверяет выход и при неудаче всё откатывает. Дальше: `vpn-exit status`, `vpn-exit remove`.
