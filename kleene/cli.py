"""Command-line interface for Kleene."""

import argparse
import json
import sys

from . import __version__
from .ast import ParseError
from .bench import bench_all
from .engine import DOTALL, MULTILINE, IGNORECASE, Regex

FLAG_MAP = {"i": IGNORECASE, "s": DOTALL, "m": MULTILINE}


def _flags(value):
    flags = 0
    for ch in value:
        if ch in FLAG_MAP:
            flags |= FLAG_MAP[ch]
    return flags


def _read_text(argument):
    """Read text from an argument that is either a literal or a file path."""
    if argument is None:
        return sys.stdin.read()
    try:
        with open(argument, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, FileNotFoundError):
        return argument


def _match_dicts(rx, text):
    out = []
    for m in rx.finditer(text):
        d = {"match": m.group(0), "span": list(m.span(0)),
             "groups": m.groups(), "groupdict": m.to_dict()}
        out.append(d)
    return out


def _print(value, as_json):
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="kleene",
        description="Kleene: a linear-time regex engine (NFA -> Pike VM / "
                    "DFA) with a visual workbench.")
    parser.add_argument("--version", action="version",
                        version=f"kleene {__version__}")
    parser.add_argument("-f", "--flags", default="",
                        help="flags, any of i (ignore case), s (dotall), "
                             "m (multiline)")
    sub = parser.add_subparsers(dest="command", required=True)

    # -f may also be given after the subcommand; SUPPRESS keeps the top-level
    # value when it is not repeated.
    flag_parent = argparse.ArgumentParser(add_help=False)
    flag_parent.add_argument("-f", "--flags",
                             default=argparse.SUPPRESS,
                             help="flags, any of i/s/m")

    def add_match(p, full=False):
        p.add_argument("pattern")
        p.add_argument("source", nargs="?",
                       help="literal text or path to a file; default stdin")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("match", parents=[flag_parent],
                       help="find all non-overlapping matches")
    add_match(p)

    p = sub.add_parser("fullmatch", parents=[flag_parent],
                       help="check whether the whole text matches")
    add_match(p)

    p = sub.add_parser("findall", parents=[flag_parent],
                       help="list matched substrings / groups")
    add_match(p)

    p = sub.add_parser("groups", parents=[flag_parent],
                       help="show capture groups for every match")
    add_match(p)

    p = sub.add_parser("split", parents=[flag_parent],
                       help="split text on matches")
    add_match(p)

    p = sub.add_parser("sub", parents=[flag_parent],
                       help="substitute matches with a replacement")
    p.add_argument("pattern")
    p.add_argument("replacement")
    p.add_argument("source", nargs="?")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("explain", parents=[flag_parent],
                       help="AST, NFA/DFA statistics and structure")
    p.add_argument("pattern")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("trace", parents=[flag_parent],
                       help="step-by-step NFA execution")
    p.add_argument("pattern")
    p.add_argument("source", nargs="?")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("nfa", parents=[flag_parent],
                       help="emit the NFA graph as JSON")
    p.add_argument("pattern")

    p = sub.add_parser("dfa", parents=[flag_parent],
                       help="emit the DFA graph as JSON")
    p.add_argument("pattern")

    p = sub.add_parser("bench", help="linear-time vs Python re benchmarks")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("serve", help="launch the visual workbench")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8856)

    return parser


