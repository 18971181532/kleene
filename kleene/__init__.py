"""Kleene — a small, linear-time regular-expression engine and NFA/DFA
workbench.

Patterns are parsed to an AST, compiled to a Thompson NFA, and run by a
Pike-style threaded virtual machine (linear in the input length, with
capture groups and no catastrophic backtracking). The same NFA powers an
NFA-to-DFA subset construction and a live interactive workbench.
"""

__version__ = "0.1.0"

from .engine import Regex, compile  # noqa: E402,F401
from .ast import ParseError  # noqa: E402,F401

__all__ = ["Regex", "compile", "ParseError", "__version__"]
