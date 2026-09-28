# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0 — 2026-09-27

### Added
- Initial public release of `forwarded-parse` — pure-Python, zero-dependency
  RFC 7239 `Forwarded` HTTP header parser, serializer, and normalizer.
- `parse(value: str) -> Forwarded` — full RFC 7239 §4 parser with obs-fold
  handling (RFC 7230 §3.2.4), quoted-string values (RFC 7230 §3.2.6), and
  obfuscated-token preservation (RFC 7239 §6.3).
- `format(parsed: Forwarded) -> str` — canonical round-trip serializer.
  Round-trip property verified: `format(parse(h)) == format(parse(format(parse(h))))`.
- `normalize(parsed: Forwarded) -> Forwarded` — deterministic ordering of
  elements and within each element (`for` / `by` / `host` / `proto`).
- `Forwarded` and `ForwardedElement` — frozen, slotted dataclasses with
  `to_dict()` helpers for JSON serialisation.
- `ForwardedParseError(ValueError)` — typed exception with `reason` and
  `position` attributes.
- CLI: `python -m forwarded_parse [--json]` — reads a Forwarded header from
  stdin, writes canonical form (or JSON with `--json`) to stdout.
- 331 pytest tests across 13 test modules covering canonical, obs-fold,
  quoted-string, obfuscated-token, multi-element, for-chaining,
  round-trip, error, edge-case, CLI, fresh-venv smoke, and RFC 7239 §7
  reference examples.
- `benchmarks/run_benchmark.py` — reproducible 50-iteration benchmark
  against naive `str.split(',')` baseline across 10 workload profiles.
- `py.typed` marker; `pyproject.toml` with `dependencies = []`.
- README follows the canonical 6-section structure (Title+badges, Quick
  Start, Performance, Why forwarded-parse?, Key Features & API, License).

## v0.1.1 — 2026-09-28

Patch release closing 2 HIGH-severity adversarial findings surfaced by
cycle_136's `@repo-adversary` workstream.

### Fixed
- **F-001** (HIGH, library bug, 1620 hits): idempotence violation on
  unknown-key-only elements. `parse("foo=bar")` previously returned a
  phantom `ForwardedElement` with `for_=()` and `by/host/proto=None`;
  now returns `Forwarded(elements=())` per RFC 7239 §4's
  unknown-extension rule, mirroring `_parse_pair()`'s `None` return
  for unknown-key pairs. Fix is in `src/forwarded_parse/_parser.py`
  `_parse_element()` (one new guard after the pair loop).
- **F-004** (HIGH, CLI symptom, 44 hits): CLI empty stdout on
  all-unknown inputs. Same root cause as F-001; closing the library
  bug eliminates the symptom. The CLI's existing `if out: write`
  guard is intentionally left intact — `format()` now correctly
  returns `''` for legitimate empty inputs.

### Tests
- New `tests/test_idempotence_unknown_key_only.py` — 13 tests covering
  library-level drop semantics, `format()` empty output, AC7 round-trip
  idempotence on all-unknown inputs, `normalize()` identity, known-key
  preservation, mixed real+phantom elements, and CLI stdout behaviour
  for both default and `--json` modes.

### Compatibility
- No public API breakage. `parse("foo=bar")` previously returned a
  phantom element; it now returns an empty `Forwarded`. Callers that
  iterated `.elements` looking for `for_` content see the same outcome
  in both shapes because phantom elements always had `for_=()`.
- `dependencies = []` unchanged.
- README unchanged (no user-facing contract change).

### Cross-check
Regenerated adversarial fuzz against `harness_format_main`,
`harness_normalize_main`, and `harness_cli_parse` shows zero
oracle-mismatches after the fix.
