#!/usr/bin/env python3
"""F-002: Minimal reproducer for the cross-cycle oracle's escape-resolution gap.

The harness's "oracle" (benchmarks/adversarial/cycle_136/harness_cross_cycle.py,
function `_oracle_extract_for_values`) is a regex-based reference implementation
used as a sanity-check comparator. It strips surrounding quotes from a `for=`
value but does NOT resolve RFC 7230 §3.2.6 backslash escapes. The real parser
DOES resolve escapes. For inputs where the two paths produce different
`for=`-lists, the harness flags an "oracle mismatch" — but the mismatch is
in the oracle, not the parser.

This script reproduces the smallest case where oracle and parser disagree.
"""
import re, sys
sys.path.insert(0, "src")
from forwarded_parse import parse

# Approximation of the harness oracle's `_oracle_extract_for_values`
def oracle_extract(s: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r'for=(\"[^\"]*\"|[^;,]+)', s):
        v = m.group(1)
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]  # naive — does NOT resolve \" or \\
        out.append(v)
    return out

# Smallest trigger: a quoted for= value containing an escaped double-quote.
# RFC 7230 §3.2.6: \" → " inside a quoted-string.
INPUT = r'for="a\"b"'

parsed = parse(INPUT)
parser_for = list(parsed.elements[0].for_) if parsed.elements else []
oracle_for = oracle_extract(INPUT)

print(f"INPUT:        {INPUT!r}")
print(f"parser for[]: {parser_for}")
print(f"oracle for[]: {oracle_for}")
print(f"agree:        {parser_for == oracle_for}")
print()

assert parser_for != oracle_for, "should disagree"
print("BUG CONFIRMED: oracle naively strips quotes; parser resolves RFC 7230 §3.2.6 escapes.")