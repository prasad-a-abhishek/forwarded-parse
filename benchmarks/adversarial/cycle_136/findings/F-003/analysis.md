# F-003: random_quoted_value() may emit bodies ending in bare backslash

## Severity: INFO (harness bug, not a library bug)

## Surface(s)
- `harness_quote_handling` (1843 parser-rejection events attributed to this
  generator gap)

## Smallest reproducer
```
INPUT:  "abc\"
parser: raises ForwardedParseError("malformed forwarded-pair: '\"abc\\\"' (expected token=value)")
```

## Root cause

`benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value()`
generates quoted-string bodies by concatenating random tokens and escape
sequences. The closing character may be a bare backslash (length-1 sequence
that is just `\`). When wrapped in `"..."`, the result is `"...\"`, which
has an unescaped `\` immediately before the closing `"` — a malformed
quoted-string per RFC 7230 §3.2.6 (only `\"` and `\\` are recognised as
escape pairs; a bare trailing `\` is invalid).

The harness docstring claims bodies are "always well-formed" but does not
enforce this for the trailing character.

## Why this is INFO, not HIGH

1. The library is correct. RFC 7230 §3.2.6 is unambiguous on this point:
   only `\"` and `\\` are escapes. The parser's `unterminated quoted-string`
   error is the spec-correct response.
2. The cycle_136 CORPUS_RUN report (T3) explicitly classifies this as
   `RANDOM_GENERATOR_HARNESS_BUG` — the bug is in the test harness's input
   generator, not the shipped product.
3. The library's quote handling is verified clean at scale by
   `harness_quote_handling` ITSELF (which surfaces this gap) and the
   `harness_parse_main` and `harness_obfuscated` surfaces.

## Fix direction

In `benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value()`,
either:
- (a) After generating the body, check `if body.endswith('\\')` and either
  strip the trailing backslash or append one more "safe" character.
- (b) Reject the trailing-backslash case in the generator and roll a new
  character.

(a) is preferred (smaller diff). The fix is ~3 lines.

## Scale evidence
- 1843 parser-rejection events out of ~250 000 iterations on
  `harness_quote_handling` (~0.74 %). All 1843 are caused by this single
  generator gap.
- The library itself is CLEAN — every parser rejection in this surface is
  spec-compliant.