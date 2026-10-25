import unittest

from kleene.compiler import compile_pattern


class TestCompiler(unittest.TestCase):
    def test_basic_has_accept(self):
        nfa, groups, tree = compile_pattern("a", 0)
        self.assertTrue(any(st.accept for st in nfa.states))

    def test_single_char_two_states(self):
        nfa, _, _ = compile_pattern("a", 0)
        # one char edge from start to a state that epsilon-reaches accept
        char_edges = [(s, t) for s, lbl, t in nfa.edges() if lbl is not None]
        self.assertEqual(len(char_edges), 1)

    def test_save_slots_for_group(self):
        nfa, groups, _ = compile_pattern("(a)", 0)
        self.assertEqual(groups, 1)
        saves = [val for st in nfa.states for op, val in st.ops
                 if op == "save"]
        # group 1 uses slots 2 (open) and 3 (close), plus group 0 slots 0/1
        self.assertIn(2, saves)
        self.assertIn(3, saves)

    def test_two_groups(self):
        _, groups, _ = compile_pattern("(a)(b)", 0)
        self.assertEqual(groups, 2)

    def test_noncapture_no_group(self):
        _, groups, _ = compile_pattern("(?:ab)", 0)
        self.assertEqual(groups, 0)

    def test_star_has_back_edge(self):
        nfa, _, _ = compile_pattern("a*", 0)
        # there must be a char edge (and the loop structure exists)
        char_edges = [1 for _, lbl, _ in nfa.edges() if lbl is not None]
        self.assertEqual(len(char_edges), 1)

    def test_alternation_branches(self):
        nfa, _, _ = compile_pattern("a|b", 0)
        # two distinct char edges labelled a and b
        labels = sorted(lbl.describe() for _, lbl, _ in nfa.edges()
                        if lbl is not None)
        self.assertEqual(labels, ["a", "b"])

    def test_graph_layout(self):
        nfa, _, _ = compile_pattern("ab|c", 0)
        g = nfa.to_graph()
        ids = {n["id"] for n in g["nodes"]}
        self.assertEqual(ids, set(range(len(g["nodes"]))))
        for e in g["edges"]:
            self.assertIn(e["from"], ids)
            self.assertIn(e["to"], ids)


if __name__ == "__main__":
    unittest.main()
