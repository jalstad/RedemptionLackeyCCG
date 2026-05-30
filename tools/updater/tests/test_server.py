import json
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from tools.updater import server


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read()

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    def test_serves_index_html(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body.lower())

    def test_preview_endpoint_returns_current_version(self):
        status, data = self._post("/api/current", {})
        self.assertEqual(status, 200)
        self.assertEqual(data["version"], "2.3.1")

    def test_preview_invalid_paste_returns_ok_false(self):
        status, data = self._post("/api/preview", {
            "pasted_text": "too\tfew", "version": "2.3.2",
            "yymmdd": "260530", "message": "x"})
        self.assertEqual(status, 200)
        self.assertFalse(data["ok"])
        self.assertIn("error", data)
