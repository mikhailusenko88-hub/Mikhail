"""Проверки аварийной панели без сервера: python3 -m unittest rescue/test_rescue.py"""
import importlib.util
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request


def load(tmp):
    os.environ.update(CRM_BASE=os.path.join(tmp, "crm"), STATE_DIR=os.path.join(tmp, "state"), SITE_CRON=os.path.join(tmp, "cron"),
                      SITE_SRC=os.path.join(tmp, "site"), CRM_PORT="1", RESCUE_PORT="0", DOMAIN="",
                      RESCUE_PASS_FILE=os.path.join(tmp, "rescue-pass"))
    open(os.path.join(tmp, "rescue-pass"), "w").write("Secret-Pass-1\n")
    spec = importlib.util.spec_from_file_location("rescue_t", os.path.join(os.path.dirname(__file__), "rescue.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        for d in ("crm/src/crm", "crm/prev/crm", "state", "site"):
            os.makedirs(os.path.join(t, d))
        open(os.path.join(t, "crm/src/crm/v"), "w").write("new")
        open(os.path.join(t, "crm/prev/crm/v"), "w").write("old")
        open(os.path.join(t, "cron"), "w").write("# Сайт\n#  - каждую минуту: (journalctl -t prostranstvo-sync)\n"
                                                 "* * * * *     prostranstvo  /usr/local/sbin/prostranstvo-sync 2>&1 | logger -t prostranstvo-sync\n"
                                                 "17 4 * * * root other\n")
        self.m = load(t)
        self.m.wait_crm = lambda sec=30: True
        self.m.sh = lambda cmd, timeout=60, user="": (0, "")

    def tearDown(self):
        self.tmp.cleanup()

    def test_selftest_and_page(self):
        self.assertEqual(self.m.selftest(), 0)

    def test_cron_toggle(self):
        cron = os.path.join(self.tmp.name, "cron")
        self.assertTrue(self.m.site_auto())
        self.m.site_cron(False)
        txt = open(cron).read()
        self.assertIn("#RESCUE# * * * * *     prostranstvo  /usr/local/sbin/prostranstvo-sync", txt)
        self.assertIn("#  - каждую минуту: (journalctl -t prostranstvo-sync)", txt)       # комментарий не тронут
        self.assertIn("\n17 4 * * * root other", txt)
        self.assertFalse(self.m.site_auto())
        self.m.site_cron(False)                                                                # повторно — без двойной метки
        self.assertNotIn("#RESCUE# #RESCUE#", open(cron).read())
        self.m.site_cron(True)
        self.assertNotIn("#RESCUE#", open(cron).read())
        self.assertTrue(self.m.site_auto())

    def test_rollback_swaps_and_back(self):
        src = os.path.join(self.tmp.name, "crm/src/crm/v")
        ok, msg = self.m.act_crm_rollback("")
        self.assertTrue(ok, msg)
        self.assertEqual(open(src).read(), "old")
        self.m.act_crm_rollback("")
        self.assertEqual(open(src).read(), "new")

    def test_auto_pause_flag(self):
        flag = os.path.join(self.tmp.name, "state/pause-auto")
        self.m.act_auto(False)
        self.assertTrue(os.path.exists(flag))
        self.m.act_auto(True)
        self.assertFalse(os.path.exists(flag))

    def test_site_pin_requires_listed_version(self):
        ok, msg = self.m.act_site_pin("a" * 40)
        self.assertFalse(ok)
        self.assertTrue(self.m.site_auto())                                                    # ничего не тронули

    def test_http_login_token_and_origin(self):
        srv = self.m.ThreadingHTTPServer(("127.0.0.1", 0), self.m.H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        base = f"http://127.0.0.1:{port}"
        self.m.status = lambda: {k: "работает" for k in ("crm", "site", "auto")} | {"crm_service": "active", "crm_ver": "x", "crm_prev": "y",
                                                                                     "site_ver": "z", "site_auto": "да", "disk": "1G", "services": "веб"}

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NoRedirect)

        def req(path, data=None, origin="https://crm.test", cookie=""):
            h = {"Host": "crm.test", "X-Real-IP": "10.0.0.5"}
            if origin:
                h["Origin"] = origin
            if cookie:
                h["Cookie"] = cookie
            r = urllib.request.Request(base + path, data=urllib.parse.urlencode(data).encode() if data is not None else None, headers=h)
            try:
                resp = op.open(r)
            except urllib.error.HTTPError as e:
                resp = e
            return resp.status if hasattr(resp, "status") else resp.code, resp.headers, resp.read().decode()

        code, _, body = req("/rescue/")
        self.assertEqual(code, 200); self.assertIn('name="pw"', body); self.assertNotIn("crm_restart", body)   # без входа — только форма
        code, _, body = req("/rescue/login", {"pw": "wrong"})
        self.assertEqual(code, 403); self.assertIn("Неверный пароль", body)
        code, _, body = req("/rescue/act", {"t": self.m.TOKEN, "act": "auto_off"})                       # без входа — нельзя
        self.assertEqual(code, 403)
        code, hdr, _ = req("/rescue/login", {"pw": "Secret-Pass-1"})
        self.assertEqual(code, 303)
        ck = hdr["Set-Cookie"].split(";")[0]
        self.assertIn("HttpOnly", hdr["Set-Cookie"]); self.assertIn("Secure", hdr["Set-Cookie"])
        code, _, body = req("/rescue/", cookie=ck)
        self.assertIn("Аварийная панель", body); self.assertIn("crm_restart", body)
        flag = os.path.join(self.tmp.name, "state/pause-auto")
        self.assertEqual(req("/rescue/act", {"t": "wrong", "act": "auto_off"}, cookie=ck)[0], 400)
        self.assertEqual(req("/rescue/act", {"t": self.m.TOKEN, "act": "auto_off"}, origin="https://evil.example", cookie=ck)[0], 400)
        self.assertFalse(os.path.exists(flag))
        self.assertEqual(req("/rescue/act", {"t": self.m.TOKEN, "act": "auto_off"}, cookie=ck)[0], 303)
        self.assertTrue(os.path.exists(flag))
        req("/rescue/act", {"t": self.m.TOKEN, "act": "crm_stop"}, cookie=ck)                             # без галочки — нет
        self.assertIn("галочку", self.m.LAST["msg"])
        for i in range(10):
            req("/rescue/login", {"pw": "bad"})
        code, _, body = req("/rescue/login", {"pw": "Secret-Pass-1"})                                   # подбор — пауза
        self.assertEqual(code, 429)
        srv.shutdown()


if __name__ == "__main__":
    unittest.main()
