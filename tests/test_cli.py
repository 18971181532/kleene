import io
import json
import unittest
from contextlib import redirect_stdout

from kleene.cli import main


def run(*args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(list(args))
    return code, buf.getvalue()


class TestCLI(unittest.TestCase):
    def test_match(self):
        code, out = run("match", r"\d+", "a42b")
        self.assertEqual(code, 0)
        self.assertIn("42", out)

    def test_match_json(self):
        code, out = run("match", r"(\d+)", "a42b", "--json")
        data = json.loads(out)
        self.assertEqual(data[0]["match"], "42")
        self.assertEqual(data[0]["groups"], ["42"])

    def test_findall(self):
        code, out = run("findall", r"\w+", "a b c")
        self.assertEqual(out.strip().split(), ["a", "b", "c"])

    def test_fullmatch(self):
        code, _ = run("fullmatch", r"\d+", "42")
        self.assertEqual(code, 0)
        code, _ = run("fullmatch", r"\d+", "42x")
        self.assertEqual(code, 1)

    def test_split(self):
        code, out = run("split", r"\s+", "a  b c")
        self.assertEqual(out.strip().split(), ["a", "b", "c"])

    def test_sub(self):
        code, out = run("sub", r"\d+", "#", "a1 b2")
        self.assertEqual(out, "a# b#")

    def test_explain_json(self):
        code, out = run("explain", "(a|b)+", "--json")
        data = json.loads(out)
        self.assertEqual(data["groups"], 1)
        self.assertGreater(data["states"], 0)

    def test_nfa_json(self):
        code, out = run("nfa", "ab")
        data = json.loads(out)
        self.assertTrue(len(data["nodes"]) >= 2)

    def test_dfa_json(self):
        code, out = run("dfa", "ab")
        data = json.loads(out)
        self.assertTrue(any(n["accept"] for n in data["nodes"]))

    def test_trace_json(self):
        code, out = run("trace", "ab", "ab", "--json")
        frames = json.loads(out)
        self.assertTrue(any(f["accepted_ends"] for f in frames))

    def test_bench_json(self):
        code, out = run("bench", "--json")
        data = json.loads(out)
        self.assertIn("pathological", data)
        self.assertIn("ordinary", data)

    def test_parse_error_exit(self):
        code, _ = run("match", "(a", "aaa")
        self.assertEqual(code, 2)

    def test_backreference_rejected(self):
        code, _ = run("match", r"(a)\1", "aa")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
