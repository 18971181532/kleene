"""Character classes: normalized, union-able sets of Unicode code points."""

import sys

MAX_CP = sys.maxunicode

# Shorthand character classes (matches Python's re semantics).
DIGITS = [(48, 57)]            # 0-9
WORD = [(48, 57), (65, 90), (97, 122), (95, 95)]  # 0-9 A-Z a-z _
WHITESPACE = [(9, 13), (32, 32)]  # tab..cr, space


def in_ranges(ch: str, ranges) -> bool:
    cp = ord(ch)
    for lo, hi in ranges:
        if lo <= cp <= hi:
            return True
    return False


def is_word(ch: str) -> bool:
    return in_ranges(ch, WORD)


def is_digit(ch: str) -> bool:
    return DIGITS[0][0] <= ord(ch) <= DIGITS[0][1]


def is_space(ch: str) -> bool:
    return in_ranges(ch, WHITESPACE)


class CharSet:
    """A set of code points as a sorted, merged list of inclusive ranges."""

    def __init__(self, ranges=None, negated=False):
        self.ranges = self._normalize(ranges or [])
        self.negated = negated

    @staticmethod
    def _normalize(ranges):
        if not ranges:
            return []
        rs = sorted((lo, hi) for lo, hi in ranges if lo <= hi)
        merged = [list(rs[0])]
        for lo, hi in rs[1:]:
            if lo <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        return [(lo, hi) for lo, hi in merged]

    @classmethod
    def single(cls, ch: str) -> "CharSet":
        return cls([(ord(ch), ord(ch))])

    @classmethod
    def dot(cls, dotall=False) -> "CharSet":
        # Dot matches any char except newline (unless dotall).
        cs = cls([(0, MAX_CP)], negated=False)
        if not dotall:
            cs.negated = True
            cs.ranges = [(10, 10), (13, 13)]
        return cs

    def match(self, ch: str) -> bool:
        hit = self._contains(ord(ch))
        return (not hit) if self.negated else hit

    def _contains(self, cp: int) -> bool:
        for lo, hi in self.ranges:
            if cp < lo:
                return False
            if cp <= hi:
                return True
        return False

    def union(self, other: "CharSet") -> "CharSet":
        """Union with another CharSet. Negation is handled conservatively."""
        if self.negated or other.negated:
            # Keep correctness: represent a negated union by computing the
            # complement of the intersection of the excluded sets.
            if self.negated and not other.negated:
                # (complement A) ∪ B = complement (A \ B)
                kept = self._subtract_ranges(self.ranges, other.ranges)
                return CharSet(kept, negated=True)
            if other.negated and not self.negated:
                kept = self._subtract_ranges(other.ranges, self.ranges)
                return CharSet(kept, negated=True)
            both = self._intersect_ranges(self.ranges, other.ranges)
            return CharSet(both, negated=True)
        return CharSet(self.ranges + other.ranges)

    @staticmethod
    def _subtract_ranges(a, b):
        out = []
        for lo, hi in a:
            cur = [(lo, hi)]
            for blo, bhi in b:
                nxt = []
                for x, y in cur:
                    if bhi < x or blo > y:
                        nxt.append((x, y))
                    else:
                        if x < blo:
                            nxt.append((x, min(y, blo - 1)))
                        if y > bhi:
                            nxt.append((max(x, bhi + 1), y))
                cur = nxt
            out.extend(cur)
        return out

    @staticmethod
    def _intersect_ranges(a, b):
        out = []
        i = j = 0
        while i < len(a) and j < len(b):
            lo = max(a[i][0], b[j][0])
            hi = min(a[i][1], b[j][1])
            if lo <= hi:
                out.append((lo, hi))
            if a[i][1] < b[j][1]:
                i += 1
            else:
                j += 1
        return out

    def label(self) -> str:
        """Compact text label for graph rendering."""
        if self.negated and not self.ranges:
            return "."
        if self.negated and self.ranges == [(10, 10), (13, 13)]:
            return "."
        if not self.negated:
            if len(self.ranges) == 1:
                lo, hi = self.ranges[0]
                if lo == hi:
                    return self._name_cp(lo)
            if self.ranges == [(48, 57)]:
                return "\\d"
            if self.ranges == WORD:
                return "\\w"
            if self.ranges == WHITESPACE:
                return "\\s"
        return "[^]" if self.negated else "[]"

    def fold_case(self):
        """Return a case-insensitive version of this set (IGNORECASE).

        ASCII letters are folded by range (cheap and exact); non-ASCII
        letters in small Latin-1 ranges are mapped per code point.
        """
        ranges = list(self.ranges)
        for lo, hi in self.ranges:
            # A-Z -> a-z
            al, ah = max(lo, 65), min(hi, 90)
            if al <= ah:
                ranges.append((al + 32, ah + 32))
            # a-z -> A-Z
            al, ah = max(lo, 97), min(hi, 122)
            if al <= ah:
                ranges.append((al - 32, ah - 32))
            # non-ASCII letters in bounded Latin-1 ranges
            if hi <= 0xFF and (hi - lo) <= 256:
                for cp in range(lo, hi + 1):
                    if 123 <= cp <= 0xFF:
                        ch = chr(cp)
                        if ch.isalpha():
                            for mapped in (ch.upper(), ch.lower()):
                                if len(mapped) == 1:
                                    ranges.append((ord(mapped), ord(mapped)))
        return CharSet(ranges, negated=self.negated)

    def describe(self) -> str:
        """Human-readable representation of the class."""
        parts = []
        for lo, hi in self.ranges:
            parts.append(self._name_cp(lo) if lo == hi
                         else f"{self._name_cp(lo)}-{self._name_cp(hi)}")
        body = "".join(parts)
        if self.negated:
            if not self.ranges:
                return "."
            return f"[^{body}]"
        if len(self.ranges) == 1 and self.ranges[0][0] == self.ranges[0][1]:
            return self._name_cp(self.ranges[0][0])
        return f"[{body}]"

    @staticmethod
    def _name_cp(cp: int) -> str:
        special = {0: "\\0", 9: "\\t", 10: "\\n", 13: "\\r", 32: " ",
                   45: "\\-", 91: "\\[", 92: "\\\\", 93: "\\]",
                   94: "\\^", 124: "\\|", 40: "\\(", 41: "\\)",
                   42: "\\*", 43: "\\+", 63: "\\?", 46: "\\.",
                   123: "\\{", 125: "\\}"}
        if cp in special:
            return special[cp]
        return chr(cp)
