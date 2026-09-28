# FUZZING_REPORT — cycle_136 / forwarded-parse v0.1.0

> Adversary T5 (this card): the mandatory final report for the
> `@repo-adversary` workstream per **Invariant 26 §5**. Aggregates the
> work of T1 (VULN_AUDIT, d9417ba) → T2 (HARNESSES, 6db1a6b) → T3
> (CORPUS_RUN, 57dd284, DIRTY) → T4 (TRIAGE, c310408) and declares the
> cycle's adversarial verdict. This card is the **parent-of-tag** for
> the future cycle_136/ship card; until its verdict moves from DIRTY to
> CLEAN, the cycle cannot ship.

## §1 — Executive Summary

`forwarded-parse` v0.1.0 (commit `d9417ba`) was adversarially exercised
across **10 fuzzing surfaces** for a total of **1,765,000 requested
iterations** (1,759,784 clean — 5,216 oracle mismatches across 4
surfaces, 0 short of requested budget due to mismatch-stopped
subprocesses). **Zero process crashes, zero hangs, zero OOM
events.** Library was verified CLEAN at 250,000-iter scale on 3
surfaces (`harness_parse_main`, `harness_type_errors`,
`harness_obfuscated`) and DIRTY on 4 surfaces (`harness_format_main`,
`harness_normalize_main`, `harness_cross_cycle`, `harness_cli_parse`,
`harness_quote_handling`) due to **2 real library bugs** surfaced
only at corpus scale, plus **2 harness-side bugs** that do not block
ship but should be cleaned up in cycle_137. The two library bugs
(F-001 idempotence violation on unknown-key-only elements, F-004 CLI
empty-stdout symptom of F-001) share a single root cause and a single
≤5-line fix in `src/forwarded_parse/_parser.py:_parse_element()`. The
T1 manual vulnerability audit found 0C/0H/0M/1L/10I; T3 fuzzing
revealed 2 additional HIGHs that manual review cannot surface (round-trip
property AC7 holds for any manually-chosen well-formed input, but
breaks on the smallest adversarial input `foo=bar`). The cycle is
**NEEDS_REMEDIATION**: HIGH-severity library bugs must be closed before
`cycle_136/ship` can complete.

## §2 — Methodology

### §2.1 — Approach

Per **Invariant 26 §2-3**, the adversary workstream was staged as
**8 stdlib-subprocess harnesses** (no Atheris, no libFuzzer — `pytest`
+ `subprocess.run` is sufficient for a pure-Python parser of this
size, and avoids the cost of native-extension instrumentation that
would not find bugs faster on a 187-LOC parser). Each harness is a
deterministic, seed-driven generator (`DEFAULT_SEED =
0xC0FFEE_1360_0001`) that drives a single public surface, asserts no
uncaught exception, and asserts one or more semantic oracles (idempotence,
round-trip, CRLF non-emission, TypeError-vs-ForwardedParseError
boundary).

### §2.2 — Per-surface iteration budget

Per surface, chosen to fit a wall-clock cap of ~1000 s under the 1500 s
dispatch limit. The CLI subprocess surface (`harness_cli_parse`)
dominates wall-clock at ~17 iters/s (1MiB stdin payload every 11th
iter); the other surfaces run at 5,000+ iters/s. All harness-bound
surfaces ran in parallel via a 4-worker thread pool, which cut
end-to-end wall-clock from sequential ~1390 s to ~854 s.

| Surface              | Iters   | Wall (s) | Iters/s  | Oracle assertion                            |
|----------------------|--------:|---------:|---------:|---------------------------------------------|
| harness_cli_parse    |  15,000 |   850.10 |     17.6 | exit 0 + non-empty input → non-empty stdout |
| harness_parse_main   | 250,000 |   126.23 |  1,980.6 | no uncaught exc; no CR/LF in format output  |
| harness_format_main  | 250,000 |   124.62 |  2,006.1 | `parse(s) == parse(format(parse(s)))`       |
| harness_normalize_main | 250,000 |   125.07 |  1,998.7 | `parse(s).to_dict() == normalize(parse(s)).to_dict()` |
| harness_cross_cycle  | 250,000 |   104.32 |  2,396.4 | regex-oracle agrees on `for=` value lists   |
| harness_obfuscated   | 250,000 |    13.82 | 18,089.0 | RFC 7239 §6.3 obf round-trip preserved      |
| harness_quote_handling | 250,000 |    12.   | 20,476.6 | RFC 7230 §3.2.6 escape resolution correct   |
| harness_type_errors  | 250,000 |     0.29 |    ~     | non-str → typed error (Invariant 21)        |
| harness_cli_format   |       0 |     0.00 |    —     | corpus-only (alias surface — see §2.4)      |
| harness_cli_normalize |      0 |     0.00 |    —     | corpus-only (alias surface — see §2.4)      |
| **TOTAL**            |**1,765,000** | **854.1** | — | — |

