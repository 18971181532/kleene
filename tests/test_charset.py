import unittest

from kleene.charset import CharSet, is_digit, is_space, is_word


class TestCharSet(unittest.TestCase):
    def test_single(self):
        cs = CharSet.single("a")
        self.assertTrue(cs.match("a"))
        self.assertFalse(cs.match("b"))

    def test_range(self):
        cs = CharSet([(ord("a"), ord("z"))])
        self.assertTrue(cs.match("m"))
        self.assertFalse(cs.match("A"))
        self.assertFalse(cs.match("5"))

    def test_normalize_merges(self):
        cs = CharSet([(97, 99), (100, 102)])  # a-c and d-f touch
        self.assertEqual(cs.ranges, [(97, 102)])

    def test_negated(self):
        cs = CharSet([(ord("0"), ord("9"))], negated=True)
        self.assertFalse(cs.match("5"))
        self.assertTrue(cs.match("a"))

    def test_dot(self):
        dot = CharSet.dot()
        self.assertTrue(dot.match("a"))
        self.assertFalse(dot.match("\n"))
        self.assertFalse(dot.match("\r"))
        self.assertTrue(CharSet.dot(dotall=True).match("\n"))

    def test_union(self):
        digits = CharSet([(48, 57)])
        lower = CharSet([(97, 122)])
        u = digits.union(lower)
        self.assertTrue(u.match("5"))
        self.assertTrue(u.match("z"))
        self.assertFalse(u.match("A"))

    def test_union_negated(self):
        # [^0-9] union [a-c] -> a-c are now accepted even though not digits
        non_digit = CharSet([(48, 57)], negated=True)
        abc = CharSet([(ord("a"), ord("c"))])
        u = non_digit.union(abc)
        self.assertTrue(u.match("a"))
        self.assertTrue(u.match("z"))
        self.assertFalse(u.match("5"))

    def test_helpers(self):
        self.assertTrue(is_digit("9"))
        self.assertTrue(is_word("_"))
        self.assertTrue(is_space("\t"))
        self.assertFalse(is_space("x"))


if __name__ == "__main__":
    unittest.main()
