# cycle_136/adv/03 — CORPUS_RUN for forwarded-parse

> **Status: DIRTY.** Run completed across 10 surfaces with 1,765,000 iters
> requested (1,759,784 clean). Aggregate verdict: **DIRTY** — 4 distinct
> findings surfaced at corpus scale (2 LIBRARY bugs, 2 HARNESS-side bugs).
> No process crashes, no hangs, no OOM. Findings are categorised and
> forwarded to T4 (`t_1290ae8c`) for triage.

This is the corpus_run card per **Invariant 26 §3**. It seeds diverse input
corpora per surface, drives the T2 harness executables at scale, and
collects per-surface + aggregate stats. All work lives under
`benchmarks/adversarial/cycle_136/fuzz/`.

## §1 — Surfaces and seed corpora

Each `<surface>/corpus/` directory contains 32 seed inputs drawn from the
adversarial distribution that the T2 harness internally samples
(`_harness_common.random_str`, `adversarial_pool`, `random_obf_token`,
`random_quoted_value`, plus a JSON type-tag pool for `harness_type_errors`).
Corpora are written deterministically using `DEFAULT_SEED = 0xC0FFEE_1360_0001`
so re-running the generator yields identical bytes.

Total: **10 surfaces × 32 seeds = 320 corpus inputs** on disk, used as
documentation of the input distribution (not loaded by the harnesses at
fuzz-time; the harnesses use internal generators for performance).

Manifest: `fuzz/_corpus_manifest.json` lists every surface and seed count.

| Surface                  | Kind | Seeds | Notes |
|--------------------------|------|------:|-------|
| harness_parse_main       | text | 32 | random utf-8 + adversarial pool |
| harness_format_main      | text | 32 | parseable text inputs |
| harness_normalize_main   | text | 32 | parseable text inputs |
| harness_cli_parse        | text | 32 | stdin payloads (some 1MiB-scale) |
| harness_cli_format       | text | 32 | alias surface (no dedicated harness; CLI is stdin-only per T2) |
| harness_cli_normalize    | text | 32 | alias surface (no dedicated harness) |
| harness_type_errors      | json | 32 | type-tag candidates (24 types) |
| harness_obfuscated       | text | 32 | `for=_obf` and mixed obf chains |
| harness_quote_handling   | text | 32 | RFC 7230 §3.2.6 quoted-string bodies |
| harness_cross_cycle      | text | 32 | parseable text inputs (regex-oracle cross-check) |

## §2 — Fuzzer execution

Per-surface iters were chosen to fit a wall-clock budget of ~1000 s
(under the 1500 s dispatch cap). The CLI subprocess surface
(`harness_cli_parse`) dominates wall-clock at ~17 iters/s (every 11th
iter is a 1MiB-scale payload); the other surfaces run at
5000+ iters/s. All 8 harness-bound surfaces ran in parallel
(thread pool, max_workers=4).

| Surface                  | Iters  | Wall (s) | Iters/s  |
|--------------------------|-------:|---------:|---------:|
| harness_cli_parse        | 15,000 |   850.10 |     17.6 |
| harness_parse_main       | 250,000 |   126.23 |  1,980.6 |
| harness_format_main      | 250,000 |   124.62 |  2,006.1 |
| harness_normalize_main   | 250,000 |   125.07 |  1,998.7 |
| harness_cross_cycle      | 250,000 |   104.32 |  2,396.4 |
| harness_obfuscated       | 250,000 |    13.82 | 18,089.0 |
| harness_quote_handling   | 250,000 |    12.21 | 20,476.6 |
| harness_type_errors      | 250,000 |     0.29 |   … (sub-second budget) |
| harness_cli_format       |       0 |     0.00 |  corpus-only (alias) |
| harness_cli_normalize    |       0 |     0.00 |  corpus-only (alias) |
| **TOTAL**                | **1,765,000** | **854.1 (parallel)** | — |

(Harness parallelism cuts end-to-end wall-clock from a sequential ~1390 s
to ~854 s.)

Stats envelope (per V3): `{iters, crashes, hangs, oom, oracle_mismatches, exit_code, duration_s}` — written per surface to `fuzz/<surface>/stats.json`. Aggregate: `fuzz/AGGREGATE_STATS.json`.

