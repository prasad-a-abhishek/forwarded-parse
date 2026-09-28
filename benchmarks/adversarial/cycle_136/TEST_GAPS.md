# Test gaps — cycle_136 / adv / 01

> Repository: `forwarded-parse` v0.1.0 (commit `d9417ba`)
> Date: 2026-09-28
> Source of truth: `tests/` (13 modules, 176 collected `def test_*`,
> 331 collected cases after parameter expansion per the build card)
> plus the SPEC.md `§9` acceptance criteria.

The existing test suite is **solid for canonical paths** but leaves
several stress / boundary scenarios uncovered. None of the gaps are
security defects; they are coverage gaps that the next-cycle
adversary work (T2 fuzz harnesses, T3 seed corpus) will fill.

## A. Stress / DoS-path gaps

| Gap | Suggested input | Why |
|---|---|---|
| 10 000-element chain | `'for=10.0.0.0, for=10.0.0.1, ..., for=10.0.0.9999'` | Not exercised by any current test; would catch a future O(n²) regression in `_split_top_level` |
| 1 MiB single token value | `'for=' + 'a' * 1_048_576` | Not exercised; would catch a future quadratic-concat regression |
| 1 000 000-element `for=` chain within one element | `';'.join(f'for=10.0.0.{i}' for i in range(1_000_000))` | Not exercised; ensures `_parse_pair` doesn't degrade |
| Deep obs-fold (10 000 CRLF+WSP sequences) | `'for=a' + '\r\n ' * 10_000 + 'for=b'` | Not exercised; ensures `unfold_obs_fold` doesn't degrade |

Manual probe run during this audit (`PYTHONPATH=src python3 -c ...`):

```
[OK] massive_10k: len=10000, elapsed=0.042s, rt_match=True
[OK] 1MiB_single_value: for_=len=1048576, elapsed=0.164s
[OK] 100k_for_chain: OK len=1
[OK] 100k_comma_chain: OK len=100000
[OK] deep_obs_fold: OK elements=1
[OK] 1M_value: 1M_value elapsed=0.153s
[OK] round_trip_stability_1k: rt_stable=True, len1=15888, len2=15888
```

All clean — but these timings belong in `tests/test_stress.py` so a
future regression is caught at CI time, not at audit time.

## B. Non-string / type-confusion gaps

Existing tests cover `parse(None)`, `parse(12345)`. The matrix below
is not exhaustive:

| Gap | Suggested input | Expected behaviour |
|---|---|---|
| `parse(b'bytes')` | bytes input | `ForwardedParseError("value must be str, got bytes")` — covered by probe, not by test |
| `parse(3.14)` | float input | same — covered by probe, not by test |
| `parse(object())` | arbitrary object | same — covered by probe, not by test |
| `parse([])` | list input | same — covered by probe, not by test |
| `format(None)` | None to format | `TypeError` — covered by `test_edge_format_non_forwarded_raises_type_error` ✓ |
| `format(b'bytes')` | bytes to format | `TypeError` — **not** covered |
| `format(12345)` | int to format | `TypeError` — **not** covered |
| `format([])` | list to format | `TypeError` — **not** covered |
| `normalize(None)` / `normalize("for=a")` | non-Forwarded | `TypeError` — covered for strings; not covered for bytes/int/list |

These are easy wins: one parametrized test with five inputs would
close the gap.

## C. Control-character / byte-class gaps

Existing `test_error_edge_cases.py` covers:
* `parse('for="example.com')` — unterminated quoted string
* `parse("for=192.0.2.43 space")` — invalid char in token
* `parse('for_192.0.2.43')` — missing `=`
* `parse('for=')` — empty value

