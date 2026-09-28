# F-004: CLI emits empty stdout for inputs that reduce to empty formatted form

## Severity: HIGH (linked to F-001 — fixed by F-001 remediation)

## Surface(s)
- `harness_cli_parse` (44/44 mismatches on "non-empty input must produce
  non-empty stdout on exit 0" assertion)

## Smallest reproducer
```
$ echo 'foo=bar' | python -m forwarded_parse
$ echo $?
0
```
stdout is empty. Exit code is 0. The CLI's documented contract (cli.py
docstring §Exit codes) says `0 — success (including empty input → empty
output)` — but does NOT explicitly carve out the case where the input parses
non-empty yet serialises to empty. The harness asserts that non-empty input
must produce non-empty stdout on exit 0; this contract is violated.

## Root cause

Same as F-001. The CLI calls `format(parsed)` then `if out: write`. For
inputs whose parsed form has no recognised keys, `format()` returns `''`
and the `if out:` guard suppresses the write — leaving exit 0 with no
output.

## Why this is the same bug as F-001, not a separate one

1. The CLI's behaviour here is a correct response to F-001's parser bug. If
   the parser correctly drops all-unknown elements, `parse('foo=bar')` would
   yield `Forwarded(elements=())` and `format()` would return `''` for a
   legitimate reason (empty input on the round-trip).
2. The harness's "non-empty input must produce non-empty stdout" assertion is
   the contract the cycle_136 spec implicitly relies on (a CLI that swallows
   output for valid input is useless for log processing pipelines).
3. **No independent library fix is needed** — fixing F-001 eliminates F-004
   as a side effect.

## Fix direction

Fix F-001 first; then either:
- (a) Leave the CLI as-is. The `if out:` guard is correct: an empty-formatted
  result means "no header content" and the caller can detect that via exit 0
  + empty stdout. Document this in the CLI docstring.
- (b) Replace the `if out:` guard with an unconditional write (always emit
  `\n` for empty) so empty stdout never escapes. This makes the CLI's
  behaviour more consistent with POSIX text-tool conventions ("if I ran it,
  it wrote *something*").

## Scale evidence
- 44 hits in `harness_cli_parse` (out of ~250 000 iterations); only triggers
  when the harness generates an input where ALL pairs are unknown keys.
- Same root cause as F-001 — fixing the parser drops the count to 0.