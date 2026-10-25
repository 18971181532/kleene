import re
import unittest

from kleene.dfa import DFAUnsupported
from kleene.engine import Regex


class TestDFA(unittest.TestCase):
    def test_build(self):
        rx = Regex("ab")
        self.assertIsNotNone(rx.dfa)
        graph = rx.dfa_graph()
        self.assertTrue(any(n["accept"] for n in graph["nodes"]))

    def test_fullmatch_simple(self):
        rx = Regex("ab+c*")
        self.assertTrue(rx.dfa.fullmatch("abc"))
        self.assertTrue(rx.dfa.fullmatch("abbbc"))
        self.assertTrue(rx.dfa.fullmatch("ab"))
        self.assertFalse(rx.dfa.fullmatch("ac"))
        self.assertFalse(rx.dfa.fullmatch("abx"))

    def test_prefix_end(self):
        rx = Regex("a+")
        self.assertEqual(rx.dfa.prefix_end("aaab"), 3)
        self.assertEqual(rx.dfa.prefix_end("bbb"), -1)

    def test_fullmatch_vs_re(self):
        patterns = [r"ab*", r"[0-9]+", r"(a|b)+c", r"\w+\d*",
                    r"x{2,4}y?", r"[\w.]+", r"a(b|c)*d"]
        samples = ["", "a", "ab", "abbb", "123", "abc", "abcbcd",
                   "xxx", "xxy", "a.b.c", "word1"]
        for pat in patterns:
            rx = Regex(pat)
            if rx.dfa is None:
                continue
            for s in samples:
                mine = bool(rx.dfa.fullmatch(s))
                ref = re.fullmatch(pat, s) is not None
                self.assertEqual(mine, ref, f"{pat!r} fullmatch {s!r}")

    def test_assertion_unsupported(self):
        rx = Regex(r"^a\b")
        self.assertIsNone(rx.dfa)
        with self.assertRaises(DFAUnsupported):
            # constructing directly from an NFA that contains an assert
            from kleene.compiler import compile_pattern
            nfa, _, _ = compile_pattern("^a", 0)
            from kleene.dfa import DFA
            DFA(nfa)


if __name__ == "__main__":
    unittest.main()
