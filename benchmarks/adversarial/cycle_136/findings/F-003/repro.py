#!/usr/bin/env python3
"""F-003: Minimal reproducer for random_quoted_value() trailing-backslash bug.

The harness's generator (benchmarks/adversarial/cycle_136/_harness_common.py,
function `random_quoted_value`) is documented as producing "always
well-formed" quoted-string bodies. But the body generator may emit a
trailing bare backslash (e.g. `abc\`), which when wrapped in `"..."` becomes
`"abc\"` — a malformed quoted-string (closing quote preceded by an unescaped
backslash, per RFC 7230 §3.2.6 only `\"` and `\\` are escapes).

The PARSER correctly rejects this as `malformed forwarded-pair` (or
`unterminated quoted-string` for the quoted-pair case). The bug is in the
generator, not the parser.

This script reproduces the smallest harness-generated input that triggers
the bug.
"""
import sys
sys.path.insert(0, "src")
from forwarded_parse import parse

# Smallest trigger: a body ending in a single bare backslash, wrapped in
# double-quotes — i.e. an unterminated quoted-string per RFC 7230 §3.2.6.
INPUT = '"abc\\"'

print(f"INPUT: {INPUT!r}")
try:
    p = parse(INPUT)
    print(f"parser accepted (BUG): {p.to_dict()}")
except Exception as e:
    print(f"parser correctly raised: {type(e).__name__}: {e}")
print()

# The CORRECTNESS is on the parser side. The bug is that the harness
# generates inputs that are SUPPOSED to be well-formed but are not.
# The fix is in _harness_common.py:random_quoted_value, NOT in the parser.
print("BUG LOCATION: benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value")
print("BUG CLASS:    random-generator produces malformed inputs the parser (correctly) rejects")
print("LIBRARY:      CORRECT (RFC 7230 §3.2.6: only \\\" and \\\\ are escapes; bare trailing \\ is invalid)")