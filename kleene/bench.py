"""Micro-benchmarks comparing Kleene's linear-time engine with Python re.

Two scenarios are measured:

* ``pathological``  - ``(a+)+b`` over ``a``*N, a classic catastrophic
  backtracking pattern.  A backtracking engine is exponential here; Kleene
  is linear.  Python's ``re`` is intentionally capped at a small size so
  the benchmark never hangs.
* ``ordinary``      - ``\\d+`` over random digits, a linear pattern in both
  engines, shown as a fair baseline.

The reported times are the median of a few runs in milliseconds.  This is a
small teaching tool, not a rigorous benchmark suite.
"""

import random
import time

try:
    import re
except ImportError:  # pragma: no cover
    re = None

from .engine import Regex

PATHOLOGICAL = "(a+)+b"
ORDINARY = r"\d+"


def _median_ms(fn, repeat=3):
    best = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        dt = (time.perf_counter() - t0) * 1000.0
        best = dt if best is None else min(best, dt)
    return round(best, 4)


def _re_safe(pattern, text, cap=20):
    """Run re only when the input is small enough not to blow up.

    The pathological case is exponential; on a slow or throttled CI runner
    even n=24 can take many seconds, so we cap at n=20 (about 2**20 paths),
    which still shows the exponential curve clearly.
    """
    if re is None or len(text) > cap:
        return None
    try:
        return _median_ms(lambda: re.search(pattern, text), repeat=1)
    except Exception:
        return None


def bench_pathological(sizes=None):
    sizes = sizes or [10, 15, 20, 24, 30, 50, 75, 100, 200, 400, 800]
    rows = []
    for n in sizes:
        text = "a" * n
        rx = Regex(PATHOLOGICAL)
        # include compilation of the NFA once, then matching
        kleene_ms = _median_ms(lambda: Regex(PATHOLOGICAL).search(text))
        re_ms = _re_safe(PATHOLOGICAL, text)
        rows.append({"n": n, "kleene_ms": kleene_ms, "re_ms": re_ms})
    return {"pattern": PATHOLOGICAL, "kind": "pathological", "rows": rows,
            "note": "re is omitted beyond n=20 because it is exponential "
                    "and would hang."}


def bench_ordinary(sizes=None):
    sizes = sizes or [100, 500, 1000, 5000, 10000, 25000, 50000, 100000]
    rows = []
    rng = random.Random(42)
    for n in sizes:
        text = "".join(rng.choice("0123456789 ") for _ in range(n))
        kleene_ms = _median_ms(lambda: Regex(ORDINARY).findall(text))
        re_ms = None
        if re is not None:
            re_ms = _median_ms(lambda: re.findall(ORDINARY, text))
        rows.append({"n": n, "kleene_ms": kleene_ms, "re_ms": re_ms})
    return {"pattern": ORDINARY, "kind": "ordinary", "rows": rows}


def bench_all():
    return {"pathological": bench_pathological(),
            "ordinary": bench_ordinary()}


def _format_table(result):
    print(f"\nPattern: {result['pattern']}  ({result['kind']})")
    print(f"{'n':>8}  {'kleene(ms)':>12}  {'re(ms)':>12}")
    for row in result["rows"]:
        ref = "—" if row["re_ms"] is None else f"{row['re_ms']:.4f}"
        print(f"{row['n']:>8}  {row['kleene_ms']:>12.4f}  {ref:>12}")
    if result.get("note"):
        print(result["note"])


def main():
    _format_table(bench_pathological())
    _format_table(bench_ordinary())


if __name__ == "__main__":
    main()
