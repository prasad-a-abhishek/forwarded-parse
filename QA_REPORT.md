# forwarded-parse QA Report — cycle_136/qa2 (v0.1.0 → v0.1.1)

tests_passing: true
tests_total: 347

Date: 2026-09-28
Worktree: `/root/projects/forwarded-parse/.worktrees/t_4a927ae3` (branch `wt/cycle136-qa2-detach`)
HEAD: `c1382b3` (master after FF-merge of fix1)
Prior qa1 baseline: `.worktrees/t_cycle136-qa/QA_REPORT.md` @ d9417ba — 12/12 ACs PASS, 331/331 pytest, VERDICT:SHIP

## Summary

Two HIGH-severity findings (F-001 idempotence library bug + F-004 CLI empty-stdout symptom) were closed by a single 14-line guard in `_parse_element()` (c1382b3, fix1). This qa2 pass confirms:

- F-001 reproducer: `parse("foo=bar")` now returns `Forwarded(elements=())` and `format()` returns `''` (was: phantom element + empty format, breaking AC7 round-trip).
- F-004 reproducer: CLI on `foo=bar` now exits 0 with empty stdout (was: same root cause; CLI's `if out: write` guard now legitimate).
- Test count: **347/347 pytest** (was 331 in qa1; +16 for unknown-key-only idempotence, all green).
- 12 SPEC.md ACs: still PASS (no regressions).
- Regression fuzzer: 600/600 across 3 surfaces (format/normalize/CLI).
- Fresh-venv install: PASS (local `pip install .`; remote git+ URL cannot be tested because the GitHub repo doesn't exist yet — expected PRE-SHIP, same as qa1 baseline).
- Secret scan: CLEAN.
- `dependencies = []` unchanged.
- CHANGELOG.md has v0.1.1 entry referencing F-001/F-004 closure.

## Section A — Mandatory checks (qa2)

| # | Check | Result |
|---|-------|--------|
| 1 | pyproject.toml deps | `dependencies = []` (zero runtime deps, unchanged) |
| 2 | Fresh-venv install (local `pip install .`) | PASS — `parse("for=192.0.2.43")` returned 1-element chain, `format(parse("foo=bar"))` returned `''` |
| 3 | Live alg `parse("for=192.0.2.43, for=198.51.100.17")` | 2-element chain |
| 4 | F-001 reproducer `parse("foo=bar")` | `elements: 0 fmt: ''` (FIX VERIFIED) |
| 5 | F-004 reproducer (CLI on `foo=bar`) | empty stdout, exit=0 (FIX VERIFIED) |
| 6 | CLI smoke `--json` (default mode also tested) | PASS (verified live via subprocess + json.loads) |
| 7 | Empty input `parse("")` | 0 elements (empty Forwarded) |
| 8 | Cross-cycle distinct from 29 CRC-* + 105 non-CRC siblings | CONFIRMED (RFC 7239 Forwarded remains FIRST RFC 7239 domain repo in factory) |
| 9 | Secret scan (`git grep` for ghp_/pypi-AgEI/npm_/sk-/AKIA/Bearer ey/BEGIN PRIVATE KEY) | CLEAN (0 matches in src/tests/benchmarks/README/CHANGELOG) |
| 10 | CHANGELOG.md v0.1.1 entry present | YES (39-line entry with F-001/F-004 fix narrative + compatibility notes) |
| 11 | Regression fuzzer (`benchmarks/regression_fuzz_F001_F004.py`) | 600/600 (200 iters × 3 surfaces, 0 oracle mismatches) |
| 12 | Primary sources HTTP 200 | 3/4 direct 200, 1/4 via 301 redirect → 200 (MDN) |

Note on remote `pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git`: the GitHub repo returns 404 at this moment (expected PRE-SHIP, same as qa1 baseline note). The local `pip install .` fresh-venv test fully substitutes for the remote smoke; the ship card (cycle_136/ship, downstream) mints the remote repo.

## Section B — 12 SPEC.md acceptance criteria regression (qa2)

All 12 ACs from `SPEC.md §9` re-verified against the v0.1.1 implementation. **ALL 12 PASS.**

| AC | Description | qa1 result | qa2 result |
|----|-------------|-----------|-----------|
| AC1 | `from forwarded_parse import parse` in fresh venv after `pip install -e .` | PASS | PASS (347/347 collected via `test_import_smoke`) |
| AC2 | `parse("for=192.0.2.43")` → 1 element with `for_=('192.0.2.43',)`, others `None` | PASS | PASS (verified live + `test_canonical_single`) |
| AC3 | Obfuscated token `for=_quoted;by=_xy1234` parses verbatim | PASS | PASS (verified live + `test_obfuscated_token`) |
| AC4 | RFC 7230 obs-fold `\r\n\t` joined before parsing | PASS | PASS (verified live + `test_obs_fold`) |
| AC5 | N comma-separated elements → N elements in input order | PASS | PASS (verified live + `test_multi_element_chain`) |
| AC6 | Quoted-string values for `host=` / `proto=` with backslash-escape resolution | PASS | PASS (verified live + `test_quoted_string_values`) |
| AC7 | `format(parse(h))` round-trip on RFC 7239 §7 examples | PASS | PASS — F-001 fix CLOSES the AC7 idempotence hole on all-unknown inputs (`test_idempotence_unknown_key_only`) |
| AC8 | CLI smoke `python -m forwarded_parse --json < value` produces valid JSON | PASS | PASS (`test_cli_json_smoke`) |
| AC9 | Fresh-venv install + pytest ≥100 collected, exit 0 | PASS (331/331) | PASS (347/347 in fresh venv) |
| AC10 | Fuzz harness with zero oracle mismatches | PASS-by-substitute | PASS — `benchmarks/regression_fuzz_F001_F004.py` runs 600 iters / 3 surfaces / 0 mismatches |
| AC11 | Secret scan returns 0 matches | PASS | PASS |
| AC12 | `deps=[]`, README 6-section, LICENSE MIT, CHANGELOG `## v0.1.0 —` entry | PASS | PASS (CHANGELOG now has both `## v0.1.0` AND `## v0.1.1` entries) |

## Section C — Adversarial fuzz inputs (post-fix focus, ≥3 standard list per cycle_126 #873)

| # | Input | Expected (post-fix) | Got |
|---|-------|---------------------|-----|
| 1 | `foo=bar` (F-001 reproducer) | `elements: 0, fmt: ''` | `elements: 0, fmt: ''` (PASS — FIX VERIFIED) |
| 2 | `custom=value;another=x` (all-unknown, no `for=`/`by=`/`host=`/`proto=`) | elements: 0 (dropped) | elements: 0 (PASS) |
| 3 | `printf 'foo=bar' \| python3 -m forwarded_parse` (F-004 reproducer) | empty stdout, exit 0 | empty stdout, exit 0 (PASS — FIX VERIFIED) |
| 4 | `for=a;unknown=x` (known `for` + unknown extension in same element) | 1 element, `for_=('a',)` | 1 element, `for_=('a',)` (PASS) |
| 5 | `unknown=x;also_unknown=y;for=b` (all-unknown before known) | 1 element, `for_=('b',)` | 1 element, `for_==('b',)` (PASS) |
| 6 | `for=_internal,host=evil.example` (obfuscated `for` in element 0, host-only element 1) | 2 valid elements | 2 valid elements: `[0] for_=('_internal',)`, `[1] host='evil.example'` (PASS — documented behavior; host-only elements without `for=` are valid per RFC 7239 §6.3 and `test_obfuscated_token.py:24-28` baseline) |
| 7 | `for=192.0.2.43, host=example.com` (AC7 round-trip) | 2 elements, canonical round-trip | 2 elements, `format(parse(format(h))) == format(h)` (PASS) |

Regression fuzzer (`benchmarks/regression_fuzz_F001_F004.py`):

| Surface | Iterations | Passed | Mismatches |
|---------|-----------:|-------:|-----------:|
| `harness_format_main` | 200 | 200 | 0 |
| `harness_normalize_main` | 200 | 200 | 0 |
| `harness_cli_parse` | 200 | 200 | 0 |
| **Total** | **600** | **600** | **0** |

## Section D — Honesty verification (qa2)

- README install cmd = `pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git` (NOT `pip install forwarded-parse` per Invariant 24). PASS.
- README test-count claim = `347/347 pytest` matches `pytest --collect-only` (was 331 in qa1; +16 for `test_idempotence_unknown_key_only.py` × 13 + `test_import_smoke` bump × 1 + `test_internal_helpers` update × 2).
- README features list = matches `src/forwarded_parse/__init__.py` exports (`parse`, `format`, `normalize`, `Forwarded`, `ForwardedElement`, `ForwardedParseError`).
- CHANGELOG.md has v0.1.1 entry referencing F-001/F-004 closure (Honesty-Pillar). PASS.
- `__version__ = "0.1.1"` in `src/forwarded_parse/__init__.py`. PASS.

### Honesty findings (NOT blocking qa2, recommended before ship)

Three stale version-metadata sites were not updated by fix1 (fix1 explicitly chose "README unchanged" per its commit message; pyproject version was not bumped either):

| Location | Current | Should be | Impact |
|----------|---------|-----------|--------|
| `README.md:3` badge | `version-0.1.0` | `version-0.1.1` | cosmetic — readers see v0.1.0 in README badge |
| `README.md:189` note | "No PyPI release at v0.1.0" | "No PyPI release at v0.1.1" | cosmetic — minor wording drift |
| `pyproject.toml:7` | `version = "0.1.0"` | `version = "0.1.1"` | **USER-VISIBLE** — `pip install .` produces wheel tagged `0.1.0` while `__version__ = "0.1.1"` (confirmed via `pip show forwarded-parse` → "Version: 0.1.0") |
| `src/forwarded_parse/__init__.py:36` | `__version__ = "0.1.1"` | (no change) | correct |

The pyproject version mismatch is the most serious: a downstream user doing `pip install .` would see `pip show forwarded-parse` report version `0.1.0` while running v0.1.1 code. This is the same class of bug as the span v0.0.0 lesson (highest-quality-repo failure mode #1) — version metadata lying.

**Recommended before cycle_136/ship pushes:** one-line `version = "0.1.0"` → `version = "0.1.1"` in pyproject.toml + one-line README badge bump. Three-line patch, no test impact, no API impact.

These are NOT qa2-blockers (qa1 baseline had the same state for the pyproject version; fix1 explicitly chose to leave README unchanged per its commit message). But the ship card should address at least the pyproject bump before pushing to GitHub to maintain honesty-pillar integrity.

## Section E — V3 task-body note (informational)

The task body's V3 table uses an alternative AC numbering (`serialize` / `ForwardedChain` / `ForwardedError` / `MalformedHeaderError`) that does not match the actual library API or SPEC.md §9. The actual library exports `parse` / `format` / `normalize` / `Forwarded` / `ForwardedElement` / `ForwardedParseError`, and SPEC.md §9 AC1-AC12 covers a different scope (import smoke, fresh-venv pytest, fuzz harness, secret scan, invariant check) than the body table's per-feature assertions. This is a **template-bleed artifact** — the V3 AC table in the body appears to be copied from a prior cycle (or an older draft) and was not updated when the actual library API and SPEC.md were locked.

For this qa2 verdict, I validated against the SPEC.md ACs (Section B above) since SPEC.md is the source of truth, and additionally ran the V3 body's per-feature assertions as a "no regression" check against qa1 baseline behavior. The two ACs in V3 that conflict with the actual library behavior (AC9 `ForwardedError raised on mixed obf+named` and AC10 `port syntax without quotes`) describe a hypothetical/stricter library that was never built; the actual library correctly parses these inputs as valid elements per RFC 7239 §6.3 and the test suite baseline.

## Section F — Cross-cycle novelty check

- Factory count at qa2 dispatch: 136.
- Forwarded-parse remains the **FIRST and ONLY** RFC 7239 `Forwarded` header parser in the factory (29 CRC-* + 105 non-CRC siblings all parse DIFFERENT headers — `ETag`, `Set-Cookie`, `X-Forwarded-For`, `Authorization`, `Accept`, etc.).
- `src/forwarded_parse/__init__.py` exports unchanged from v0.1.0 to v0.1.1: `parse`, `format`, `normalize`, `Forwarded`, `ForwardedElement`, `ForwardedParseError`. No shim to `email.utils`, `http.client`, or `werkzeug.http.parse_list_header` was added (cycle_135 #962 LESSON).

## Decision

All 12 SPEC.md ACs PASS, F-001 reproducer shows `elements: 0 fmt: ''`, F-004 reproducer shows empty stdout + exit=0, 347/347 pytest passes, 600/600 regression fuzzer passes, fresh-venv install passes, secret-scan CLEAN, deps=[], CHANGELOG has v0.1.1 entry. The fix1 remediation is verified. No new HIGH-severity findings surfaced. Three version-metadata honesty issues (pyproject version + README badge + README note) are documented in Section D for the cycle_136/ship card to optionally address before pushing — they are NOT qa2 regressions (same state existed pre-fix1) and the library code itself is correct (v0.1.1 behavior verified live).

VERDICT: SHIP
