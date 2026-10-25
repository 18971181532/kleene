import unittest

from kleene import ast as A
from kleene.ast import ParseError


def parse(pattern):
    return A.Parser(pattern).parse()


class TestParser(unittest.TestCase):
    def test_literal_concat(self):
        tree = parse("abc")
        self.assertIsInstance(tree, A.Concat)
        self.assertEqual(len(tree.parts), 3)

    def test_alternation(self):
        tree = parse("ab|cd|ef")
        self.assertIsInstance(tree, A.Alt)
        self.assertEqual(len(tree.options), 3)

    def test_greedy_repeats(self):
        star = parse("a*")
        self.assertEqual((star.minimum, star.maximum, star.lazy),
                         (0, None, False))
        plus = parse("a+")
        self.assertEqual((plus.minimum, plus.maximum), (1, None))
        opt = parse("a?")
        self.assertEqual((opt.minimum, opt.maximum), (0, 1))
        rep = parse("a{2,5}")
        self.assertEqual((rep.minimum, rep.maximum), (2, 5))

    def test_lazy_repeats(self):
        for pat, mn, mx in [("a*?", 0, None), ("a+?", 1, None),
                           ("a??", 0, 1), ("a{2,}?", 2, None)]:
            node = parse(pat)
            self.assertTrue(node.lazy, pat)
            self.assertEqual(node.minimum, mn)
            self.assertEqual(node.maximum, mx)

    def test_capture_group(self):
        node = parse("(a)(b)")
        groups = [p for p in node.parts if isinstance(p, A.Group)]
        self.assertEqual([g.index for g in groups], [1, 2])

    def test_noncapture_group(self):
        node = parse("(?:abc)+")
        # outer is a repeat; its child is the group's content directly
        self.assertIsInstance(node, A.Repeat)
        self.assertIsInstance(node.child, A.Concat)

    def test_char_class(self):
        tree = parse("[^0-9a-z]")
        self.assertIsInstance(tree, A.Char)
        self.assertTrue(tree.charset.negated)

    def test_assertions(self):
        self.assertIsInstance(parse("^a"), A.Concat)
        kinds = []
        for p in parse(r"\bword\b").parts:
            if isinstance(p, A.Assertion):
                kinds.append(p.kind)
        self.assertEqual(kinds, ["boundary", "boundary"])
        self.assertIsInstance(parse(r"\B"), A.Assertion)

    def test_backreference_rejected(self):
        with self.assertRaises(ParseError):
            parse(r"(a)\1")

    def test_unbalanced_group(self):
        with self.assertRaises(ParseError):
            parse("(abc")

    def test_bad_repeat(self):
        with self.assertRaises(ParseError):
            parse("a{3,2}")

    def test_shorthand_escapes(self):
        for pat in [r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", r"\t", r"\n"]:
            self.assertIsNotNone(parse(pat), pat)


if __name__ == "__main__":
    unittest.main()