Sanity gates honoured: every harness subprocess returned before its
1400-second `subprocess.run` timeout; no `TimeoutExpired` exceptions;
no `MemoryError`; no kernel-level OOM-killer signals.

## §3 — Aggregate findings

| Finding | Surface(s)                  | Iters | Severity | Class                  | Status |
|---------|-----------------------------|------:|----------|------------------------|--------|
| **F-001** — Idempotence violation: element with no recognized keys drops on round-trip | harness_format_main (810) + harness_normalize_main (810) | 1,620 | **HIGH** | LIBRARY BUG | Owned by T4 → T5 |
| **F-002** — Cross-cycle oracle doesn't resolve quoted-string escapes | harness_cross_cycle (1,709) | 1,709 | INFO | ORACLE HARNESS BUG (noise floor — the regex oracle is intentionally naive per its docstring; corpus_run surface real "mismatches" that aren't library defects) | Surface to T5 for harness-cleanup or document |
| **F-003** — `random_quoted_value()` may emit bodies ending in bare backslash, defeating its own "well-formed" invariant | harness_quote_handling (1,843) | 1,843 | INFO | RANDOM GENERATOR HARNESS BUG (the parser CORRECTLY rejects malformed input per RFC 7230 §3.2.6) | Surface to T5 for harness-cleanup |
| **F-004** — CLI emits empty stdout for inputs that reduce to an empty formatted form | harness_cli_parse (44) | 44 | **HIGH** (same root cause as F-001) | LIBRARY BUG | Owned by T4 → T5 (fixed by F-001 remediation) |

**Library-verified CLEAN at scale (no oracle mismatches, no crashes):**

| Surface                  | Iters  | Verdict |
|--------------------------|-------:|---------|
| harness_parse_main       | 250,000 | CLEAN (parse() total over arbitrary input; format() never re-emits CR/LF) |
| harness_type_errors      | 250,000 | CLEAN (Invariant 21 boundary satisfied for all 24 non-str candidates) |
| harness_obfuscated       | 250,000 | CLEAN (RFC 7239 §6.3 obf round-trip preserved verbatim across all 4 parameter slots) |

### F-001 detail

**Input triggering it:** any string that parses to an element with no recognised keys
(`for`/`by`/`host`/`proto`). Smoke examples:

* `foo=bar` — unknown pair, silently ignored by parser per RFC 7239 §4.
  `parse("foo=bar")` → `Forwarded(elements=(ForwardedElement(for_=(), by=None, host=None, proto=None),))`.
  `format(...)` → `""`.
  `parse("")` → `Forwarded(elements=())`.
  These two parses disagree ⇒ idempotence violation (AC7 broken).
* `custom=value`, `=value`, `proto-version=2`, `;foo=bar;`, `for=_a;custom=x`.

**Root cause:** the parser's `_parse_element` (in `src/forwarded_parse/_parser.py`)
builds a `_ElementDict` for every non-empty `;`-chunk and pushes it onto the
elements list even when all recognised keys ended up `None`. There is no
post-filter to drop elements that contributed no recognised parameter. This
contradicts RFC 7239 §4's extensibility principle: unknown names are
ignored by consumers, so an element containing only unknown pairs is
logically empty from a consumer's view.

**Recommended fix (forwarded to T5):** in `_parse_element`, return `None`
when `out["for_"] == [] and out["by"] is None and out["host"] is None and out["proto"] is None`. The caller already handles `None` returns by skipping the element.

This is a real library bug discovered **only at corpus scale** — the
T2 smoke pass at 100 iters per surface never hit `foo=bar`-class
inputs (`adversarial_pool` did include `foo=bar`, but `random_str` did
not, and the mix weight put `foo=bar` at ~1/N chance per iter; 100 iters
is too few to reliably hit it). At 250k iters, the random-str pool
repeatedly generates inputs starting with `for=a;` followed by an unknown
key, or bare `custom=value`.

### F-004 detail

Same root cause: CLI's `format(parsed)` returns `""` for inputs like
`foo=bar`; the CLI's `if out: stdout.write(...)` then skips the write.
Exit 0 + empty stdout + non-empty stdin = the 44 harness_cli_parse
mismatches. Fixing F-001 cascades to F-004.

### F-002 detail