def _compile(args):
    flags = _flags(getattr(args, "flags", ""))
    return Regex(args.pattern, flags)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "serve":
        from .server import serve
        serve(args.host, args.port)
        return 0

    if cmd == "bench":
        data = bench_all()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            from .bench import _format_table
            _format_table(data["pathological"])
            _format_table(data["ordinary"])
        return 0

    if cmd == "explain":
        try:
            rx = Regex(args.pattern, _flags(args.flags))
        except ParseError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        data = rx.explain()
        _print(data if args.json else _human_explain(data), args.json)
        return 0

    if cmd == "nfa":
        rx = Regex(args.pattern, _flags(args.flags))
        print(json.dumps(rx.nfa_graph(), ensure_ascii=False))
        return 0

    if cmd == "dfa":
        rx = Regex(args.pattern, _flags(args.flags))
        graph = rx.dfa_graph()
        if graph is None:
            print(json.dumps({"error": "pattern contains assertions; "
                                       "DFA path is not supported"},
                             ensure_ascii=False))
            return 1
        print(json.dumps(graph, ensure_ascii=False))
        return 0

    # text-based commands
    try:
        rx = _compile(args)
    except ParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = _read_text(getattr(args, "source", None))

    if cmd == "match":
        matches = _match_dicts(rx, text)
        if args.json:
            print(json.dumps(matches, ensure_ascii=False, indent=2))
        else:
            for d in matches:
                print(f"{d['span'][0]}:{d['span'][1]}  {d['match']!r}")
        return 0

    if cmd == "fullmatch":
        m = rx.fullmatch(text.rstrip("\n"))
        ok = m is not None
        if args.json:
            print(json.dumps({"fullmatch": ok,
                              "match": m.group(0) if m else None},
                             ensure_ascii=False))
        else:
            print("true" if ok else "false")
        return 0 if ok else 1

    if cmd == "findall":
        result = rx.findall(text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for item in result:
                print(item if not isinstance(item, tuple) else
                      " / ".join("" if x is None else x for x in item))
        return 0

    if cmd == "groups":
        matches = _match_dicts(rx, text)
        if args.json:
            print(json.dumps(matches, ensure_ascii=False, indent=2))
        else:
            for d in matches:
                print(f"{d['span']}  {d['groups']}")
        return 0

    if cmd == "split":
        result = rx.split(text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for part in result:
                print(part)
        return 0

    if cmd == "sub":
        result = rx.sub(args.replacement, text)
        if args.json:
            print(json.dumps({"result": result}, ensure_ascii=False))
        else:
            sys.stdout.write(result)
        return 0

    if cmd == "trace":
        frames = rx.trace(text)
        if args.json:
            print(json.dumps(frames, ensure_ascii=False, indent=2))
        else:
            for fr in frames:
                ch = fr["char"] if fr["char"] is not None else "EOF"
                print(f"pos={fr['position']:>3} char={ch!r:>4} "
                      f"active={fr['active']} accepts={fr['accepted_ends']}")
        return 0

    return 0


def _human_explain(data):
    lines = [
        f"pattern   : {data['pattern']}",
        f"groups    : {data['groups']}",
        f"NFA states: {data['states']}",
        f"edges     : {data['edges']} ({data['epsilon']} epsilon)",
        f"DFA path  : {'yes' if data['dfa_supported'] else 'no (VM only)'}",
        "AST       :",
    ]
    lines.append(_render_ast(data["ast"], 1))
    return "\n".join(lines)


def _render_ast(node, depth):
    pad = "  " * depth
    t = node["type"]
    if t == "char":
        return f"{pad}char {node['class']}"
    if t == "assert":
        return f"{pad}assert {node['kind']}"
    if t == "concat":
        body = "\n".join(_render_ast(p, depth + 1) for p in node["parts"])
        return f"{pad}concat\n{body}"
    if t == "alt":
        body = "\n".join(_render_ast(o, depth + 1) for o in node["options"])
        return f"{pad}alt\n{body}"
    if t == "repeat":
        mx = "" if node["max"] is None else f",{node['max']}"
        kind = "lazy" if node["lazy"] else "greedy"
        body = _render_ast(node["child"], depth + 1)
        return f"{pad}repeat {{{node['min']}{mx}}} {kind}\n{body}"
    if t == "group":
        body = _render_ast(node["child"], depth + 1)
        return f"{pad}group {node['index']}\n{body}"
    return f"{pad}{t}"


if __name__ == "__main__":
    sys.exit(main())
