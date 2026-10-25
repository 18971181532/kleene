import unittest

from kleene import compile
from kleene.engine import Regex


class TestEngine(unittest.TestCase):
    def test_compile_factory(self):
        rx = compile("a+")
        self.assertIsInstance(rx, Regex)

    def test_explain(self):
        rx = compile("(a|b)+c?")
        info = rx.explain()
        self.assertEqual(info["groups"], 1)
        self.assertGreater(info["states"], 0)
        self.assertGreater(info["edges"], 0)
        self.assertIn("ast", info)
        self.assertTrue(info["dfa_supported"])

    def test_explain_dfa_unsupported_for_assertion(self):
        info = compile("^a").explain()
        self.assertFalse(info["dfa_supported"])

    def test_ast_to_dict(self):
        d = compile("a|b").explain()["ast"]
        self.assertEqual(d["type"], "alt")
        self.assertEqual(len(d["options"]), 2)

    def test_graphs(self):
        rx = compile("ab+")
        nfa = rx.nfa_graph()
        self.assertIn("nodes", nfa)
        self.assertIn("edges", nfa)
        dfa = rx.dfa_graph()
        self.assertIn("nodes", dfa)

    def test_findall_groups(self):
        self.assertEqual(compile("(a)(b)").findall("ab"), [("a", "b")])
        self.assertEqual(compile("a").findall("aba"), ["a", "a"])
        self.assertEqual(compile("(a)").findall("aba"), ["a", "a"])


if __name__ == "__main__":
    unittest.main()
