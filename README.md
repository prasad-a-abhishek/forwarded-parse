# forwarded-parse

[![PyPI version](https://img.shields.io/badge/version-0.1.1-blue.svg)](https://github.com/prasad-a-abhishek/forwarded-parse)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#dependencies)

**Zero-dependency RFC 7239 HTTP `Forwarded` header parser, serializer, and normalizer.**

> *"Stop writing `headers['Forwarded'].split(',')` — parse obs-fold, quoted-strings, and obfuscated tokens the RFC 7239 way."*

## Quick Start

```bash
pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git
```

```python
from forwarded_parse import parse, format, normalize

parsed = parse("for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https")
# parsed.elements == (
#     ForwardedElement(for_=('192.0.2.43',), by='203.0.113.60', host='example.com', proto='https'),
#     ForwardedElement(for_=('198.51.100.17',), by=None, host=None, proto=None),
# )

print(format(parsed))
# -> 'for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https'

print(normalize(parsed) == parsed)  # True — already canonical
```

CLI:

```bash
$ echo 'for=_secret123, for=192.0.2.43;proto=https' | python -m forwarded_parse --json
{
  "elements": [
    {"for": ["_secret123"], "by": null, "host": null, "proto": null},
    {"for": ["192.0.2.43"], "by": null, "host": null, "proto": "https"}
  ]
}
```

## ⚡ Performance & Benchmarks

| Workload | forwarded-parse | naive `str.split(',')` |
|----------|----------------:|-----------------------:|
| single `for=ipv4` | 7.5 µs | 0.2 µs |
| obfuscated token `for=_secret` | 4.7 µs | 0.1 µs |
| single element, all four keys | 15.1 µs | 0.1 µs |
| 4-hop proxy chain | 18.0 µs | 0.2 µs |
| quoted `host="example.com"` | 11.2 µs | 0.1 µs |
| IPv6 literal `for="[2001:db8::1]"` | 8.4 µs | 0.1 µs |
| obs-fold `for=a,\r\n for=b` | 16.4 µs | 0.1 µs |
| `for=` chained 4 times | 8.5 µs | 0.1 µs |
| 8-element mixed | 43.1 µs | 0.2 µs |

**Honest interpretation:** naive `str.split(',')` is faster in absolute terms
because it returns an unstructured list of strings. forwarded-parse is slower
by tens of microseconds because it returns a typed `Forwarded` object that
implements obs-fold handling, quoted-string parsing, and obfuscated-token
preservation — features naive splitting cannot express. Both are negligible
compared to TLS termination or JSON serialisation on a real request path.

Reproduce:

```bash
python3 benchmarks/run_benchmark.py
```

See [`benchmarks/BENCHMARK.md`](benchmarks/BENCHMARK.md) for full methodology.

## Why forwarded-parse?

When a request passes through one or more proxies, load balancers, or CDNs,
the origin server needs the originating client IP, the protocol spoken by the
client, and the `Host` header seen by the first proxy. The de-facto
`X-Forwarded-For` header carries only the IP chain. RFC 7239 standardises the
richer `Forwarded` header:

```
Forwarded: for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https
```

Python's standard library does not parse this header:

- `http.client.HTTPMessage` and `email.message.Message` only split on `,` and
  `;` without recognising the `key=value` token grammar.
- `wsgiref.headers.Headers` is a writer, not a parser.
- `werkzeug.http.parse_list_header` and `parse_dict_header` are WSGI helpers
  that do not implement the RFC 7239 ABNF (no obs-fold handling, no
  obfuscated token form `:_obfuscated_value`).

| Edge case | naive `str.split(',')` | `forwarded-parse` |
|-----------|------------------------|-------------------|
| `Forwarded: for=192.0.2.43` | `['for=192.0.2.43']` | `ForwardedElement(for_=('192.0.2.43',), …)` |
| `Forwarded: for=_secret123` (obfuscated) | `['for=_secret123']` (loses structure) | `ForwardedElement(for_=('_secret123',), …)` (preserved verbatim) |
| `Forwarded: for=a,\r\n for=b` (obs-fold) | `['for=a', '\r\n for=b']` (broken) | `[ForwardedElement(for_=('a',)), ForwardedElement(for_=('b',))]` (joined per RFC 7230 §3.2.4) |
| `Forwarded: host="example.com"` | `['host="example.com"']` (raw) | `host='example.com'` (quotes stripped) |
| `Forwarded: for=a;for=b;for=c` (chained) | `['for=a;for=b;for=c']` (collapsed) | `ForwardedElement(for_=('a', 'b', 'c'), …)` (per RFC 7239 §6.3) |
| `Forwarded: for=[2001:db8::1]` (IPv6) | `['for=[2001:db8::1]']` (raw) | `for_=('[2001:db8::1]',)` (preserved through quoted-form) |

**vs. `werkzeug.http.parse_list_header`:** parses comma-separated lists but
has no `Forwarded`-specific grammar — no obs-fold, no obfuscated tokens, no
key=value awareness. Wrong abstraction: a generic list parser with no
domain knowledge.

**vs. `pyforwarded` (PyPI, no releases since 2018, <10 stars):** stale, no
obfuscated-token support, no serializer round-trip.

**vs. rolling your own:** every backend that needs the client IP ends up
writing a slightly different splitter. `forwarded-parse` is the single
RFC 7239-conformant parser with a typed `Forwarded` object and round-trip
`format()` serializer.

## Key Features & API

- `parse(value: str) -> Forwarded` — full RFC 7239 §4 parser. Accepts a
  single `Forwarded` header field value; obs-fold is joined before parsing.
  Raises `ForwardedParseError` on malformed input.
- `format(parsed: Forwarded) -> str` — canonical round-trip serializer
  (RFC 7239 §7 examples). Round-trip property:
  `format(parse(h)) == format(parse(format(parse(h))))`.
- `normalize(parsed: Forwarded) -> Forwarded` — deterministic ordering
  (for-chains preserved in input order; known keys emitted in canonical
  order: `for` / `by` / `host` / `proto`).
- `Forwarded(elements: tuple[ForwardedElement, ...])` — frozen dataclass.
- `ForwardedElement(for_: tuple[str, ...], by: str | None, host: str | None, proto: str | None)`
  — frozen dataclass; `for_` carries the chain from one forwarding element.
- `ForwardedParseError` — `ValueError` subclass with `reason` and `position`.
- CLI: `python -m forwarded_parse [--json] < header.txt` — canonical output
  to stdout (or JSON with `--json`).
- Obs-fold handling (RFC 7230 §3.2.4) — `CRLF` + SP/HTAB joined before parsing.
- Obfuscated-token preservation (RFC 7239 §6.3) — `for=_anything` preserved
  verbatim as opaque token.
- IPv4 and IPv6 literal support — IPv6 in quoted-string form.
- Quoted-string values (RFC 7230 §3.2.6) for `host=` and `proto=` with
  backslash-escape resolution.
- Typed (`py.typed` marker included); Python 3.11+.
- **Zero runtime dependencies** — `dependencies = []`.

### Full example

```python
from forwarded_parse import parse, format, normalize, ForwardedElement, Forwarded

# Parse the RFC 7239 §7 example chain
header = (
    "for=192.0.2.43, "
    "for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https, "
    "for=_obfuscated;by=_proxy"
)
parsed = parse(header)
assert len(parsed.elements) == 3
assert parsed.elements[0].for_ == ("192.0.2.43",)
assert parsed.elements[1].by == "203.0.113.60"
assert parsed.elements[1].host == "example.com"
assert parsed.elements[1].proto == "https"
assert parsed.elements[2].for_ == ("_obfuscated",)
assert parsed.elements[2].by == "_proxy"

# Round-trip
reparsed = parse(format(parsed))
assert format(reparsed) == format(parsed)

# Normalize (idempotent on already-canonical input)
assert normalize(parsed) == parsed
```

### Errors

```python
from forwarded_parse import parse, ForwardedParseError

try:
    parse('for="unterminated')
except ForwardedParseError as exc:
    print(exc.reason, exc.position)
    # -> 'unterminated quoted-string' 0
```

### Install

```bash
pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git
```

(No PyPI release at v0.1.1 — install from the git repo. The first PyPI
release will be tagged from this commit.)

For local development:

```bash
git clone https://github.com/prasad-a-abhishek/forwarded-parse.git
cd forwarded-parse
pip install -e .
pytest -q
```

### Dependencies

**Zero runtime dependencies.** `dependencies = []` in `pyproject.toml`. The
package uses only the Python standard library (`dataclasses`, `typing`).

Build backend: `setuptools >= 61.0`, `wheel` (already in any modern Python
environment).

## License

MIT License — see [`LICENSE`](LICENSE) for the full text.
Author: Hermes Repo Factory, 2026.