Gaps:
* NUL byte in value: `parse('for=abc\x00def')` — raises `ForwardedParseError("invalid character '\\x00' in token value")` — covered by probe, not by test
* Bare `\r\n` (no obs-fold context): `parse('\r\n')` — raises `ForwardedParseError` — covered by probe, not by test
* Bare `\r`: `parse('\r')` — same — covered by probe, not by test
* Bare `\n`: `parse('\n')` — same — covered by probe, not by test
* Tab-only: `parse('\t\t')` — returns `[]` — covered by probe (`test_edge_whitespace_only_yields_empty_forwarded` covers spaces but not tabs)
* DEL (0x7F): `parse('\x7f')` — raises `ForwardedParseError` — covered by probe, not by test
* HTAB inside value: `parse('for=\t')` — raises `ForwardedParseError("empty value")` after `_strip_ows` strips the tab and the result is empty — not covered by test

These are also easy wins; one parametrized test closes the gap.

## D. Format / round-trip gaps

| Gap | Suggested test |
|---|---|
| `format()` of `ForwardedElement` with empty `for_` tuple | produces `""` (no `for=` prefix) — covered by probe, not by test |
| `format()` of `ForwardedElement` with `by=""` (empty string, not None) | produces `by=""` — covered by probe, not by test |
| `format()` of `ForwardedElement` with all four fields `None`/empty | produces `""` — covered by probe (`format(empty_element) == ''`), not by test |
| `format()` then re-`parse()` of an element containing `host="example.com"` (quoted string) | round-trips `host='example.com'` — **covered** by `test_serializer.py` |
| Canonical ordering independent of input order | `parse('for=a;proto=https;by=2')` and `parse('by=2;for=a;proto=https')` should `format()` to the same string — covered by probe, **not** by test |

## E. CLI gaps

`tests/test_cli_json_smoke.py` has 6 tests:
* Version of subprocess invocation
* `python -m forwarded_parse --json < fixture` → valid JSON
* Empty stdin
* Malformed input → exit 1 + stderr message
* `cli.main(argv=['--json'])` programmatic call
* `--help` exit 0

Gaps:
* **No test for `cli.main(['--bogus-flag'])` → exit 1** (argparse usage error)
* **No test for `cli.main()` with non-TTY stdin that has trailing `\r\n`** — the `rstrip('\n')` then strip-`\r` logic in `cli.py:70-72` is untested
* **No test that CLI `--json` output is parseable JSON even with NUL bytes / Unicode** — the `json.dumps(..., indent=2)` escape behaviour is not directly exercised
* **No test that `cli.main(['--json'])` with a fixture containing `host="ex.com"` produces valid JSON** — covered indirectly by the basic smoke test
* **No test that `cli.main()` is idempotent on a normal multi-element chain** — round-trip is tested at the library level but not via the CLI
* The `cli.py` docstring example contains a bug (`"proto": https` unquoted — should be `"proto": "https"`) — this is a documentation defect (I-4), not a security one, but a `test_help_text_contains_valid_json` test would catch it.

## F. AC10 (fuzz harness) gap

SPEC.md `§9 AC10` references a `fuzz_parse.py` harness. **This file
does not exist** in the repo. The QA worker substituted pytest-corpus
coverage (`test_error_edge_cases.py` etc.). For the next cycle's
adversary workstream (T2 harnesses + T3 fuzz execution), this gap is
explicitly closed by spawning fuzzer harnesses for at least three
surfaces:

1. `parse(value: str)` — Atheris or `random`+`hypothesis` driven
2. `format(parsed: Forwarded)` — element-builder mutations
3. CLI stdin reader — `echo '...'` → `python -m forwarded_parse`

The five-card adversary chain (T1 audit → T2 harness → T3 fuzz run →
T4 triage → T5 FUZZING_REPORT.md) is the explicit remediation for this
gap.

## G. Cross-cycle distinctness gap (informational)

`forwarded-parse` is the first RFC 7239 parser in the factory. The
"competition table" gap is the inverse: there is no PyPI alternative
to benchmark against (the most-cited alternative, `pyforwarded`, has
had no releases since 2018). `benchmarks/BENCHMARK.md` correctly
benchmarks against `naive str.split(',')` — that is the right baseline
for this niche.