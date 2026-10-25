"""Regex AST nodes and a recursive-descent parser.

Grammar:
    pattern      := alternation
    alternation  := concat ('|' concat)*
    concat       := repeat*
    repeat       := atom quantifier?
    atom         := group | class | dot | assertion | escape | literal
    group        := '(' (?: ...)? alternation ')'
"""

from .charset import (CharSet, DIGITS, WHITESPACE, WORD, is_digit,
                      is_space, is_word)


# ---------------------------------------------------------------- AST ----
class Node:
    pass


class Char(Node):
    def __init__(self, charset: CharSet):
        self.charset = charset


class Assertion(Node):
    # kind in start, end, boundary, not_boundary
    def __init__(self, kind: str):
        self.kind = kind


class Concat(Node):
    def __init__(self, parts):
        self.parts = parts


class Alt(Node):
    def __init__(self, options):
        self.options = options


class Repeat(Node):
    def __init__(self, child, minimum, maximum, lazy=False):
        self.child = child
        self.minimum = minimum
        self.maximum = maximum  # None == unbounded
        self.lazy = lazy


class Group(Node):
    def __init__(self, child, index):
        self.child = child
        self.index = index  # 1-based capture index, None for non-capturing


# ------------------------------------------------------------- parser ----
class ParseError(Exception):
    pass


