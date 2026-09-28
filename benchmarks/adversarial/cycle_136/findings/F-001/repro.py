#!/usr/bin/env python3
"""F-001: Minimal reproducer for idempotence violation on unknown-key elements.

Smallest input that triggers the bug: a single forwarded-pair whose name is not
one of {for, by, host, proto}. The parser accepts it (per RFC 7239 §4 extension
rule), but stores an empty element (for_=[], by=None, host=None, proto=None).
`format()` then serialises that element to ''. Re-parsing '' yields a Forwarded
with elements=() — an empty list — breaking AC7's round-trip idempotence property
(format(parse(h)) == format(parse(format(parse(h))))).
"""
import sys
sys.path.insert(0, "src")
from forwarded_parse import parse, format

# Smallest trigger — single unknown-pair element
INPUT = "foo=bar"

p1 = parse(INPUT)
f1 = format(p1)
p2 = parse(f1)
f2 = format(p2)

print(f"INPUT:                {INPUT!r}")
print(f"parse(INPUT):         {p1.to_dict()}")
print(f"format(parse(INPUT)): {f1!r}")
print(f"parse(format(...)):   {p2.to_dict()}")
print(f"format(...) again:    {f2!r}")
print()

# Demonstrate the failure
assert f1 == f2, f"idempotence: {f1!r} != {f2!r}"
print("IDEMPOTENT: True")
# But the first parse is NOT what the user fed in — the input 'foo=bar' vanished:
assert p1.to_dict() != {"elements": []}, "first parse should preserve the unknown pair"
print("BUT: parse() returned a non-empty element that format() then dropped.")
print("BUG CONFIRMED: a header containing only unknown forward-pair names becomes 'no header' after round-trip.")