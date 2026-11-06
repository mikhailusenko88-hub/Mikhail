# Проверка почты и CRM — 2026-11-06 07:45 UTC

## DNS (публичный 8.8.8.8 и сервер хостинга ns1.firstvds.ru)
### 8.8.8.8
- [да] SPF: v=spf1 ip4:185.60.134.150 mx ~all
- [да] DMARC: v=DMARC1; p=none; adkim=r; aspf=r
- [да] DKIM есть, длина 410, sha256 d8be577aab581d77
- [да] MX: 20 mail.nashdekor.ru. 10 mail.nashdekor.ru. 
- [да] mail.nashdekor.ru → 185.60.134.150 
### ns1.firstvds.ru
- [да] SPF: v=spf1 ip4:185.60.134.150 mx ~all
- [да] DMARC: v=DMARC1; p=none; adkim=r; aspf=r
- [да] DKIM есть, длина 410, sha256 d8be577aab581d77
- [да] MX: 20 mail.nashdekor.ru. 10 mail.nashdekor.ru. 
- [да] mail.nashdekor.ru → 185.60.134.150 

## PTR (обратная запись)
- [да] PTR 185.60.134.150 → mail.nashdekor.ru. 

## Порты почты (сертификат)
- [да] порт 993: subject=CN=mail.nashdekor.ru notAfter=Feb  4 05:57:11 2027 GMT 
- [да] порт 465: subject=CN=mail.nashdekor.ru notAfter=Feb  4 05:57:11 2027 GMT 
- [да] порт 587 (STARTTLS): subject=CN=mail.nashdekor.ru notAfter=Feb  4 05:57:11 2027 GMT 
- порт 25 из GitHub не проверить (у раннеров закрыт исходящий 25)

## Сайты
- [да] https://nashdekor.ru/ → 200
- [да] https://mail.nashdekor.ru/ → 200
- [да] https://crm.nashdekor.ru/login → 200
- [да] https://mail.nashdekor.ru/pochta-dns.txt → 200

## Домен в реестре
- state:         REGISTERED, DELEGATED, UNVERIFIED