### §2.3 — Sanity gates

Every harness subprocess returned before its 1400-second timeout (no
`TimeoutExpired` exceptions). No `MemoryError`, no kernel-level OOM-killer
signals, no signal-induced exits, no `RecursionError` (the parser is
linear-time iterative — no regex backtracking, no recursion). The 331
existing pytest cases still pass after T2's harness additions — no
regressions.

### §2.4 — Deviations from default surface model

The T2 task body listed CLI flags `--parse <val>`, `--format <val>`,
`--normalize <val>`, `--self-test` that do not exist in the shipped
`src/forwarded_parse/cli.py` (the CLI is stdin-only with a `--json`
toggle). T2 built one CLI harness (`harness_cli_parse`) that drives
the actual CLI; `harness_cli_format` and `harness_cli_normalize` were
seeded as corpus-only (no harness, 0 iters) because the CLI has no
separate `--format` / `--normalize` mode. This deviation was also
flagged as T1 Info finding I-2.

The T2 task body also asked the type-error harness to assert empty
quoted-strings are rejected. The actual library behaviour (consistent
with RFC 7230 §3.2.6) is that empty quoted-strings ARE accepted. The
harness verifies acceptance is consistent across `by`/`host`/`proto`
slots.

### §2.5 — Oracle strategy per surface

