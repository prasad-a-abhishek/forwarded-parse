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
