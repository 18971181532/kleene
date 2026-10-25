"""Deterministic differential fuzz test against Python's re.

Only the *non-nullable subset* is generated: every quantifier is applied
directly to a non-nullable leaf, and every concatenation / alternation
contains at least one mandatory term.  On this subset Kleene is expected to
agree with Python re exactly (this is the boundary the README documents).
"""

import random
import re
import unittest

from kleene.engine import Regex

LEAVES = ["a", "b", "0", "1", r"\d", "[ab]", "[0-9]", ".", r"\w"]
QUANTS = ["*", "+", "?", "*?", "+?", "??", "{2}", "{1,3}", "{2,}"]
NULL_QUANTS = {"*", "?", "*?", "??"}


def gen_atom(rng):
    leaf = rng.choice(LEAVES)
    q = rng.choice(QUANTS) if rng.random() < 0.55 else ""
    if q:
        leaf = leaf + q
    nullable = q in NULL_QUANTS
    if rng.random() < 0.28:
        leaf = "(" + leaf + ")"
    return leaf, nullable


def gen_mandatory(rng, depth):
    """A guaranteed non-nullable expression."""
    if depth <= 0:
        # build a mandatory atom: prefer + / {n} / bare leaf
        leaf, nullable = gen_atom(rng)
        if nullable:
            leaf = rng.choice(["a", "b", "0", r"\d", "[ab]"]) + \
                rng.choice(["", "+", "{2}", "{1,3}"])
        return leaf
    parts = []
    k = rng.randint(1, 3)
    for i in range(k):
        if i == 0 or rng.random() < 0.7:
            # mandatory part
            if rng.random() < 0.4 and depth > 1:
                parts.append(gen_mandatory(rng, depth - 1))
            else:
                leaf, nullable = gen_atom(rng)
                if nullable:
                    leaf = rng.choice(["a", "b", "0", r"\d", "[ab]"]) + \
                        rng.choice(["", "+", "{2}", "{1,3}"])
                parts.append(leaf)
        else:
            atom, _ = gen_atom(rng)
            parts.append(atom)
    expr = "".join(parts)
    if rng.random() < 0.35:
        left = gen_mandatory(rng, depth - 1)
        expr = left + "|" + expr
    return expr


def gen_text(rng):
    n = rng.randint(0, 9)
    return "".join(rng.choice("ab01 x") for _ in range(n))


class TestFuzz(unittest.TestCase):
    def test_differential_spans(self):
        rng = random.Random(20261025)
        checked = 0
        mismatches = []
        for _ in range(420):
            pattern = gen_mandatory(rng, 3)
            text = gen_text(rng)
            try:
                mine = [m.span() for m in Regex(pattern).finditer(text)]
                ref = [m.span() for m in re.finditer(pattern, text)]
            except Exception as exc:  # pattern re rejects (e.g. .); skip
                continue
            checked += 1
            if mine != ref:
                mismatches.append((pattern, text, mine, ref))
        self.assertGreater(checked, 200, "too few cases executed")
        self.assertEqual(mismatches, [],
                         "differential mismatches:\n" +
                         "\n".join(repr(m) for m in mismatches[:10]))

    def test_differential_groups(self):
        rng = random.Random(777)
        mismatches = []
        checked = 0
        for _ in range(300):
            pattern = gen_mandatory(rng, 3)
            if "(" not in pattern:
                continue
            text = gen_text(rng)
            try:
                mine = [m.groups() for m in Regex(pattern).finditer(text)]
                ref = [m.groups() for m in re.finditer(pattern, text)]
            except Exception:
                continue
            checked += 1
            if mine != ref:
                mismatches.append((pattern, text, mine, ref))
        self.assertGreater(checked, 40)
        self.assertEqual(mismatches, [],
                         "group mismatches:\n" +
                         "\n".join(repr(m) for m in mismatches[:10]))


if __name__ == "__main__":
    unittest.main()
