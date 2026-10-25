"""NFA to DFA subset construction (powerset construction).

The DFA is a capture-free fast path. It provides deterministic fullmatch /
prefix matching and a renderable graph; the search-with-capture path uses
the Pike VM. Patterns with zero-width assertions are rejected by the DFA
(engine falls back to the VM).
"""

from .nfa import layout_nodes


class DFAUnsupported(Exception):
    pass


class DFA:
    def __init__(self, nfa):
        self.nfa = nfa
        if any(op == "assert" for st in nfa.states for op, _ in st.ops):
            raise DFAUnsupported("DFA fast path does not support assertions")
        self._closure_cache = {}
        self._move_cache = {}
        self.start = self.closure(frozenset([nfa.start]))

    # ------------------------------------------------------------
    def closure(self, seeds):
        if seeds in self._closure_cache:
            return self._closure_cache[seeds]
        stack = list(seeds)
        seen = set(seeds)
        while stack:
            sid = stack.pop()
            for lbl, tgt in self.nfa.states[sid].edges:
                if lbl is None and tgt not in seen:
                    seen.add(tgt)
                    stack.append(tgt)
        out = frozenset(seen)
        self._closure_cache[seeds] = out
        return out

    def move(self, subset, ch):
        key = (subset, ch)
        if key in self._move_cache:
            return self._move_cache[key]
        nxt = set()
        for sid in subset:
            for lbl, tgt in self.nfa.states[sid].edges:
                if lbl is not None and lbl.match(ch):
                    nxt.add(tgt)
        out = self.closure(frozenset(nxt))
        self._move_cache[key] = out
        return out

    def accepts(self, subset):
        return any(self.nfa.states[sid].accept for sid in subset)

    # ------------------------------------------------ matcher ----
    def fullmatch(self, text):
        """True iff the whole text matches the pattern."""
        state = self.start
        for ch in text:
            state = self.move(state, ch)
            if not state:
                return False
        return self.accepts(state)

    def prefix_end(self, text):
        """Longest accepted prefix length (greedy match from the start),
        or -1 if no prefix matches."""
        state = self.start
        best = 0 if self.accepts(state) else -1
        for i, ch in enumerate(text, start=1):
            state = self.move(state, ch)
            if not state:
                break
            if self.accepts(state):
                best = i
        return best

    # ------------------------------------------------- graph ----
    def alphabet(self):
        """One representative (label, char) for each distinct char class."""
        reps = []
        seen = set()
        for st in self.nfa.states:
            for lbl, _ in st.edges:
                if lbl is None:
                    continue
                sig = lbl.describe()
                if sig in seen:
                    continue
                seen.add(sig)
                if lbl.ranges and not lbl.negated:
                    rep = chr(lbl.ranges[0][0])
                elif lbl.negated and lbl.ranges:
                    rep = self._rep_outside(lbl)
                else:
                    rep = "a"
                reps.append((sig, rep))
        return reps

    @staticmethod
    def _rep_outside(lbl):
        excluded = set()
        for lo, hi in lbl.ranges:
            for cp in range(lo, min(hi, lo + 256) + 1):
                excluded.add(cp)
        for cp in range(32, 127):
            if cp not in excluded:
                return chr(cp)
        return "a"

    def build_graph(self):
        alphabet = self.alphabet()
        index = {}
        order = []
        edges = []

        def get_id(subset):
            if subset not in index:
                index[subset] = len(order)
                order.append(subset)
            return index[subset]

        get_id(self.start)
        q = 0
        while q < len(order):
            subset = order[q]
            q += 1
            for label, rep in alphabet:
                tgt = self.move(subset, rep)
                if not tgt:
                    continue
                tid = get_id(tgt)
                edges.append({"from": index[subset], "to": tid,
                              "label": label, "epsilon": False})
        nodes = []
        for dfa_id, subset in enumerate(order):
            label = "{" + ",".join(str(s) for s in sorted(subset)) + "}"
            if len(label) > 14:
                label = label[:12] + "...}"
            nodes.append({"id": dfa_id, "x": 0, "y": 0,
                          "accept": self.accepts(subset),
                          "start": subset == self.start,
                          "note": label, "subset": sorted(subset)})
        layout_nodes(nodes, edges)
        return {"nodes": nodes, "edges": edges, "start": 0}
