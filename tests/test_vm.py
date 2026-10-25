import re
import time
import unittest

from kleene.engine import Regex


def spans(pattern, text, flags=0):
    return [m.span() for m in Regex(pattern, flags).finditer(text)]


def groups(pattern, text):
    return [m.groups() for m in Regex(pattern).finditer(text)]


class TestVM(unittest.TestCase):
    def test_literal(self):
        self.assertEqual(Regex("abc").search("xxabcxx").group(0), "abc")
        self.assertIsNone(Regex("abc").search("ab"))

    def test_concat_quantifiers(self):
        self.assertEqual(Regex("a+").search("aaab").group(0), "aaa")
        self.assertEqual(Regex("ab*").search("abbbc").group(0), "abbb")
        self.assertEqual(Regex("a?b").search("b").group(0), "b")
        self.assertEqual(Regex("a{2,3}").search("aaaaa").group(0), "aaa")

    def test_greedy_extends(self):
        # greedy must extend then backtrack to satisfy the trailing 'a'
        self.assertEqual(Regex("[ab]+a").search("abab").group(0), "aba")

    def test_lazy_shortest(self):
        self.assertEqual(Regex("a+?").search("aaa").group(0), "a")
        self.assertEqual(Regex(".+?a").search("zzza").group(0), "zzza")

    def test_alternation_priority(self):
        self.assertEqual(Regex("cat|category").search("category").group(0),
                         "cat")
        self.assertEqual(Regex("a+?a").search("aaa").group(0), "aa")

    def test_char_classes(self):
        self.assertEqual(Regex(r"\d+").search("ab42x").group(0), "42")
        self.assertEqual(Regex(r"\w+").search("hi_1 x").group(0), "hi_1")
        self.assertEqual(Regex(r"\s+").search("a  b").span(0), (1, 3))
        self.assertEqual(Regex(r"[a-c]+").search("xaby").group(0), "ab")
        self.assertEqual(Regex(r"[^0-9]+").search("ab12").group(0), "ab")

    def test_dot(self):
        self.assertEqual(Regex("a.c").search("a\nc"), None)
        from kleene.engine import DOTALL
        self.assertEqual(Regex("a.c", DOTALL).search("a\nc").group(0), "a\nc")

    def test_anchors(self):
        self.assertIsNotNone(Regex("^ab").search("ab\ncd"))
        self.assertIsNone(Regex("^cd").search("ab\ncd"))
        self.assertIsNotNone(Regex("cd$").search("ab\ncd"))
        from kleene.engine import MULTILINE
        self.assertEqual(Regex(r"^\w+", MULTILINE).findall("ab\ncd"),
                         ["ab", "cd"])

    def test_word_boundary(self):
        self.assertEqual(Regex(r"\bword\b").search("a word here").group(0),
                         "word")
        self.assertIsNone(Regex(r"\bword\b").search("password"))

    def test_captures(self):
        m = Regex(r"(\d{4})-(\d{2})-(\d{2})").search("date 2026-10-25")
        self.assertEqual(m.groups(), ("2026", "10", "25"))
        self.assertEqual(m.span(1), (5, 9))

    def test_noncapture(self):
        m = Regex(r"(?:ab)+(\d+)").search("abab42")
        self.assertEqual(m.groups(), ("42",))

    def test_optional_capture(self):
        m = Regex(r"(a)?(b)").search("b")
        self.assertEqual(m.groups(), (None, "b"))

    def test_findall_overlaps(self):
        self.assertEqual(Regex(r"\d+").findall("a1 b22 c3"),
                         ["1", "22", "3"])
        self.assertEqual(Regex(r"(\w)@(\w)").findall("a@b x@y"),
                         [("a", "b"), ("x", "y")])

    def test_empty_matches(self):
        # a* over 'ab': "a" at 0, empty at 1, empty at 2 (matches re)
        result = [m.group(0) for m in Regex("a*").finditer("ab")]
        self.assertEqual(result, ["a", "", ""])
        self.assertEqual([m.group(0) for m in re.finditer("a*", "ab")],
                         result)

    def test_fullmatch(self):
        self.assertIsNotNone(Regex(r"\d+").fullmatch("42"))
        self.assertIsNone(Regex(r"\d+").fullmatch("42x"))

    def test_match_prefix(self):
        self.assertIsNotNone(Regex(r"\d+").match("42x"))
        self.assertIsNone(Regex(r"\d+").match("x42"))

    def test_split(self):
        self.assertEqual(Regex(r"\s+").split("a  b c"),
                         ["a", "b", "c"])
        self.assertEqual(Regex(r"(\d+)").split("a1b2c"),
                         ["a", "1", "b", "2", "c"])

    def test_sub(self):
        self.assertEqual(Regex(r"\d+").sub("#", "a1 b22"), "a# b#")
        self.assertEqual(Regex(r"(\d+)").sub(r"[\1]", "a1 b2"), "a[1] b[2]")
        self.assertEqual(Regex(r"(\d+)").sub(lambda m: m.group(1) * 2, "a3"),
                         "a33")

    def test_ignorecase(self):
        from kleene.engine import IGNORECASE
        self.assertEqual(Regex("abc", IGNORECASE).search("xABCy").group(0),
                         "ABC")

    def test_trace_structure(self):
        frames = Regex("ab").trace("ab")
        self.assertEqual(frames[0]["position"], 0)
        self.assertTrue(any(f["accepted_ends"] for f in frames))

    def test_linear_time(self):
        # catastrophic backtracking pattern must be fast at large n
        pattern = "(a+)+b"
        text = "a" * 50000
        t0 = time.perf_counter()
        result = Regex(pattern).search(text)
        dt = time.perf_counter() - t0
        self.assertIsNone(result)
        self.assertLess(dt, 2.0, "engine should be linear, took %.2fs" % dt)


class TestDifferential(unittest.TestCase):
    """Differential checks against Python re on the non-nullable subset."""

    CASES = [
        (r"abc", "xabcy"),
        (r"[ab]+a", "abab"),
        (r"(a|b)+c?\d+", "abababc42 x"),
        (r"a+?a", "aaa"),
        (r".+?a", "zzza"),
        (r"[ab]+\w?a+?1*?", "aba"),
        (r"(\d{4})-(\d{2})-(\d{2})", "2026-10-25 2020-01-01"),
        (r"\d+", "a1 b22 c333"),
        (r"\w+@\w+", "mail a@b here"),
        (r"[a-z]+", "AbCdEf"),
        (r"ab{2,4}", "abbbb"),
        (r"(cat|dog)s?", "cats and dogs"),
        (r"https?://\S+", "see http://x.com now"),
        (r"[\w.+-]+@[\w-]+\.[\w.-]+", "x@y.dev"),
        (r"a(b|c)*d", "abcbcd"),
        (r"(ab|cd)+", "abxcd"),
        (r"\s+", "a  b\tc\nd"),
        (r"[^aeiou]+", "consonants"),
        (r"a{2}", "aaaaa"),
        (r"colou?r", "color and colour"),
    ]

    def test_spans_match_re(self):
        for pattern, text in self.CASES:
            mine = spans(pattern, text)
            ref = [m.span() for m in re.finditer(pattern, text)]
            self.assertEqual(mine, ref, f"span mismatch for {pattern!r}")

    def test_groups_match_re(self):
        for pattern, text in self.CASES:
            if "(" not in pattern:
                continue
            mine = groups(pattern, text)
            ref = [m.groups() for m in re.finditer(pattern, text)]
            self.assertEqual(mine, ref, f"group mismatch for {pattern!r}")


if __name__ == "__main__":
    unittest.main()
