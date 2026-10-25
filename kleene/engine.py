"""High-level regex engine: compile, match, find, split and substitute."""

from . import ast as A
from .compiler import compile_pattern
from .dfa import DFA, DFAUnsupported
from .vm import VM, SEARCH, MATCH, FULLMATCH, Match

# Flag bits mirror Python's re where easy.
IGNORECASE = 0x02
DOTALL = 0x10
MULTILINE = 0x08


class Regex:
    def __init__(self, pattern: str, flags=0):
        self.pattern = pattern
        self.flags = flags
        self.nfa, self.group_count, self.tree = compile_pattern(pattern, flags)
        self.vm = VM(self.nfa, self.group_count, flags, pattern)
        try:
            self.dfa = DFA(self.nfa)
        except DFAUnsupported:
            self.dfa = None

    # ------------------------------------------------- queries ----
    def search(self, text, start=0):
        caps = self.vm.run(text, start, SEARCH)
        return Match(self.pattern, text, caps) if caps else None

    def match(self, text, start=0):
        caps = self.vm.run(text, start, MATCH)
        return Match(self.pattern, text, caps) if caps else None

    def fullmatch(self, text):
        caps = self.vm.run(text, 0, FULLMATCH)
        return Match(self.pattern, text, caps) if caps else None

    def finditer(self, text):
        return self.vm.find_iter(text, SEARCH)

    def findall(self, text):
        out = []
        for m in self.finditer(text):
            if self.group_count == 0:
                out.append(m.group(0))
            elif self.group_count == 1:
                out.append(m.group(1) if m.group(1) is not None else "")
            else:
                out.append(tuple(m.group(g) for g in
                                 range(1, self.group_count + 1)))
        return out

    def split(self, text):
        out = []
        last = 0
        for m in self.finditer(text):
            s, e = m.span(0)
            if s == e:
                # empty match: split point between chars
                if s > last:
                    out.append(text[last:s])
                last = e
                continue
            out.append(text[last:s])
            for g in range(1, self.group_count + 1):
                out.append(m.group(g))
            last = e
        out.append(text[last:])
        return out

    def sub(self, repl, text):
        out = []
        last = 0
        for m in self.finditer(text):
            s, e = m.span(0)
            out.append(text[last:s])
            if callable(repl):
                out.append(repl(m))
            else:
                out.append(self._expand(repl, m))
            last = e
            if e == s:
                if e < len(text):
                    out.append(text[e])
                    last = e + 1
        out.append(text[last:])
        return "".join(out)

    @staticmethod
    def _expand(template, m):
        out = []
        i = 0
        n = len(template)
        while i < n:
            ch = template[i]
            if ch == "\\" and i + 1 < n:
                nxt = template[i + 1]
                # \g<number> / \g<name> style reference
                if nxt == "g" and i + 2 < n and template[i + 2] == "<":
                    close = template.find(">", i + 3)
                    if close != -1:
                        key = template[i + 3:close]
                        try:
                            out.append(m.group(int(key)) or "")
                        except (ValueError, IndexError):
                            out.append(m.groupdict().get(key) or "")
                        i = close + 1
                        continue
                if nxt.isdigit():
                    out.append(m.group(int(nxt)) or "")
                    i += 2
                    continue
                out.append(nxt)
                i += 2
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    # ------------------------------------------------- inspection ----
    def explain(self):
        return {
            "pattern": self.pattern,
            "groups": self.group_count,
            "states": len(self.nfa.states),
            "edges": sum(len(st.edges) for st in self.nfa.states),
            "epsilon": sum(1 for _, lbl, _ in self.nfa.edges() if lbl is None),
            "ast": ast_to_dict(self.tree),
            "dfa_supported": self.dfa is not None,
        }

    def nfa_graph(self):
        return self.nfa.to_graph()

    def dfa_graph(self):
        return self.dfa.build_graph() if self.dfa else None

    def trace(self, text):
        return self.vm.trace(text, 0)


def compile(pattern, flags=0):
    return Regex(pattern, flags)


def ast_to_dict(node):
    if isinstance(node, A.Char):
        return {"type": "char", "class": node.charset.describe()}
    if isinstance(node, A.Assertion):
        return {"type": "assert", "kind": node.kind}
    if isinstance(node, A.Concat):
        return {"type": "concat", "parts": [ast_to_dict(p) for p in node.parts]}
    if isinstance(node, A.Alt):
        return {"type": "alt",
                "options": [ast_to_dict(o) for o in node.options]}
    if isinstance(node, A.Repeat):
        return {"type": "repeat", "min": node.minimum, "max": node.maximum,
                "lazy": node.lazy, "child": ast_to_dict(node.child)}
    if isinstance(node, A.Group):
        return {"type": "group", "index": node.index,
                "child": ast_to_dict(node.child)}
    return {"type": "unknown"}
