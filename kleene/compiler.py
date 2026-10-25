"""Compile a regex AST to a Thompson NFA.

The produced NFA has epsilon edges and labelled char edges. Capture groups
are encoded by Save ops (slot 2*g = open, 2*g+1 = close); the whole match
is wrapped in group 0 (slots 0/1). Zero-width assertions are Assert ops.
"""

from . import ast as A
from .nfa import NFA


class Fragment:
    """A sub-NFA with a dangling start and accept state id."""

    def __init__(self, nfa, start, accept):
        self.nfa = nfa
        self.start = start
        self.accept = accept

    def patch(self, target):
        self.nfa.states[self.accept].add_epsilon(target)


class Compiler:
    def __init__(self, flags=0):
        self.flags = flags
        self.nfa = NFA()
        self.group_count = 0

    def state(self, note=""):
        sid = self.nfa.new_state(note)
        return sid, self.nfa.states[sid]

    def compile(self, root, group_count):
        self.group_count = group_count
        nfa = self.nfa
        inner = self.compile_node(root)
        # Wrap whole match in group 0: Save(0) -> inner -> Save(1) -> accept.
        s0, st0 = self.state("group 0 open")
        st0.ops.append(("save", 0))
        s1, st1 = self.state("group 0 close")
        st1.ops.append(("save", 1))
        end, endst = self.state("accept")
        endst.accept = True
        st0.add_epsilon(inner.start)
        inner.patch(s1)
        st1.add_epsilon(end)
        nfa.start = s0
        return nfa

    # ------------------------------------------------------------
    def compile_node(self, node):
        if isinstance(node, A.Char):
            s, st = self.state("char")
            a, _ = self.state()
            charset = node.charset
            if self.flags & 0x02:  # IGNORECASE
                charset = charset.fold_case()
            st.add_char(charset, a)
            return Fragment(self.nfa, s, a)
        if isinstance(node, A.Assertion):
            s, st = self.state(node.kind)
            st.ops.append(("assert", node.kind))
            a, _ = self.state()
            st.add_epsilon(a)
            return Fragment(self.nfa, s, a)
        if isinstance(node, A.Concat):
            parts = [self.compile_node(p) for p in node.parts]
            for left, right in zip(parts, parts[1:]):
                left.patch(right.start)
            return Fragment(self.nfa, parts[0].start, parts[-1].accept)
        if isinstance(node, A.Alt):
            options = [self.compile_node(o) for o in node.options]
            split, sp = self.state("split")
            end, _ = self.state()
            for frag in options:
                sp.add_epsilon(frag.start)   # order == priority
                frag.patch(end)
            return Fragment(self.nfa, split, end)
        if isinstance(node, A.Group):
            return self.compile_group(node)
        if isinstance(node, A.Repeat):
            return self.compile_repeat(node)
        raise TypeError(f"unknown node {node!r}")

    def compile_group(self, node):
        nfa = self.nfa
        inner = self.compile_node(node.child)
        open_id, open_st = self.state(f"group {node.index} open")
        open_st.ops.append(("save", node.index * 2))
        close_id, close_st = self.state(f"group {node.index} close")
        close_st.ops.append(("save", node.index * 2 + 1))
        end, _ = self.state()
        open_st.add_epsilon(inner.start)
        inner.patch(close_id)
        close_st.add_epsilon(end)
        return Fragment(nfa, open_id, end)

    def compile_repeat(self, node):
        nfa = self.nfa
        pieces = []
        for _ in range(node.minimum):
            pieces.append(self.compile_node(node.child))
        if node.maximum is None:
            pieces.append(self.compile_star(node.child, node.lazy))
        else:
            for _ in range(node.maximum - node.minimum):
                pieces.append(self.compile_optional(node.child, node.lazy))
        if not pieces:
            s, st = self.state()
            a, _ = self.state()
            st.add_epsilon(a)
            return Fragment(nfa, s, a)
        for left, right in zip(pieces, pieces[1:]):
            left.patch(right.start)
        return Fragment(nfa, pieces[0].start, pieces[-1].accept)

    def compile_star(self, child, lazy):
        nfa = self.nfa
        body = self.compile_node(child)
        split, sp = self.state("split *")
        end, _ = self.state()
        if lazy:
            sp.add_epsilon(end)
            sp.add_epsilon(body.start)
        else:
            sp.add_epsilon(body.start)
            sp.add_epsilon(end)
        body.patch(split)
        return Fragment(nfa, split, end)

    def compile_optional(self, child, lazy):
        nfa = self.nfa
        body = self.compile_node(child)
        split, sp = self.state("split ?")
        end, _ = self.state()
        if lazy:
            sp.add_epsilon(end)
            sp.add_epsilon(body.start)
        else:
            sp.add_epsilon(body.start)
            sp.add_epsilon(end)
        body.patch(end)
        return Fragment(nfa, split, end)


def compile_pattern(pattern: str, flags=0):
    tree, group_count = A.parse(pattern, flags)
    nfa = Compiler(flags).compile(tree, group_count)
    return nfa, group_count, tree
