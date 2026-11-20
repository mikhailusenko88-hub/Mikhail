# Мост в Казахстан (kz-bridge)

Российский сервер принимает подключения и пересылает их на сервер в Казахстане (Hoster.kz).
VPN на российском сервере не ставится — только переброска портов. Устройства подключаются к российскому адресу,
казахстанский адрес видит только сам мост.

Проверка (ничего не меняет):
    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/most/kz-bridge.sh | bash -s -- НОВЫЙ_IP --dry
Поставить / сменить адрес Казахстана:
    curl -fsSL https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail/most/kz-bridge.sh | bash -s -- НОВЫЙ_IP
На мосту: `kz-bridge status`, `kz-bridge remove`.

Порты (здесь → Казахстан): SSH 2222→22, XRay XHTTP 8443→8443, XRay Reality 8444→443, Amnezia XRay 445→445 (tcp/udp),
AmneziaWG 39894→39894 (udp), страницы 8080→8080. Занятый порт скрипт заменяет следующим свободным и пишет об этом.
