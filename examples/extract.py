"""Kleene example: extract structured fields from a log line.

Run with:  python examples/extract.py

Uses the Kleene engine as a library (no third-party dependencies) to pull
out timestamps, IP addresses, e-mails and HTTP status codes from a small
log, then shows a substitution and a split.
"""

from kleene import Regex

SAMPLE = (
    "2026-10-25 09:14:02 10.0.0.1 user=alice@example.com GET /index 200\n"
    "2026-10-25 09:15:11 10.0.0.4 user=bob@corp.io POST /api/login 401\n"
)

PATTERNS = {
    "timestamp": r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})",
    "ip": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "status": r"\b\d{3}\b",
}


def main():
    for name, pat in PATTERNS.items():
        rx = Regex(pat)
        values = [m.group(0) for m in rx.finditer(SAMPLE)]
        print(f"{name:9}: {values}")

    print("\nCapture groups for the first timestamp:")
    rx = Regex(PATTERNS["timestamp"])
    m = rx.search(SAMPLE)
    print("  date =", "/".join(m.groups()[:3]))
    print("  time =", ":".join(m.groups()[3:]))

    print("\nRedact e-mails with sub():")
    redacted = Regex(PATTERNS["email"]).sub("<redacted>", SAMPLE)
    print("  " + redacted.replace("\n", "\n  ").rstrip())

    print("\nSplit a command string on whitespace:")
    print("  ", Regex(r"\s+").split("GET /index.html 200"))


if __name__ == "__main__":
    main()
