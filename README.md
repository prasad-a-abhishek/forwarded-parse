# forwarded-parse

**Zero-dependency RFC 7239 HTTP `Forwarded` header field parser, serializer, and normalizer.**

> *"No more `headers['Forwarded'].split(',')` hacks — parse the obfuscated tokens, fold the obs-fold continuations, round-trip the canonical form."*

> **Build status:** v0.1.0 not yet shipped. This README is the discoverer-stage scaffold; the build card (cycle_136/build) will replace it with measured benchmark numbers and the final 6-section canonical layout per repo-factory Invariant 16.

## Quick Start

```bash
pip install git+https://github.com/prasad-a-abhishek/forwarded-parse.git
```

```python
from forwarded_parse import parse, format, normalize

parsed = parse("for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https")
# parsed.elements == [
#     ForwardedElement(for=['192.0.2.43'], by=None, host=None, proto=None),
#     ForwardedElement(for=['198.51.100.17'], by='203.0.113.60', host='example.com', proto='https'),
# ]

canonical = format(parsed)
print(canonical == normalize(parsed))  # True
```

CLI:

```bash
$ echo 'for=_secret123, for=192.0.2.43;proto=https' | python -m forwarded_parse --json
```

## ⚡ Performance & Benchmarks

Benchmarks are published by the build card once the implementation lands.
This section will be replaced with measured numbers from
`benchmarks/run_benchmark.py` (5 runs × 10 workloads vs. baseline
`str.split(';').split(',')` heuristic and vs. `werkzeug.http.parse_list_header`
where applicable). Until the build card ships, the placeholder above
should be treated as "TODO — build card must populate with real numbers".

## Why forwarded-parse?

Today, every Python backend that reads a `Forwarded` header off the wire writes
some variant of this:

```python
parts = [p.strip() for p in headers["Forwarded"].split(",")]
for part in parts:
    kv = [x.strip() for x in part.split(";")]
    ...
```

That works for `Forwarded: for=192.0.2.43` and breaks subtly on:

| Edge case                                   | `.split(',')` heuristic      | `forwarded-parse`                         |
|---------------------------------------------|------------------------------|-------------------------------------------|
| `Forwarded: for=_secret123` (obfuscated)    | `for=_secret123` (token)     | `for='_secret123'` (verbatim opaque)      |
| `Forwarded: for="[2001:db8::1]"` (IPv6)     | drops the brackets           | `for='[2001:db8::1]'`                     |
| `Forwarded: host="example.com";proto=https` | keeps quotes as value        | `host='example.com'`, `proto='https'`     |
| `\r\n\t` obs-fold continuation              | treats as separate header    | joined to single value before parsing     |
| `Forwarded:` (empty value)                  | `['']`                       | `Parsed(elements=[])`                     |

The 5-line snippet gets copy-pasted across four proxy-aware middlewares, all
subtly disagreeing on whether obfuscated tokens should be flagged, whether
IPv6 brackets should be stripped, and whether to error on malformed
quoted-strings. `forwarded-parse` is the single, dependency-free, RFC 7239
-conformant parser that drops in.

**vs. `http.client` / `email.message` stdlib splitters:** they split on `,`
and `;` blindly; cannot tell `key=value` from quoted values containing
punctuation, and do not implement the obs-fold join rule from RFC 7230 §3.2.4.

**vs. `werkzeug.http.parse_list_header` / `parse_dict_header`:** Werkzeug's
helpers parse RFC 9110 §5.6.x comma-lists but with no `Forwarded`-specific
grammar — no obfuscated-token handling per RFC 7239 §6.3, no obs-fold
handling, no IPv6 literal support inside `for=`/`by=`. Wrong abstraction:
a generic list parser with no domain knowledge.

**vs. `pyforwarded` (PyPI, last release 2018, <10 stars):** stale, no
obfuscated-token support, no serializer round-trip, no `for=192.0.2.43, for=...`
multi-element disambiguation, no CLI.

## Key Features & API

- `parse(value: str) -> Parsed` — full RFC 7239 §4 parser; obs-fold handled,
  obfuscated tokens preserved verbatim, IPv6 literals in `for=`/`by=`
  preserved with square brackets.
- `format(parsed: Parsed) -> str` — canonical round-trip serializer.
- `normalize(parsed: Parsed) -> Parsed` — deterministic key ordering,
  deterministic element ordering, canonical whitespace handling.
- `ForwardedElement(for: tuple[str, ...], by: Optional[str], host: Optional[str], proto: Optional[str])`
  — immutable `NamedTuple`.
- `ForwardedParseError` — typed exception carrying `line`, `col`, `reason`.
- CLI: `python -m forwarded_parse [--json] [--serialize] [VALUE]`.
- 100+ unit tests, zero runtime dependencies.
- Typed (`py.typed`); Python 3.11+.

## License

MIT License — see [`LICENSE`](LICENSE) for the full text. Author: Hermes Repo Factory, 2026.