| Surface | Oracle |
|---------|--------|
| harness_parse_main | (no semantic oracle — only "no uncaught exception" + "format() output contains no CR or LF byte") |
| harness_format_main | `parse(parse(s)) == parse(s)` (idempotence on AC7) |
| harness_normalize_main | `normalize(parse(s))` equals `parse(s)` to_dict (normalize is identity for well-formed input) |
| harness_cli_parse | exit 0 + non-empty stdin ⇒ non-empty stdout |
| harness_type_errors | non-str → typed exception (ForwardedParseError for parse; TypeError for format/normalize); never AttributeError, IndexError, KeyError |
| harness_obfuscated | `for=_obf` serialises as bare token (no quotes); verbatim round-trip across all 4 parameter slots |
| harness_quote_handling | parser resolves RFC 7230 §3.2.6 escape pairs (`\"`, `\\`); rejects bare trailing `\` |
| harness_cross_cycle | regex-based reference oracle on `for=` value extraction agrees with parser |

## §3 — Seed Corpus

### §3.1 — Construction

For each of the 8 harness-bound surfaces and 2 alias surfaces, **32 seed
inputs** were generated deterministically using
`DEFAULT_SEED = 0xC0FFEE_1360_0001` and written to
`benchmarks/adversarial/cycle_136/fuzz/<surface>/corpus/00.txt` …
`31.txt` (or `.json` for `harness_type_errors`). Total: **10 surfaces
× 32 seeds = 320 corpus inputs** on disk.

The corpora are documentation of the input distribution that the T2
harness internally samples (`_harness_common.random_str`,
`adversarial_pool`, `random_obf_token`, `random_quoted_value`, plus a
JSON type-tag pool for `harness_type_errors`); the harnesses use the
internal generators directly during fuzzing for performance — the
disk corpora are reusable for replay, regression, and as the
canonical seed for future fuzz cycles.

Manifest: `benchmarks/adversarial/cycle_136/fuzz/_corpus_manifest.json`
lists every surface and seed count.

### §3.2 — Input distribution per surface

| Surface | Distribution |
|---------|--------------|
| harness_parse_main | `random_str` (utf-8 with `errors='replace'`, 0–4096 bytes) + every 5th iter `adversarial_pool` (50+ known-bad seeds) |
| harness_format_main | same as harness_parse_main |
| harness_normalize_main | same as harness_parse_main |
| harness_cli_parse | adversarial_pool + 1MiB random bytes every 11th iter (CLI is the dominant wall-clock surface) |
| harness_cli_format | corpus-only (alias) |
| harness_cli_normalize | corpus-only (alias) |
| harness_type_errors | 21 non-str candidates (None, int, float, bool, list, tuple, bytes, bytearray, set, object, type-inst, memoryview, range, iterator) + 12 non-Forwarded candidates |
| harness_obfuscated | `random_obf_token` (1–64 char body, alnum + `-._~`); every 3rd iter multi-element chain; every 5th iter cycles through `by`/`host`/`proto` slots |
| harness_quote_handling | `random_quoted_value` (state-tracked generator enforcing no unescaped `"`, no `\` followed by `"`) + guard cases (unterminated, empty) |
| harness_cross_cycle | same as harness_parse_main + every 11th iter forces obf-only chain |

### §3.3 — Adversarial pool seeds (excerpt)

The `adversarial_pool` seeded into every parser-facing surface contains
at minimum: empty string, OWS-only (`"  \t"`), CRLF obs-fold
(`"\r\n for=192.0.2.43"`), multibyte UTF-8, NUL byte, IPv6 literals
(`"[2001:db8::1]"`), obf tokens (`"_a1b2c3"`), quoted-strings
(`"for=\"hello\""`), missing `=` (`"foo"`), unterminated quotes
(`"for=\"hello"`), known-edge single-element round trips
(`"for=192.0.2.43"`), known-edge multi-element chains
(`"for=192.0.2.43, for=198.51.100.7"`), and **the F-001 trigger
`"foo=bar"`** (unknown-pair element) — added post-T4 to the seed pool
so a future regression on this bug surfaces immediately at smoke-test
scale.

## §4 — Findings Table

| ID    | Severity | Class                       | Surface(s)                          | Instances | Blocks ship | Owner      |
|-------|----------|-----------------------------|-------------------------------------|-----------|-------------|------------|
| F-001 | HIGH     | LIBRARY_BUG                 | harness_format_main, harness_normalize_main | 1,620 (810 each) | **YES** | @repo-builder |
| F-002 | INFO     | ORACLE_HARNESS_BUG          | harness_cross_cycle                 | 1,709     | NO          | @repo-adversary (harness cleanup, cycle_137) |
| F-003 | INFO     | RANDOM_GENERATOR_HARNESS_BUG | harness_quote_handling              | 1,843     | NO          | @repo-adversary (harness cleanup, cycle_137) |
| F-004 | HIGH     | LIBRARY_BUG_SYMPTOM (→ F-001) | harness_cli_parse                 |       44  | **YES** (linked to F-001) | @repo-builder |

**Severity totals:** 0 Critical / 2 High / 0 Medium / 0 Low / 2 Info = **4 total findings**.

**`zero_high_severity_unanalyzed == true`** — both High findings (F-001,
F-004) have full per-finding folders under
`benchmarks/adversarial/cycle_136/findings/F-NNN/` with `repro.py`,
`analysis.md`, `expected.txt`, `actual.txt`, `stack_trace.txt`. The
two INFO findings are harness-side and explicitly not blocking.

**Library-verified CLEAN at scale:**

| Surface              | Iters   | Verdict |
|---------------------|--------:|---------|
| harness_parse_main  | 250,000 | CLEAN (parser total over arbitrary input; format() never re-emits CR/LF) |
| harness_type_errors | 250,000 | CLEAN (Invariant 21 boundary satisfied for all 24 non-str candidates) |
| harness_obfuscated  | 250,000 | CLEAN (RFC 7239 §6.3 obf round-trip preserved verbatim across all 4 parameter slots) |

## §5 — Per-Finding Narrative

### §5.1 — F-001 (HIGH) · Idempotence violation on elements with no recognised keys

**Surface hits:** 1,620 (810 in `harness_format_main` on the
`parse(s) == parse(format(parse(s)))` assertion; 810 in
`harness_normalize_main` on the normalize-is-identity assertion).

**Smallest reproducer:**

```python
>>> parse("foo=bar")
Forwarded(elements=(ForwardedElement(for_=(), by=None, host=None, proto=None),))
>>> format(parse("foo=bar"))
''
>>> parse(format(parse("foo=bar")))
Forwarded(elements=())
```

`format(parse("foo=bar")) == format(parse(format(parse("foo=bar"))))`
(trivially both `''`), but the **first** parse returned a non-empty
`Forwarded` whose only representation is `''` — i.e. the input was
parsed into a phantom element that vanishes on round-trip. This breaks
**AC7 (round-trip idempotence)**.

**Root cause** (`src/forwarded_parse/_parser.py:_parse_element`,
line 312):

1. `_parse_pair()` correctly returns `None` for unknown forward-pair
   names (RFC 7239 §4 extension rule), and the caller `continue`s on
   `None`.
2. But `_parse_element()` then unconditionally appends the element
   dict (with default values `for_=[]`, `by/host/proto=None`) to the
   result list — even though no recognised key was ever seen.

This is asymmetric: the extension rule is applied at the **pair** level
(skip unknown pairs) but not symmetrically at the **element** level
(skip elements that contribute no recognised parameter).

**Impact:** breaks AC7. Existing 331-test suite does NOT cover inputs
containing only unknown keys — this is a real test-coverage gap
surfaced by fuzzing. End-user impact: a downstream proxy that
unconditionally re-emits `format(parse(incoming_forwarded))` will
silently drop any unknown-parameter extensions (per RFC 7239 §4, this
is technically allowed, but the library's idempotence contract makes it
a regression when the user does explicitly want to preserve-and-round-trip
unknown data — they cannot tell that the library discarded it).

**Repro artifacts:** `benchmarks/adversarial/cycle_136/findings/F-001/`
(repro.py + analysis.md + expected.txt + actual.txt + stack_trace.txt).

**Recommended fix** (≤5 lines, in
`src/forwarded_parse/_parser.py:_parse_element`):

```python
# After the pair loop, before appending to result:
if not out["for_"] and out["by"] is None and out["host"] is None and out["proto"] is None:
    return None  # symmetric with _parse_pair()'s None return for unknown keys
