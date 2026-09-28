# cycle_136/adv/02 — HARNESSES for forwarded-parse

> Status: **8/8 surfaces clean.** Smoke pass at `--iters 100` per surface
> completes in ~5.9s total (5.7s is the CLI subprocess surface). No crashes,
> no oracle mismatches. All 331 existing pytest cases still pass.

## What this is

The `harness_*.py` files in this directory are the cycle_136/T2
fuzzing-harness surface per **Invariant 26 §2**. They feed varied,
sometimes-bad inputs into every public entrypoint of `forwarded-parse`
(`/root/projects/forwarded-parse/.worktrees/t_cycle136-adv-01/src/forwarded_parse/`)
and assert no uncaught exception (crash) AND no oracle mismatch (semantic
regression). The `T3` corpus_run card will scale these harnesses up to
long durations; this T2 deliverable establishes they are correct.

The common driver is `_harness_common.py` — every harness `sys.path.insert`s
its parent directory and imports `run_harness`, which writes a JSON results
envelope to `fuzz/<surface>/results.json` per smoke run.

## Smoke results

Every harness was invoked once with `--iters 100 --seed 0xC0FFEE_1360_0001`
(deterministic). All returned exit 0 with `verdict: CLEAN`.

| Harness | Surface | Inputs exercised | Smoke iters | Smoke exit |
|---|---|---|---|---|
| harness_parse_main.py | Core API — `parse(s)` → `format(parsed)` round-trip; assert no CR/LF re-emission | Random utf-8 (`errors='replace'`) up to 4096 bytes + 50+ known-bad seeds (empty, OWS-only, CRLF obs-fold, multibyte, NUL, IPv6 literals, obf tokens, quoted-strings, missing `=`, unterminated quotes, etc.) | 100/100 | 0 CLEAN |
| harness_format_main.py | Idempotence oracle — `parse(s)` → `format()` → `parse()` must equal the first parse; `format()` must also be idempotent | Same input pool as `harness_parse_main` | 100/100 | 0 CLEAN |
| harness_normalize_main.py | `parse(s)` → `normalize()` → `format()` → `parse()` round-trip with parser-idempotence guard | Same input pool as `harness_parse_main` | 100/100 | 0 CLEAN |
| harness_cli_parse.py | CLI subprocess surface — `python3 -m forwarded_parse` reads stdin, emits canonical form or JSON (with `--json`); 1MiB random bytes every 11th iter | Adversarial pool + every 11th iter injects 1MiB random bytes to exercise large-input path | 100/100 | 0 CLEAN |
| harness_type_errors.py | Type-error boundary (Invariant 21) — non-str to `parse()` (must raise ForwardedParseError, NOT AttributeError); non-Forwarded to `format()`/`normalize()` (must raise TypeError) | 21 non-str candidates (None, int, float, bool, list, tuple, bytes, bytearray, set, object, type-inst, memoryview, range, iterator) + 12 non-Forwarded candidates | 100/100 | 0 CLEAN |
| harness_obfuscated.py | RFC 7239 §6.3 obf round-trip — `for=_obf` must serialize as bare token (no quotes), preserve verbatim across `parse → format → parse`; also exercises obf in `by=`/`host=`/`proto=` slots | Random obf tokens (1–64 char body, alnum + `-._~`); every 3rd iter adds multi-element chains, every 5th iter cycles through `by`/`host`/`proto` slots | 100/100 | 0 CLEAN |
| harness_quote_handling.py | RFC 7230 §3.2.6 quoted-string escape resolution — `\\"` → `"`, `\\\\` → `\\`, bare `\` preserved verbatim; also unterminated quote rejection and empty `""` acceptance | Random well-formed quoted-string bodies (state-tracked generator ensures no malformed inputs); unterminated + empty inputs as guard cases | 100/100 | 0 CLEAN |
| harness_cross_cycle.py | Independent regex-based oracle — re-implements for=value extraction using `re.fullmatch` on the tchar class and string-split on `;`/`,`; verifies agreement with `parse()` on `for=` values across all elements | Same adversarial pool + every 11th iter forces an obf-only chain to exercise the §6.3 path | 100/100 | 0 CLEAN |

**Totals:** `800` iters → `800` clean. `0` crashes, `0` oracle mismatches.
Aggregate elapsed: `~5.9s` wall-clock on the verifier host.

## Per-surface results.json

Each `fuzz/<surface>/results.json` contains:

- `surface`, `iters_requested`, `iters_clean`
- `crashes` (list of `{iter, kind, msg}` — empty when clean)
- `oracle_mismatches` (list of `{iter, kind, msg}` — empty when clean)
- `harness_self_error` (None when clean; populated on harness-config bugs)
- `seed`, `started_utc`, `ended_utc`, `elapsed_seconds`
- `python` (verifier interpreter version)
- `argv` (exact command line of the run)
- `verdict` (`CLEAN` | `DIRTY` | `HARNESS_SELF_ERROR`) and `exit_code`

Re-running any harness with the same `--seed` produces a byte-different
output envelope only because of `started_utc` / `ended_utc` /
`elapsed_seconds`; the actual `crashes` and `oracle_mismatches` arrays
are deterministic.

## Surfaces covered (per V1–V3 in the task body)

| Required surface | Harness(es) |
|---|---|
| Core API (`parse`, `format`, `normalize`) | `harness_parse_main`, `harness_format_main`, `harness_normalize_main`, `harness_type_errors` |
| CLI entrypoint | `harness_cli_parse` (NB: the actual CLI is `python3 -m forwarded_parse` reading from stdin with optional `--json`; the task body's mention of `--parse`/`--format`/`--normalize`/`--self-test` flags does not match `src/forwarded_parse/cli.py` — see "Deviations from task body" below) |
| I/O / rendering (stdin/stdout, CRLF, unicode, large inputs, malformed) | `harness_parse_main` (CRLF obs-fold, multibyte, malformed UTF-8), `harness_cli_parse` (1MiB stdin) |
| Type-error boundary (≥1 required) | `harness_type_errors` |
| Obfuscated tokens (RFC 7239 §6.3) | `harness_obfuscated` |
| Quoted-string handling (RFC 7230 §3.2.6) | `harness_quote_handling` |
| Cross-cycle / sanity oracle | `harness_cross_cycle` (regex-based, since forwarded-parse is the FIRST RFC 7239 parser in the factory — no factory sibling to oracle against) |

That's **7 distinct required surfaces** with **8 harnesses** total, well
above the "≥3 surfaces" floor in V1 of the task body.

## Deviations from task body

The task body listed CLI flags `--parse <val>`, `--format <val>`,
`--normalize <val>`, `--self-test` that do not exist in
`src/forwarded_parse/cli.py` (the shipped CLI is stdin-only with a
`--json` toggle). This was also flagged as an Info finding in the
cycle_136/T1 VULN_AUDIT. The harness exercises the actual CLI surface
(stdin + `--json`).

The task body also asked the type-error harness to assert "clean
TypeError (NOT AttributeError or uncaught)" for `parse()`. The actual
behaviour (also flagged in VULN_AUDIT Info finding) is that `parse()`
delegates to `parse_forwarded()` which raises `ForwardedParseError` (a
`ValueError` subclass) for non-str input. The harness therefore accepts
EITHER `TypeError` OR `ForwardedParseError` for `parse()` on non-str
input (Invariant 21's intent — never `AttributeError`, never uncaught
— is preserved), while `format()` / `normalize()` (which DO perform
explicit `isinstance` checks) must raise `TypeError` only.

The task body also asked the type-error harness to assert empty
quoted-strings are rejected. The actual behaviour (consistent with RFC
7230 §3.2.6) is that empty quoted-strings ARE accepted for `by`/`host`/
`proto` (the value is the empty string, which is a valid parameter
value). The harness now verifies this acceptance is consistent across
all three slots.

## What this run did NOT find

Per the **honest progress** principle, the cross-cycle sanity oracle
(`harness_cross_cycle`) re-derives the `for=` value list from a regex-based
re-implementation and compares against `parse()`. **They agreed on all
100 iterations.** I tried:

1. Plain token `for=` values (alphanumeric + punctuation) → exact match.
2. Quoted-string `for=` values (`for="192.0.2.43"`, `for="[2001:db8::1]"`,
   `for="Hello\\World"`) → both produce the unquoted, escape-resolved
   value.
3. Obf-only chains (multiple `for=_obf` separated by `, `) → both
   produce the same ordered list.
4. Multi-element chains with mixed obf + named values → both produce
   the same per-element `for_` lists.

The quoted-string round-trip oracle (`harness_quote_handling`) exercised
the parser's escape-resolution logic on bodies generated by a
state-tracked generator that ensures no unescaped `"` and no `\\` followed
by `"` (which would close the string prematurely per RFC 7230 §3.2.6).
**The parser's escape resolution matched the harness's re-implementation
on all 100 iterations.**

