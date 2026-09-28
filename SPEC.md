# forwarded-parse — SPEC

## 1. Title & one-line summary

**forwarded-parse** — pure-Python, zero-dependency RFC 7239 `Forwarded` HTTP header parser, serializer, and normalizer.

## 2. Problem statement

When a request passes through one or more proxies, load balancers, or CDNs, the
origin server needs a way to learn the originating client IP, the protocol
spoken by the client, and the `Host` header seen by the first proxy. The
de-facto `X-Forwarded-For` header carries the IP chain but lacks a formal
grammar and supports only one piece of information per header instance. RFC
7239 standardises this as the `Forwarded` header:

```
Forwarded: for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https, for=192.0.2.43
```

Python's standard library does not parse this header:

* `http.client.HTTPMessage` and `email.message.Message` only split on `,`
  and `;` without recognising the `key=value` token grammar.
* `wsgiref.headers.Headers` is a writer, not a parser.
* `werkzeug.http.parse_list_header` and `parse_dict_header` are WSGI helpers
  that do not implement the RFC 7239 ABNF (no obs-fold handling, no
  obfuscated token form `:_obfuscated_value`).

`forwarded-parse` fills this gap with a focused, dependency-free library
that parses the `Forwarded` header into a structured `Parsed` object,
serialises it back to canonical form, and normalises ordering.

## 3. Target user (one sentence)

Backend Python developers who write reverse-proxy-aware request handlers,
load-balancer health checks, audit-log middlewares, or rate-limiters that
must read the RFC 7239 `Forwarded` header correctly without pulling in a
full web framework.

## 4. Competitor analysis

| Library | Why not |
|---|---|
| `werkzeug.http.parse_list_header` | Part of Werkzeug; no `Forwarded`-specific grammar; ships a heavy WSGI stack as transitive dependency. |
| `requests`-internal `CaseInsensitiveDict` | Container only; no header-value parser. |
| `pyforwarded` (PyPI, no releases since 2018, <10 stars) | Stale, no obfuscated-token support, no serializer round-trip. |
| `django.utils.http.parse_http_datetime_safe` | Date parser only, irrelevant domain. |
| `http.client` stdlib splitter | Splits on `,` and `;` blindly; cannot tell `key=value` from quoted values containing punctuation. |

No widely-starred, actively maintained, RFC-7239-faithful pure-Python
parser exists on PyPI or GitHub.

## 5. Scope

### 5.1 In scope (this repo)

* `parse(header: str) -> Parsed` — accept a single `Forwarded` header field value (possibly folded across multiple lines via obs-fold), return a list of `ForwardedElement` records (one per comma-separated forwarding element).
* `format(parsed) -> str` — canonical round-trip serializer.
* `normalize(parsed) -> Parsed` — deterministic ordering of keys within each element, deterministic ordering of `for=` entries, with stable whitespace handling.
* CLI: `python -m forwarded_parse < header.txt` prints the canonical normalised form to stdout (one element per line, JSON-shaped output via `--json`).
* Obs-fold handling (`\r\n\t` or `\r\n ` continuation runs are joined).
* Obfuscated token form: `for=_quoted;by=_xy1234` — detect leading underscore after `=` and preserve verbatim as opaque token.
* IPv4 and IPv6 literal support for `for=` and `by=` (IPv6 in square brackets).
* Quoted-string values (RFC 7230 §3.2.6) for `host=` and `proto=`.
* Strict errors via custom `ForwardedParseError` carrying line/column + reason.

### 5.2 Out of scope (non-goals)

* Not an HTTP request parser — caller passes the header value as a string.
* Not a writer of arbitrary HTTP responses.
* Not a wrapper around any stdlib (`http.client`, `email.message`, `urllib`).
* No IP geolocation, no trust scoring, no rate-limit decision logic.
* No `X-Forwarded-For` legacy header parser (different grammar; could be a sibling repo later).

## 6. Public API surface

```python
from forwarded_parse import parse, format, normalize, ForwardedElement, ForwardedParseError

parsed = parse("for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https")
# parsed.elements == [ForwardedElement(for=['192.0.2.43'], by='203.0.113.60', host='example.com', proto='https'),
#                     ForwardedElement(for=['198.51.100.17'], by=None, host=None, proto=None)]
print(format(parsed))            # canonical round-trip
print(normalize(parsed) == parsed)  # True (already canonical)
```

CLI:

```
$ echo 'for=_secret123, for=192.0.2.43;proto=https' | python -m forwarded_parse --json
```

