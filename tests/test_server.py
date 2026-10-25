import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from kleene.server import Handler


def _request(url, data=None):
    post = data is not None
    headers = {"Content-Type": "application/json"} if post else {}
    body = json.dumps(data).encode() if post else None
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if post else "GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode()


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_health(self):
        status, body = _request(self.base + "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_analyze(self):
        status, body = _request(self.base + "/api/analyze", {
            "pattern": r"(a|b)+c?\d+", "text": "abababc42 x", "flags": ""})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["match"], "abababc42")
        self.assertGreater(len(data["nfa"]["nodes"]), 0)
        self.assertIsNotNone(data["dfa"])
        self.assertGreater(len(data["trace"]), 0)

    def test_analyze_captures(self):
        _, body = _request(self.base + "/api/analyze", {
            "pattern": r"(\d{4})-(\d{2})", "text": "2026-10", "flags": ""})
        data = json.loads(body)
        self.assertEqual(data["matches"][0]["groups"], ["2026", "10"])

    def test_bad_pattern(self):
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as ctx:
            _request(self.base + "/api/analyze",
                     {"pattern": "(a", "text": "a", "flags": ""})
        self.assertEqual(ctx.exception.code, 422)

    def test_bench(self):
        status, body = _request(self.base + "/api/bench", {})
        data = json.loads(body)
        self.assertIn("pathological", data)
        self.assertTrue(data["pathological"]["rows"])

    def test_static_index(self):
        status, body = _request(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn("Kleene", body)

    def test_static_traversal_blocked(self):
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as ctx:
            _request(self.base + "/../pyproject.toml")
        self.assertIn(ctx.exception.code, (404, 400))


if __name__ == "__main__":
    unittest.main()