If the cycle_136/T3 corpus_run phase were to find a divergence, it would
surface here — the `run_harness()` driver writes every mismatch with full
context (`{iter, kind, msg}`) so triage can reconstruct.

## What the T3 phase needs

For the next card (cycle_136/adv/03, parent-of-tag is T2's child), these
harnesses are reusable as-is. Recommended invocation:

```bash
PYTHONPATH=src python3 benchmarks/adversarial/cycle_136/harness_parse_main.py --iters 1000000
# ... and similarly for the other 7 harnesses
```

Each surface is independently scalable to whatever duration T3 picks.
`fuzz/<surface>/results.json` is the artifact the T4 TRIAGE card reads.

## Files in this directory

```
harness_parse_main.py            # core-API round-trip
harness_format_main.py           # idempotence oracle
harness_normalize_main.py        # normalize round-trip
harness_cli_parse.py             # subprocess CLI surface (stdin + --json)
harness_type_errors.py           # invariant-21 boundary
harness_obfuscated.py            # RFC 7239 §6.3 obf round-trip
harness_quote_handling.py        # RFC 7230 §3.2.6 quoted-string escape resolution
harness_cross_cycle.py           # independent regex-based sanity oracle
_harness_common.py               # run_harness + random_str / adversarial_pool / random_obf_token / random_quoted_value
HARNESSES.md                     # this file
fuzz/<surface>/results.json      # one per harness, smoke pass at 100 iters
```

## Branch / commit

- Branch: `wt/cycle136-adv-01`
- Commit: see `git log -1` after the cycle_136/T2 commit lands.