## 7. Implementation budget

* Total implementation LOC ≤ 400 (state-machine parser + serializer + CLI).
* Total test LOC ≥ 1,500.
* `dependencies = []` in `pyproject.toml`.

## 8. Primary sources (≥3 fetched URLs, all HTTP 200 verified 2026-09-27)

| URL | Source | HTTP status |
|---|---|---|
| https://datatracker.ietf.org/doc/html/rfc7239 | IETF datatracker HTML | 200 |
| https://www.rfc-editor.org/rfc/rfc7239.txt | RFC editor plain text | 200 |
| https://en.wikipedia.org/wiki/X-Forwarded-For | Wikipedia — `X-Forwarded-For` predecessor & migration to `Forwarded` | 200 |

## 9. Acceptance criteria (12 LOCKED ACs)

| AC | Description | Verification method |
|---|---|---|
| AC1 | `from forwarded_parse import parse` works in a fresh venv after `pip install -e .` | pytest `test_import_smoke` |
| AC2 | `parse("for=192.0.2.43")` returns exactly one `ForwardedElement` with `for=['192.0.2.43']` and all other fields `None` | pytest `test_canonical_single` |
| AC3 | RFC 7239 §6.3 obfuscated token form `for=_quoted;by=_xy1234` parses without error and preserves the leading-underscore token verbatim as opaque string (no error, no normalisation) | pytest `test_obfuscated_token` |
| AC4 | RFC 7230 obs-fold handling: a `\r\n\t` continuation inside the header value is joined before parsing and produces the same result as the unfolded header | pytest `test_obs_fold` |
| AC5 | Multiple comma-separated elements parse to a list of N `ForwardedElement` records in input order | pytest `test_multi_element_chain` |
| AC6 | Quoted-string values for `host=` and `proto=` parse with surrounding double-quotes stripped; backslash-escapes resolved per RFC 7230 §3.2.6 | pytest `test_quoted_string_values` |
| AC7 | `format(parse(h))` round-trips to canonical form on every example in the RFC 7239 §7 reference grammar | pytest `test_rfc7239_section7_examples` |
| AC8 | CLI smoke: `python -m forwarded_parse --json < fixture.txt` produces valid JSON with `elements` list | pytest `test_cli_json_smoke` |
| AC9 | Fresh-venv install + `pytest -q` shows ≥100 collected tests, all passing, exit 0 | CI script `scripts/ci_fresh_venv.sh` |
| AC10 | Fuzz harness (`fuzz_parse.py`) runs ≥100,000 iterations across obs-fold / quoted / obfuscated / multi-element corpora with zero crashes, zero oracle mismatches against the canonical formatter | `benchmarks/fuzz_report.md` |
| AC11 | Secret scan (`git grep -E 'ghp_\|pypi-AgEI\|npm_\|sk-\|AKIA\|Bearer ey\|BEGIN PRIVATE KEY'`) returns 0 matches across `src/`, `tests/`, `benchmarks/`, `README.md` | `scripts/secret_scan.sh` |
| AC12 | `pyproject.toml` has `dependencies = []`; `README.md` follows the canonical 6-section order; `LICENSE` is MIT; `CHANGELOG.md` has a `## v0.1.0 — YYYY-MM-DD` entry | `scripts/invariant_check.sh` |

## 10. Compliance invariants

* Zero runtime dependencies (`dependencies = []`).
* Implementation LOC ≤ 400.
* Test count ≥ 100 (floor for `forwarded-parse` is `pytest --collect-only -q` count ≥ 100).
* `pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git` documented as the install path (no PyPI release at v0.1.0).
* README follows the canonical 6-section structure (Title+badges / Quick Start / Performance / Why / Features+API / License).

## 11. Anti-patterns (DO NOT)

* ❌ Wrap `http.client`, `email.message`, or any stdlib header parser.
* ❌ Vendor a third-party `Forwarded` library.
* ❌ Add an LLM-powered "explain this chain" feature.
* ❌ Add `X-Forwarded-For` parsing (out of scope; sibling repo later).
* ❌ Skip the canonical `format()` round-trip AC (AC7).
* ❌ Cite a URL without first `curl -I`-verifying it returns 200.

## 12. Non-goals (re-stated, locked)

* No `X-Forwarded-For` parser.
* No HTTP request/response parser.
* No IP reputation or geolocation.
* No proxy chain reasoning beyond the literal `Forwarded` content.
