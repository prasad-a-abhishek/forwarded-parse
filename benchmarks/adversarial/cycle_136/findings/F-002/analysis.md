# F-002: Cross-cycle oracle does not resolve quoted-string backslash escapes

## Severity: INFO (harness bug, not a library bug)

## Surface(s)
- `harness_cross_cycle` (1709 oracle mismatches attributed to this gap)

## Smallest reproducer
```
INPUT:  for="a\"b"
parser: for=['a"b']            # RFC 7230 §3.2.6: \" → "
oracle: ['a\\"b']              # naive: strips quotes, leaves backslash literal
```

## Root cause

`benchmarks/adversarial/cycle_136/harness_cross_cycle.py` implements an
independent reference (the "oracle") using regex to extract `for=` values
without doing backslash-escape resolution. The real parser does resolve
RFC 7230 §3.2.6 escapes. For inputs where the naive regex and the real
parser disagree, the harness flags an "oracle mismatch" — but the
mismatch is the harness, not the library.

## Why this is INFO, not HIGH

1. The library is correct. The oracle is meant to be a "naive" reference (per
   its docstring "intentionally naive"), but at corpus scale (~250 000
   iterations) the gap produces 1709 false-positive mismatches that drown
   out any real library issue.
2. The cycle_136 CORPUS_RUN report (T3) explicitly classifies this as
   `ORACLE_HARNESS_BUG` — the bug is in the test harness, not the shipped
   product.
3. No library fix is needed; the library's escape handling is verified by
   the dedicated `harness_quote_handling` surface (which also covers
   `parse_main` and ran clean at scale).

## Fix direction

Two options for the next-cycle builder (T5):
- (a) **Implement RFC 7230 §3.2.6 escape resolution in the oracle.** Best
  fidelity — the oracle becomes a real reference and the surface becomes a
  strict cross-check. ~20 lines of Python.
- (b) **Loosen the harness assertion.** Compare the oracle only on UNQUOTED
  `for=` values (a one-line filter), treating the oracle as a sanity check
  for the simple case. ~2 lines of Python.

(a) is preferred for future cycles; (b) is the minimum to silence this
finding without losing coverage.

## Scale evidence
- 1709 hits out of ~250 000 iterations on `harness_cross_cycle` (~0.68 %).
  This is the dominant source of "oracle_mismatch_count" in the
  AGGREGATE_STATS.json — without this bug the surface would report CLEAN.
- The library itself is CLEAN: `harness_parse_main`, `harness_type_errors`,
  and `harness_obfuscated` ran 250 000 iterations each with zero mismatches.