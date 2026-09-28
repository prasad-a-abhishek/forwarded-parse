# cycle_136/adv/04 — TRIAGE for forwarded-parse

> Adversary T4 (this card): triage, minimise, and rank the 4 findings surfaced by T3 CORPUS_RUN. Per Invariant 26 §4: every finding gets a per-finding folder with `repro.py`, `analysis.md`, `expected.txt`, `actual.txt`, `stack_trace.txt`; severity ranking is Critical/High/Medium/Low/Info; the cycle is rejected unless `zero_high_severity_unanalyzed == true`.

## Summary

| ID    | Severity | Class                          | Surface(s)                          | Instances | Blocks ship |
|-------|----------|--------------------------------|-------------------------------------|-----------|-------------|
| F-001 | HIGH     | LIBRARY_BUG                    | harness_format_main, harness_normalize_main | 1620      | YES         |
| F-002 | INFO     | ORACLE_HARNESS_BUG             | harness_cross_cycle                 | 1709      | NO          |
| F-003 | INFO     | RANDOM_GENERATOR_HARNESS_BUG    | harness_quote_handling              | 1843      | NO          |
| F-004 | HIGH     | LIBRARY_BUG_SYMPTOM (→ F-001)  | harness_cli_parse                   | 44        | YES         |

**Severity totals:** 0 Critical / 2 High / 0 Medium / 0 Low / 2 Info = 4 total.
**`zero_high_severity_unanalyzed == true`** — both High findings (F-001 and F-004) have full per-finding folders, repros, analysis, expected/actual outputs, and stack traces.

## Per-finding narrative

### F-001 — HIGH · LIBRARY_BUG · Idempotence violation

**Surface hits:** 1620 (810 in `harness_format_main` on the `format(parse(h)) == format(parse(format(parse(h))))` assertion; 810 in `harness_normalize_main` on the normalize-is-identity assertion).

**Smallest reproducer:** `parse("foo=bar")` returns `Forwarded(elements=(ForwardedElement(for_=(), by=None, host=None, proto=None),))` — a phantom element with no recognised data. `format()` of this element returns `''`. Re-parsing `''` yields `Forwarded(elements=())`. The element appeared in the first parse, vanished on round-trip.

**Root cause** (`src/forwarded_parse/_parser.py:_parse_element`, line 312):
- `_parse_pair()` correctly returns `None` for unknown forward-pair names (RFC 7239 §4 extension rule), and the caller `continue`s on `None`.
- But `_parse_element()` then unconditionally appends the element dict (with default values `for_=[]`, `by/host/proto=None`) to the result list — even though no recognised key was ever seen.

**Fix direction:** in `_parse_element()`, after the pair loop, return `None` if the element has `for_=[]` AND `by/host/proto` all `None`. Symmetric with `_parse_pair()`'s `None` return for unknown keys.

**Why HIGH:** breaks AC7 (round-trip idempotence), the only RFC 7239 round-trip property in the spec. Existing 331-test suite does NOT cover inputs containing only unknown keys — this is a real gap surfaced by fuzzing.

### F-002 — INFO · ORACLE_HARNESS_BUG · Escape-resolution gap

**Surface hits:** 1709 in `harness_cross_cycle` (oracle mismatches attributed to the gap).

**Smallest reproducer:** `parse(r'for="a\"b"')` returns `for=['a"b']` (RFC 7230 §3.2.6 resolves `\"` to `"`); naive oracle extracts `['a\\"b']` (strips outer quotes, leaves backslash literal). They disagree.

**Root cause** (`benchmarks/adversarial/cycle_136/harness_cross_cycle.py:_oracle_extract_for_values`): naive regex implementation `v = v[1:-1]` after a quote-check, with no escape-resolution pass.

**Why INFO:** the LIBRARY is correct — the test harness's reference oracle is intentionally naive per its docstring, but at corpus scale the gap drowns out real differences. Fix direction: implement RFC 7230 §3.2.6 escape resolution in the oracle (preferred) OR loosen the assertion to compare only UNQUOTED `for=` values.

### F-003 — INFO · RANDOM_GENERATOR_HARNESS_BUG · Trailing-backslash gap