`harness_cross_cycle._oracle_extract_for_values` strips surrounding quotes
but does NOT resolve RFC 7230 §3.2.6 backslash escapes (`\"` → `"`,
`\\` → `\`). On quoted-string `for=` values containing backslashes, it
returns the un-resolved body while the real parser returns the resolved
body — guaranteed divergence. The harness's docstring acknowledges this
("intentionally naive ... sanity check, not a strict cross-validation"),
so the harness is **working as designed** but the "mismatch" signal is
not actionable. Recommendation: either implement full escape resolution in
the oracle (preferred for use as a real cross-check) or annotate
mismatches as `kind="oracle_noisy"` and de-prioritise them in triage.

### F-003 detail

`_harness_common.random_quoted_value()` may emit a `bare_backslash` as
the final character of the generated body. The harness wraps the body
in `f'{slot}="{body}"'`, producing a header value like `by="foo\"`. The
parser (correctly) flags this as `unterminated quoted-string` per
RFC 7230 §3.2.6 because the trailing `"` is preceded by an unpaired `\`.
The harness's pre-condition "body is always well-formed" is silently
violated. Recommendation: re-emit the last character as `safe` if it
would land as a bare backslash.

## §4 — Per-surface raw artifacts

* `fuzz/AGGREGATE_STATS.json` — the canonical aggregate, including a
  machine-readable `findings_summary` block keyed for downstream T4
  triage consumption.
* `fuzz/<surface>/stats.json` — per-surface envelope per V3.
* `fuzz/<surface>/results.json` — the harness's own iteration log
  (crashes + oracle mismatches with `{iter, kind, msg}`).
* `fuzz/<surface>/corpus/00.txt` … `31.txt` (or `.json` for
  harness_type_errors) — 32 deterministic seed inputs per surface.
* `fuzz/_corpus_manifest.json` — surface index + seed counts.

## §5 — Deviations from task body

* **Surface-directory naming.** T2 produced `fuzz/harness_<surface>/`
  (each directory matches the harness script's `surface=` field).
  The T3 task body asked for `fuzz/<surface>/`. Renaming would orphan
  T2's `results.json` files; the T3 deliverables instead use
  `harness_<surface>/` consistently. The CORPUS_RUN.md surface table
  uses T2's names.
* **`harness_cli_format` / `harness_cli_normalize` are corpus-only.**
  T2 built only one CLI harness (`harness_cli_parse`) because the
  shipped CLI (`src/forwarded_parse/cli.py`) is stdin-only with an
  internal `parse → format` pipeline — there is no separate
  `--format` / `--normalize` CLI mode. T3 seeded corpora for the
  hypothetical surfaces for completeness but no fuzz execution applies
  to them. `stats.json` for these surfaces is `corpus_only: true`
  with `iters_clean: 0`.
* **Verdict is DIRTY (not CLEAN as the V4 template assumes).** T3
  surfaced 4 findings; per "honest progress" and the
  invariant-26 finding-forwarding contract, the cycle is DIRTY until T4
  triage + T5 remediation resolve the LIBRARY bugs. The aggregate JSON
  includes a `findings_summary` block so the T4 worker can consume it
  directly without re-reading this prose.
* **No corpus-minimized findings folders.** F-001's reproducer is a
  handful of UTF-8 strings (1–10 bytes each); `findings.jsonl` /
  `crashes/` / `hangs/` / `oom/` are empty for every surface (no
  process-level crashes). T4 may add minimized reproducers if T5
  remediation needs them.

## §6 — Branch / commit

* Branch: `wt/cycle136-adv-01` (unchanged from T1/T2)
* Files added by T3:
  * `benchmarks/adversarial/cycle_136/_seed_corpus_gen.py`
  * `benchmarks/adversarial/cycle_136/_run_corpus.py`
  * `benchmarks/adversarial/cycle_136/fuzz/_corpus_manifest.json`
  * `benchmarks/adversarial/cycle_136/fuzz/AGGREGATE_STATS.json`
  * `benchmarks/adversarial/cycle_136/fuzz/harness_*/corpus/*.txt`
    (and `.json` for `harness_type_errors`)
  * `benchmarks/adversarial/cycle_136/fuzz/harness_*/stats.json`
    (incl. corpus-only entries for `harness_cli_format` and `harness_cli_normalize`)
  * `benchmarks/adversarial/cycle_136/CORPUS_RUN.md` (this file)
* Commit: see `git log -1` after `git commit -m "adversary(cycle_136/T3): CORPUS_RUN …"` lands.