class Parser:
    def __init__(self, pattern: str, flags=0):
        self.pattern = pattern
        self.i = 0
        self.flags = flags
        self.dotall = bool(flags & 0x10)         # re.DOTALL
        self.multiline = bool(flags & 0x08)      # re.MULTILINE
        self.group_count = 0

    def peek(self):
        return self.pattern[self.i] if self.i < len(self.pattern) else None

    def next(self):
        ch = self.pattern[self.i]
        self.i += 1
        return ch

    def expect(self, ch):
        if self.peek() != ch:
            raise ParseError(f"expected '{ch}' at {self.i}")
        self.next()

    def parse(self):
        node = self.parse_alt()
        if self.i < len(self.pattern):
            raise ParseError(f"unexpected character '{self.peek()}' at "
                             f"{self.i}")
        return node

    def parse_alt(self):
        options = [self.parse_concat()]
        while self.peek() == "|":
            self.next()
            options.append(self.parse_concat())
        if len(options) == 1:
            return options[0]
        return Alt(options)

    def parse_concat(self):
        parts = []
        while self.peek() is not None and self.peek() not in "|)":
            atom = self.parse_repeat()
            if atom is not None:
                parts.append(atom)
        if len(parts) == 1:
            return parts[0]
        return Concat(parts)

    def parse_repeat(self):
        atom = self.parse_atom()
        if atom is None:
            return None
        ch = self.peek()
        if ch is not None and ch in "*+?":
            self.next()
            lazy = self.peek() == "?"
            if lazy:
                self.next()
            if ch == "*":
                return Repeat(atom, 0, None, lazy)
            if ch == "+":
                return Repeat(atom, 1, None, lazy)
            return Repeat(atom, 0, 1, lazy)
        if ch == "{":
            saved = self.i
            try:
                minimum, maximum = self._parse_brace()
            except ParseError:
                self.i = saved
                return atom
            lazy = self.peek() == "?"
            if lazy:
                self.next()
            return Repeat(atom, minimum, maximum, lazy)
        return atom

    def _parse_brace(self):
        self.expect("{")
        start = self.i
        digits = ""
        while self.peek() and self.peek().isdigit():
            digits += self.next()
        if not digits:
            raise ParseError("bad repetition")
        minimum = int(digits)
        maximum = minimum
        if self.peek() == ",":
            self.next()
            more = ""
            while self.peek() and self.peek().isdigit():
                more += self.next()
            maximum = int(more) if more else None
        self.expect("}")
        if maximum is not None and maximum < minimum:
            raise ParseError("bad repetition bounds")
        return minimum, maximum

    def parse_atom(self):
        ch = self.peek()
        if ch is None:
            return None
        if ch == "(":
            return self.parse_group()
        if ch == "[":
            return self.parse_class()
        if ch == ".":
            self.next()
            return Char(CharSet.dot(self.dotall))
        if ch == "^":
            self.next()
            return Assertion("start")
        if ch == "$":
            self.next()
            return Assertion("end")
        if ch == "\\":
            return self.parse_escape(in_class=False)
        if ch in ")*+?{}":
            raise ParseError(f"unexpected '{ch}' at {self.i}")
        self.next()
        return Char(CharSet.single(ch))

    def parse_group(self):
        self.expect("(")
        non_capture = False
        if self.peek() == "?":
            self.next()
            if self.peek() != ":":
                raise ParseError("unsupported group syntax")
            self.next()
            non_capture = True
        if not non_capture:
            self.group_count += 1
            index = self.group_count
        child = self.parse_alt()
        self.expect(")")
        return child if non_capture else Group(child, index)

    def parse_class(self):
        self.expect("[")
        negated = False
        if self.peek() == "^":
            negated = True
            self.next()
        ranges = []
        first = True
        while first or self.peek() != "]":
            first = False
            if self.peek() is None:
                raise ParseError("unterminated character class")
            item = self.parse_class_item()
            if self.peek() == "-" and self.pattern[self.i + 1:self.i + 2] not in ("]", ""):
                self.next()
                end = self.parse_class_item()
                lo = self._item_cp(item)
                hi = self._item_cp(end)
                if lo is None or hi is None:
                    raise ParseError("unsupported range")
                if lo > hi:
                    raise ParseError("bad character range")
                ranges.append((lo, hi))
            else:
                self._add_item(ranges, item)
        self.expect("]")
        return Char(CharSet(ranges, negated=negated))

    def parse_class_item(self):
        if self.peek() == "\\":
            return self.parse_escape(in_class=True)
        ch = self.next()
        return ("char", ch)

    def _item_cp(self, item):
        kind, value = item
        if kind == "charset":
            if len(value.ranges) == 1 and value.ranges[0][0] == value.ranges[0][1]:
                return value.ranges[0][0]
            return None
        return ord(value)

    def _add_item(self, ranges, item):
        kind, value = item
        if kind == "charset":
            if value.negated:
                raise ParseError("negated shorthand inside class")
            ranges.extend(value.ranges)
        else:
            ranges.append((ord(value), ord(value)))

    def parse_escape(self, in_class):
        self.expect("\\")
        ch = self.peek()
        if ch is None:
            raise ParseError("trailing backslash")
        self.next()
        # shorthand classes
        shorthand = {
            "d": (DIGITS, False),
            "D": (DIGITS, True),
            "w": (WORD, False),
            "W": (WORD, True),
            "s": (WHITESPACE, False),
            "S": (WHITESPACE, True),
        }
        if ch in shorthand:
            rng, neg = shorthand[ch]
            return ("charset", CharSet(rng, negated=neg)) if in_class \
                else Char(CharSet(rng, negated=neg))
        if ch == "b" and not in_class:
            return Assertion("boundary")
        if ch == "B" and not in_class:
            return Assertion("not_boundary")
        if ch in "bB" and in_class:
            return ("char", "\b") if ch == "b" else ("char", "B")
        simple = {"t": "\t", "n": "\n", "r": "\r", "f": "\f", "v": "\v",
                  "0": "\x00"}
        if ch in "123456789":
            raise ParseError(
                "backreferences (\\1..\\9) are not supported")
        if ch in simple:
            literal = simple[ch]
        elif ch == "x" or ch == "u":
            width = 2 if ch == "x" else 4
            hexs = ""
            for _ in range(width):
                c = self.peek()
                if c is None or c not in "0123456789abcdefABCDEF":
                    raise ParseError(f"bad \\{ch} escape")
                hexs += self.next()
            literal = chr(int(hexs, 16))
        else:
            literal = ch  # escaped literal
        return ("char", literal) if in_class else Char(CharSet.single(literal))


def parse(pattern: str, flags=0):
    p = Parser(pattern, flags)
    return p.parse(), p.group_count