**Surface hits:** 1843 in `harness_quote_handling` (parser rejections attributed to the generator gap).

**Smallest reproducer:** `parse('"abc\\"')` raises `ForwardedParseError("malformed forwarded-pair: '\"abc\\\"' (expected token=value)")` — correctly, because RFC 7230 §3.2.6 only recognises `\"` and `\\` as escape pairs; a bare trailing `\` is invalid.

**Root cause** (`benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value`): the generator concatenates random tokens/escape sequences and may produce a body ending in a bare backslash. The harness docstring claims bodies are "always well-formed" but does not enforce this for the trailing character.

**Why INFO:** the LIBRARY is correct — the test harness's input generator is the bug. Fix direction: in `random_quoted_value`, after building the body, if it ends in `\\` either strip the trailing backslash or append one more safe character.

### F-004 — HIGH · LIBRARY_BUG_SYMPTOM (linked to F-001) · CLI empty stdout

**Surface hits:** 44 in `harness_cli_parse` (assertion: "exit 0 + non-empty input → non-empty stdout").

**Smallest reproducer:** `echo 'foo=bar' | python -m forwarded_parse` returns exit 0 with empty stdout.

**Root cause:** identical to F-001. The CLI calls `format(parsed)` then `if out: write` (`src/forwarded_parse/cli.py:84`). For all-unknown elements `format()` returns `''`, the guard suppresses the write, and exit 0 leaves no signal.

**Why HIGH (linked to F-001):** same root cause, same library fix resolves it. Documented in `findings.jsonl` as `linked_to: F-001` so the next-cycle builder knows one PR closes both.

## Verdict

**VERDICT: TRIAGE-DIRTY** — 2 HIGH findings (F-001, F-004) require a builder remediation pass before the cycle can ship.

**Recommended T5 fix scope (for the builder card):**
1. In `src/forwarded_parse/_parser.py:_parse_element()`, add the "all-unknown element is None" guard. Closes F-001 and F-004.
2. Add `tests/test_idempotence_unknown_key_only.py` covering: `foo=bar`, `a=b;c=d`, `for=a;unknown=x` (still works), `unknown=x;also_unknown=y` (drop). Add a normalize assertion.
3. *(Optional, not blocking)* fix F-002 (oracle escape-resolution) and F-003 (random_quoted_value trailing-backslash) in the harness — these are harness bugs that should be fixed for the next fuzz cycle but do NOT block ship of v0.1.1.

**Acceptance for ship:**
- F-001 fixed and re-tested (re-run the 4 repros — they must all PASS the assertions, not confirm the bug).
- F-004 fixed transitively by F-001.
- `pytest tests/` returns 0 failed.
- `harness_format_main` and `harness_normalize_main` 0 oracle mismatches at 250 000 iters.

## Acceptance for THIS card (T4)

- [x] Every T3 finding has a per-finding folder under `benchmarks/adversarial/cycle_136/findings/F-NNN/`.
- [x] Each folder contains `repro.py`, `analysis.md`, `expected.txt`, `actual.txt`, `stack_trace.txt`.
- [x] `findings/findings.jsonl` parses cleanly as one JSON object per line.
- [x] All HIGH findings analysed (no `zero_high_severity_unanalyzed` violation).
- [x] Severity ranking documented (HIGH/INFO; no Medium/Low because all 4 are either library-block or harness-noise).
- [x] Verdict line at end (TRIAGE-DIRTY).
- [x] All 4 repros verified to actually run (3 confirm the bug; F-004 confirms via AssertionError on empty stdout).
- [x] Linked to F-003/F-004 root causes to F-001 (so the builder doesn't double-fix).

## Cross-references

- Parent: `t_c582eac9` (T3 CORPUS_RUN) — commit 57dd284, 1.765M iters, DIRTY, 4 findings surfaced.
- Child: `t_78e0299f` (T5 FUZZING_REPORT) — author `benchmarks/adversarial/cycle_136/fuzz/FUZZING_REPORT.md` from this triage.
- Spec: `cycle_136/adversary` (TRIAGE.md from `~/.hermes/repo_factory/cycles/cycle_136/forwarded-parse/build_body.md`).
- Invariant 26 §4 — zero_high_severity_unanalyzed contract.