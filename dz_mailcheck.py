#!/usr/bin/env python3
"""Проверка почт студий (26.11.2026, «ищи качественно»): с сайта студии — главная и страницы контактов — все почты,
телефоны и мессенджеры; для доменов почт — MX (принимает ли домен почту вообще).
Вход: dz/mc.txt — строки «site <адрес сайта>» и «mx <домен>». Выход — status/dz/mailcheck.json, шифр ключом dz/key.pub
(как dz-contacts), и status/dz/mailcheck.txt без адресов — сколько сделано."""
import base64, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

INFO = b"dz-contacts-v1"
PK = base64.b64decode(open("dz/key.pub").read().strip())
EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,12}")
BAD = re.compile(r"\.(png|jpe?g|gif|webp|svg|css|js)$|sentry|wixpress|example\.|domain\.|yourmail|@2x|noreply|no-reply|tilda\.", re.I)
CONTACT = re.compile(r"contact|kontakt|контакт|svyaz|about|o-nas|о-нас|o_nas|requisit|rekvizit", re.I)
MSG = re.compile(r"https?://(?:t\.me|wa\.me|api\.whatsapp\.com|max\.ru|vk\.com)/[^\s\"'<>)]+", re.I)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def seal(payload):
    eph = X25519PrivateKey.generate()
    epk = eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=INFO + epk + PK).derive(
        eph.exchange(X25519PublicKey.from_public_bytes(PK)))
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(key).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), INFO)
    b = lambda x: base64.b64encode(x).decode()  # noqa: E731
    return {"v": 1, "part": "mailcheck", "epk": b(epk), "nonce": b(nonce), "ct": b(ct)}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru"})
    with urllib.request.urlopen(req, timeout=25) as r:  # noqa: S310
        raw = r.read(3_000_000)
        cs = r.headers.get_content_charset() or "utf-8"
        return r.geturl(), raw.decode(cs, "replace")


def cf_decode(h):
    """Cloudflare прячет почты: data-cfemail="…" (XOR первым байтом)."""
    try:
        b = bytes.fromhex(h)
        return "".join(chr(c ^ b[0]) for c in b[1:])
    except ValueError:
        return ""


def harvest(html):
    mails = {m.lower() for m in EMAIL.findall(urllib.parse.unquote(html)) if not BAD.search(m)}
    mails |= {cf_decode(h).lower() for h in re.findall(r'data-cfemail="([0-9a-f]+)"', html)} - {""}
    msgs = sorted({m.rstrip("/.,") for m in MSG.findall(html)})
    return mails, msgs


def check_site(site):
    res = {"site": site, "pages": [], "emails": [], "msgs": [], "err": ""}
    seen_mail, seen_msg = set(), set()
    try:
        final, html = get(site)
    except Exception as e:  # noqa: BLE001
        res["err"] = str(e)[:200]
        if site.startswith("https://"):
            try:
                final, html = get("http://" + site[8:])
                res["err"] = ""
            except Exception as e2:  # noqa: BLE001
                res["err"] += " | http: " + str(e2)[:150]
                return res
        else:
            return res
    m, g = harvest(html)
    seen_mail |= m; seen_msg |= set(g)
    res["pages"].append({"url": final, "emails": sorted(m)})
    links = []
    for href, text in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        if CONTACT.search(href) or CONTACT.search(re.sub("<[^>]+>", "", text)):
            u = urllib.parse.urljoin(final, href)
            if urllib.parse.urlparse(u).netloc == urllib.parse.urlparse(final).netloc and u not in links:
                links.append(u)
    for guess in ("/contacts/", "/kontakty/", "/contact/"):
        u = urllib.parse.urljoin(final, guess)
        if u not in links:
            links.append(u)
    for u in links[:5]:
        try:
            fu, h = get(u)
        except Exception:  # noqa: BLE001
            continue
        m, g = harvest(h)
        seen_mail |= m; seen_msg |= set(g)
        res["pages"].append({"url": fu, "emails": sorted(m)})
        time.sleep(0.5)
    res["emails"] = sorted(seen_mail)
    res["msgs"] = sorted(seen_msg)
    return res


def mx(dom):
    try:
        out = subprocess.run(["dig", "+short", "MX", dom], capture_output=True, text=True, timeout=20).stdout.split()
        return [x.rstrip(".") for x in out if not x.isdigit()]
    except Exception as e:  # noqa: BLE001
        return ["ошибка: " + str(e)[:80]]


def main():
    sites, doms = [], []
    for line in open("dz/mc.txt", encoding="utf-8"):
        line = line.strip()
        if line.startswith("site "):
            sites.append(line[5:].strip())
        elif line.startswith("mx "):
            doms.append(line[3:].strip())
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sites": [check_site(s) for s in sites],
           "mx": {d: mx(d) for d in doms}}
    os.makedirs("status/dz", exist_ok=True)
    json.dump(seal(out), open("status/dz/mailcheck.json", "w"))
    ok = sum(1 for s in out["sites"] if not s["err"])
    nomx = sum(1 for v in out["mx"].values() if not v)
    open("status/dz/mailcheck.txt", "w").write(f"{out['at']}: сайтов {len(sites)}, открылись {ok}; доменов {len(doms)}, без MX {nomx}\n")


if __name__ == "__main__":
    sys.exit(main())