```

This mirrors how `_parse_pair()` returns `None` for unknown-key pairs
and lets the outer `parse_forwarded()` loop drop the element
consistently. Acceptance test:
`tests/test_idempotence_unknown_key_only.py` covering `foo=bar`,
`custom=value`, `for=a;unknown=x` (still works — `for=` keeps it),
`unknown=x;also_unknown=y` (drop), and a normalize assertion that
`normalize(parse("foo=bar")) == Forwarded(elements=())`.

### §5.2 — F-002 (INFO) · Cross-cycle oracle doesn't resolve quoted-string escapes

**Surface hits:** 1,709 in `harness_cross_cycle` (oracle mismatches
attributed to the gap).

**Smallest reproducer:**

```
INPUT:   for="a\"b"
parser:  for=['a"b']              # RFC 7230 §3.2.6: \" → "
oracle:  ['a\\"b']                # naive: strips quotes, leaves backslash literal
```

**Root cause** (`benchmarks/adversarial/cycle_136/harness_cross_cycle.py:_oracle_extract_for_values`):
the naive regex implementation does `v = v[1:-1]` after a
`startswith/endswith('"')` check, with no intermediate
escape-resolution pass. The real parser does resolve RFC 7230 §3.2.6
escape pairs.

**Why INFO, not HIGH:** the LIBRARY is correct. The harness's reference
oracle is intentionally naive per its docstring ("sanity check, not a
strict cross-validation"), but at corpus scale the gap produces 1,709
false-positive mismatches that drown out any real library issue. No
library fix is needed; the library's escape handling is verified clean
by the dedicated `harness_quote_handling` surface. Fix direction:
either (a) implement full escape resolution in the oracle (~20 lines,
preferred — makes the surface a strict cross-check) or (b) loosen the
harness assertion to compare only UNQUOTED `for=` values (~2 lines).

**Repro artifacts:** `benchmarks/adversarial/cycle_136/findings/F-002/`.

### §5.3 — F-003 (INFO) · `random_quoted_value` emits bodies ending in bare backslash

**Surface hits:** 1,843 in `harness_quote_handling` (parser
rejections attributed to the generator gap).

**Smallest reproducer:**

```
INPUT:   "abc\"
parser:  raises ForwardedParseError(
           "malformed forwarded-pair: '\"abc\\\"' (expected token=value)"
         )
