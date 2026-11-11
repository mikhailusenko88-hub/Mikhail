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
                      SITE_SRC=os.path.join(tmp, "site"), CRM_PORT="1", RESCUE_PORT="0", DOMAIN="")
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

    def test_http_token_and_origin(self):
        srv = self.m.ThreadingHTTPServer(("127.0.0.1", 0), self.m.H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        self.m.status = lambda: {k: "работает" for k in ("crm", "site", "auto")} | {"crm_service": "active", "crm_ver": "x", "crm_prev": "y",
                                                                                     "site_ver": "z", "site_auto": "да", "disk": "1G", "services": "веб"}
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/rescue/").read().decode()
        self.assertIn("Аварийная панель", page)

        def post(data, origin):
            req = urllib.request.Request(f"http://127.0.0.1:{port}/rescue/act", data=urllib.parse.urlencode(data).encode(),
                                         headers={"Origin": origin, "Host": "crm.test"})
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        flag = os.path.join(self.tmp.name, "state/pause-auto")
        self.assertEqual(post({"t": "wrong", "act": "auto_off"}, "https://crm.test"), 400)
        self.assertEqual(post({"t": self.m.TOKEN, "act": "auto_off"}, "https://evil.example"), 400)
        self.assertFalse(os.path.exists(flag))
        post({"t": self.m.TOKEN, "act": "auto_off"}, "https://crm.test")
        self.assertTrue(os.path.exists(flag))
        post({"t": self.m.TOKEN, "act": "crm_stop"}, "https://crm.test")                       # без галочки — нет
        self.assertIn("галочку", self.m.LAST["msg"])
        srv.shutdown()


if __name__ == "__main__":
    unittest.main()
