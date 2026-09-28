# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-28

### Added
- Initial release scaffold (discoverer stage, cycle_136).
- `SPEC.md` with 12 locked acceptance criteria and RFC 7239 conformance scope.
- `seed_evidence.json` capturing `check_existing.py --keywords rfc7239` APPROVED verdict
  and HTTP 200 status for three primary sources (IETF datatracker HTML, RFC editor
  plain text, Wikipedia X-Forwarded-For).
- Build card will populate `src/`, `tests/`, and `benchmarks/`; this scaffold only.