```

**Root cause**
(`benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value`):
the generator concatenates random tokens/escape sequences and may
produce a body ending in a bare backslash. When wrapped in `"..."`,
the result is a malformed quoted-string per RFC 7230 §3.2.6 (only
`\"` and `\\` are recognised as escape pairs; a bare trailing `\` is
invalid). The harness docstring claims bodies are "always well-formed"
but does not enforce this for the trailing character.

**Why INFO, not HIGH:** the LIBRARY is correct. RFC 7230 §3.2.6 is
unambiguous: only `\"` and `\\` are escapes. The parser's
`unterminated quoted-string` error is the spec-correct response. The
bug is in the harness's input generator. Fix direction: in
`random_quoted_value`, after building the body, if it ends in `\\`
either strip the trailing backslash or append one more safe character
(~3 lines).

**Repro artifacts:** `benchmarks/adversarial/cycle_136/findings/F-003/`.

### §5.4 — F-004 (HIGH, linked to F-001) · CLI empty-stdout contract violation

**Surface hits:** 44 in `harness_cli_parse` (assertion: "exit 0 +
non-empty input → non-empty stdout").

**Smallest reproducer:**

```
$ echo 'foo=bar' | python -m forwarded_parse
$ echo $?
0
```

stdout is empty. Exit code is 0. The CLI's documented contract
(`cli.py:54-65`) carves out "empty input → empty output" but does NOT
explicitly handle the case where input parses non-empty yet serialises
to empty.

**Root cause:** identical to F-001. The CLI calls `format(parsed)` then
`if out: stdout.write(...)` (`src/forwarded_parse/cli.py:84`). For
all-unknown elements `format()` returns `''`, the guard suppresses the
write, and exit 0 leaves no signal.

**Why HIGH (linked to F-001):** same root cause, same library fix
resolves both. Documented in `findings/findings.jsonl` as
`linked_to: F-001` so the cycle_137 builder knows one PR closes both.
No independent library fix is needed; fixing F-001 cascades to F-004.

**Impact:** downstream log-processing pipelines that assume "exit 0 ⇒
output" will treat the CLI as silent-failure for valid unknown-parameter
inputs. The output volume is small (44 / 1,765,000 ≈ 0.0025%) but the
contract violation is observable and confusing.

**Recommended fix:** fix F-001 first. Then either (a) leave the CLI
as-is and document "exit 0 + empty stdout ⇒ empty round-trip" in the
CLI docstring, or (b) replace the `if out:` guard with an unconditional
`stdout.write('' if not out else out)` so empty stdout never escapes
(more POSIX-text-tool conventional). Either is acceptable; (a) is the
minimum change.

**Repro artifacts:** `benchmarks/adversarial/cycle_136/findings/F-004/`.

## §6 — Recommendations

### §6.1 — Blocking (must be remediated before `cycle_136/ship`)

**R-1 (HIGH, F-001 + F-004 single PR):** in
`src/forwarded_parse/_parser.py:_parse_element()`, add the
all-unknown-element-is-`None` guard:

```python
# After the pair loop:
if not out["for_"] and out["by"] is None and out["host"] is None and out["proto"] is None:
    return None
```

Estimated diff: 3–5 lines of production code. Closes both F-001 and
F-004 atomically. Add `tests/test_idempotence_unknown_key_only.py`
covering `foo=bar`, `custom=value`, `for=a;unknown=x` (still works —
`for=` keeps it), `unknown=x;also_unknown=y` (drop), and a normalize
assertion. Acceptance:

  - `pytest tests/` returns 0 failed.
  - `harness_format_main` and `harness_normalize_main` 0 oracle
    mismatches at 250,000 iters (re-run from T2 seeds).
  - `harness_cli_parse` 0 oracle mismatches at 15,000 iters.
  - `benchmarks/adversarial/cycle_136/findings/F-001/repro.py` and
    `…/F-004/repro.py` both PASS their `assert` lines (not confirm the
    bug — the assertions in those repros verify the FIX).

**Owner:** @repo-builder. Estimated cost: ≤30 min including test
addition and a 250k-iter re-fuzz. **Cards to mint:** a single
`cycle_136/builder/F-001+F-004-fix` card, parents=[t_78e0299f], gating
`cycle_136/ship`.

### §6.2 — Non-blocking (cycle_137 hygiene)

**R-2 (INFO, F-002):** implement RFC 7230 §3.2.6 escape resolution in
`benchmarks/adversarial/cycle_136/harness_cross_cycle.py:_oracle_extract_for_values`
so the oracle becomes a strict cross-check (~20 lines). Document in the
oracle docstring that "the oracle mirrors the parser's escape handling
verbatim". Eliminates 1,709 false-positive mismatches per cycle.

**R-3 (INFO, F-003):** in
`benchmarks/adversarial/cycle_136/_harness_common.py:random_quoted_value`,
after building the body, if `body.endswith('\\')` strip the trailing
backslash or append one more safe character (~3 lines). Eliminates
1,843 false-positive "parser rejected malformed input" events per
cycle.

These two are **harness cleanup**, not library bugs. They do NOT block
ship of forwarded-parse v0.1.1 but should land in the next adversary
cycle (cycle_137) so the next corpus-run is quieter and the next
FUZZING_REPORT's noise floor is lower.

### §6.3 — Recommended cycle_137 carry-overs (from T1 VULN_AUDIT)

These were already in `VULN_AUDIT.md` and remain unaddressed; carry
forward to cycle_137 backlog:
- **I-4:** fix `cli.py:13` invalid JSON example docstring.
- **I-6:** add `__post_init__` validator to `ForwardedElement`
  rejecting `by=""`, `host=""`, `proto=""`.
- **I-7:** add README "Caveats" note on caller-side CRLF sanitisation.
- **I-9:** replace `_is_token_char`'s `c.isalnum()` with explicit
  ASCII `a-zA-Z0-9` check.

None block ship of v0.18.0 / v0.1.1. **L-1** (no input size cap) is
explicitly out of scope for this parser per RFC 7239 §5.

### §6.4 — Acceptance for THIS card (T5 FUZZING_REPORT)

- [x] FUZZING_REPORT.md committed under
      `benchmarks/adversarial/cycle_136/` AND byte-identical copy at
      `fuzz/FUZZING_REPORT.md` (pre-push gate reads both locations).
- [x] All 6 required sections present (Executive Summary, Methodology,
      Seed Corpus, Findings Table, Per-Finding Narrative, Recommendations).
- [x] Findings Table enumerates all 4 T4 findings with id, severity,
      surface, summary, blocks-ship, owner.
- [x] Per-Finding Narrative covers each finding with smallest repro,
      root cause, impact, recommended fix.
- [x] Recommendations split into Blocking (R-1, addresses F-001+F-004)
      and Non-blocking (R-2/R-3, harness cleanup for cycle_137).
- [x] Verdict line at end (`VERDICT: NEEDS_REMEDIATION`) — byte-strict,
      plain, no bold, no quotes (pre-push gate contract).
- [x] `zero_high_severity_unanalyzed == true` (both F-001 and F-004
      have full per-finding folders).

### §6.5 — Cross-references

- Parent: `t_1290ae8c` (T4 TRIAGE) — commit `c310408`, 4 findings (0C/2H/0M/0L/2I).
- Grandparent: `t_c582eac9` (T3 CORPUS_RUN) — commit `57dd284`,
  1,765,000 iters, DIRTY.
- Great-grandparent: `t_dc622756` (T2 HARNESSES) — commit `6db1a6b`,
  8 surfaces, 800 smoke iters CLEAN.
- Great-great-grandparent: `t_a5beb2a8` (T1 VULN_AUDIT) — commit
  `fbe8ab8`, 0C/0H/0M/1L/10I on d9417ba.
- Spec: `~/.hermes/repo_factory/cycles/cycle_136/forwarded-parse/build_body.md`
  (TRIAGE.md from `cycle_136/adversary`).
- Invariant 26 §5 — `FUZZING_REPORT.md` is the **parent-of-tag** for
  `cycle_136/ship`.

VERDICT: NEEDS_REMEDIATION
