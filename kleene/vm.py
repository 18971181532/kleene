"""Pike-style threaded NFA simulator.

Linear in the input length (each position expands the closure once).
Threads are kept in a priority-ordered list (the order in which
epsilon edges are emitted), which reproduces greedy/lazy preference.
Each thread carries capture slots.
"""

from .charset import is_word

SEARCH = "search"
MATCH = "match"
FULLMATCH = "fullmatch"


class Match:
    def __init__(self, pattern, text, caps):
        self.pattern = pattern
        self.text = text
        self.caps = caps

    def span(self, group=0):
        return (self.caps[group * 2], self.caps[group * 2 + 1])

    def start(self, group=0):
        return self.caps[group * 2]

    def end(self, group=0):
        return self.caps[group * 2 + 1]

    def group(self, g=0):
        lo, hi = self.span(g)
        if lo < 0 or hi < 0:
            return None
        return self.text[lo:hi]

    def groups(self):
        return tuple(self.group(g + 1)
                     for g in range((len(self.caps) - 2) // 2))

    def to_dict(self):
        return {
            "match": self.group(0),
            "start": self.start(0),
            "end": self.end(0),
            "groups": [
                {"index": g + 1, "value": self.group(g + 1),
                 "span": self.span(g + 1)}
                for g in range((len(self.caps) - 2) // 2)
            ],
        }


class VM:
    def __init__(self, nfa, group_count, flags=0, pattern=""):
        self.nfa = nfa
        self.group_count = group_count
        self.flags = flags
        self.multiline = bool(flags & 0x08)
        self.pattern = pattern
        self.slots = 2 * (group_count + 1)

    # ------------------------------------------------- assertions ----
    def _check_assert(self, kind, pos, text):
        n = len(text)
        if kind == "start":
            if pos == 0:
                return True
            return self.multiline and pos <= n and text[pos - 1] == "\n"
        if kind == "end":
            if pos == n:
                return True
            return self.multiline and pos < n and text[pos] == "\n"
        if kind in ("boundary", "not_boundary"):
            before = is_word(text[pos - 1]) if pos - 1 >= 0 else False
            at = is_word(text[pos]) if pos < n else False
            b = before != at
            return b if kind == "boundary" else not b
        return True

    def _has_char_edge(self, sid):
        return any(lbl is not None for lbl, _ in self.nfa.states[sid].edges)

    def add_thread(self, ordered, seen, sid, caps, pos, text):
        if sid in seen:
            return
        st = self.nfa.states[sid]
        for op, val in st.ops:
            if op == "save":
                caps[val] = pos
            elif op == "assert":
                if not self._check_assert(val, pos, text):
                    return
        seen.add(sid)
        ordered.append((sid, caps))
        if st.accept:
            return
        for lbl, tgt in st.edges:
            if lbl is None:
                self.add_thread(ordered, seen, tgt, caps.copy(), pos, text)

    def _fresh(self):
        return [-1] * self.slots

    def _closure(self, seeds, pos, text):
        ordered, seen = [], set()
        for sid, caps in seeds:
            self.add_thread(ordered, seen, sid, caps, pos, text)
        return ordered

    # --------------------------------------------------- run ----
    def run(self, text, start=0, mode=SEARCH, non_empty=False):
        """Leftmost match caps at/after `start`, or None.

        non_empty=True skips zero-width matches (used to find the non-empty
        match adjacent to an empty one), while preserving greedy/lazy
        priority so an inner greedy quantifier still matches as long as it
        can.

        Leftmost semantics: every start position is searched concurrently.
        A match is held as a candidate keyed by the *smallest* starting
        position that reaches an accept. The candidate is finalised only
        once (a) no thread from an earlier start is still alive that could
        produce a more-leftmost match, and (b) no higher-priority thread of
        the same start is still able to extend a greedy match. At end of
        input, threads still waiting for a character cannot match, so the
        smallest-start accept already seen wins.
        """
        n = len(text)
        anchored = mode in (MATCH, FULLMATCH)
        ordered = self._closure([(self.nfa.start, self._fresh())],
                                start, text)
        pos = start
        candidate = None

        def is_accept(sid, caps):
            return self.nfa.states[sid].accept and \
                (not non_empty or caps[1] > caps[0])

        while pos <= n:
            # collect accept threads, honouring ordered priority
            accepts = [(idx, caps) for idx, (sid, caps) in enumerate(ordered)
                       if is_accept(sid, caps)]
            if accepts:
                s_min = min(caps[0] for _, caps in accepts)
                # highest-priority accept for the smallest start
                candidate = next(caps for _, caps in accepts
                                 if caps[0] == s_min)

            if candidate is not None:
                cs = candidate[0]
                earlier = [t for t in ordered if t[1][0] < cs]
                # index of the candidate's accept in the current closure
                cur_idx = next((idx for idx, (sid, caps) in enumerate(ordered)
                                if is_accept(sid, caps) and caps[0] == cs),
                               None)
                if cur_idx is not None:
                    # higher-priority same-start threads that can extend the
                    # (greedy) match rather than stopping at the accept.
                    can_extend = any(caps[0] == cs and
                                     self._has_char_edge(sid)
                                     for sid, caps in ordered[:cur_idx])
                else:
                    # accept no longer on this position: any surviving
                    # same-start thread is a continuation path.
                    can_extend = any(caps[0] == cs and
                                     self._has_char_edge(sid)
                                     for sid, caps in ordered)
                if pos == n:
                    # No more input: any live thread that merely waits for a
                    # character cannot match. Finalise unless an earlier-start
                    # accept is reachable right here.
                    earlier_accept = any(
                        caps[0] < cs and self.nfa.states[sid].accept
                        for sid, caps in ordered)
                    if not earlier_accept:
                        out = self._qualify(candidate, mode, start, n)
                        if out is not None:
                            return out
                        candidate = None
                elif not earlier and not can_extend:
                    out = self._qualify(candidate, mode, start, n)
                    if out is not None:
                        return out
                    candidate = None

            if pos == n:
                return self._qualify(candidate, mode, start, n) \
                    if candidate is not None else None

            # consume one character.
            if candidate is not None:
                cs = candidate[0]
                cur_idx = next((idx for idx, (sid, caps) in enumerate(ordered)
                                if is_accept(sid, caps) and caps[0] == cs),
                               len(ordered))
                # propagate earlier-start searches and same-start threads that
                # outrank the candidate (greedy extension); prune the rest.
                src = [t for idx, t in enumerate(ordered)
                       if t[1][0] < cs or (t[1][0] == cs and idx < cur_idx)]
            else:
                src = ordered
            nxt, nseen = [], set()
            ch = text[pos]
            for sid, caps in src:
                for lbl, tgt in self.nfa.states[sid].edges:
                    if lbl is not None and lbl.match(ch):
                        self.add_thread(nxt, nseen, tgt, caps.copy(),
                                        pos + 1, text)
            if not anchored and candidate is None:
                self.add_thread(nxt, nseen, self.nfa.start, self._fresh(),
                                pos + 1, text)
            ordered = nxt
            pos += 1
        return None

    @staticmethod
    def _qualify(caps, mode, start, n):
        if caps is None:
            return None
        if mode == FULLMATCH:
            return caps if caps[1] == n else None
        if mode == MATCH:
            return caps if caps[0] == start else None
        return caps

    # --------------------------------------------------- finds ----
    def find_iter(self, text, mode=SEARCH):
        pos = 0
        while pos <= len(text):
            caps = self.run(text, pos, mode)
            if caps is None:
                return
            if caps[1] == caps[0]:
                yield Match(self.pattern, text, caps)
                nonempty = self.run(text, caps[0], mode, non_empty=True)
                if nonempty is not None and nonempty[0] == caps[0]:
                    yield Match(self.pattern, text, nonempty)
                    pos = nonempty[1]
                else:
                    pos = caps[0] + 1
            else:
                yield Match(self.pattern, text, caps)
                pos = caps[1]

    # --------------------------------------------------- trace ----
    def trace(self, text, start=0):
        """Active-state sets per position (for the workbench animation)."""
        n = len(text)
        frames = []
        ordered = self._closure([(self.nfa.start, self._fresh())],
                                start, text)
        pos = start
        while pos <= n:
            active = sorted(sid for sid, _ in ordered)
            accept_ends = sorted({c[1] for sid, c in ordered
                                  if c[1] >= 0 and self.nfa.states[sid].accept})
            frames.append({
                "position": pos,
                "active": active,
                "accepted_ends": accept_ends,
                "char": text[pos] if pos < n else None,
            })
            if pos == n:
                break
            nxt, nseen = [], set()
            ch = text[pos]
            for sid, caps in ordered:
                for lbl, tgt in self.nfa.states[sid].edges:
                    if lbl is not None and lbl.match(ch):
                        self.add_thread(nxt, nseen, tgt, caps.copy(),
                                        pos + 1, text)
            self.add_thread(nxt, nseen, self.nfa.start, self._fresh(),
                            pos + 1, text)
            ordered = nxt
            pos += 1
        return frames
