# Benchmarks — forwarded-parse

Reproducible benchmark comparing **forwarded-parse v0.1.0** against the
naive `str.split(',')` baseline that most Python backends ship today.

## How to reproduce

```bash
pip install -e .
python3 benchmarks/run_benchmark.py
```

Outputs:
- `benchmarks/BENCHMARK.json` — raw timings (5 iterations x 10 workloads)
- stdout — markdown table summary

## Methodology

- 3 warmup runs (not counted)
- 5 timed runs per workload per package (50 total per package)
- Wall-clock via `time.perf_counter_ns()`
- Python 3.11.15 on Linux x86_64

## Workload profiles

| # | Profile | What it covers |
|---|---|---|
| 1 | `single_for_ipv4` | Minimal `for=` only |
| 2 | `single_for_obfuscated` | RFC 7239 §6.3 obfuscated token (leading underscore) |
| 3 | `single_element_full_keys` | All four canonical keys in one element |
| 4 | `two_elements_chained` | Two-element header |
| 5 | `four_elements_chain` | Four-hop proxy chain |
| 6 | `quoted_host` | `host=` and `proto=` as quoted-strings |
| 7 | `ipv6_literal` | IPv6 addresses (require quoting per RFC 7230) |
| 8 | `obs_folded` | CRLF + SP continuation inside header value |
| 9 | `for_chained_four` | Four `for=` values inside one element (RFC 7239 §6.3) |
| 10 | `multi_element_long` | 8-element header, mixed obfuscated + plain |

## Results (mean microseconds, lower is better)

| Workload | forwarded-parse | naive split |
|----------|----------------:|------------:|
| single_for_ipv4 | 7.5 | 0.2 |
| single_for_obfuscated | 4.7 | 0.1 |
| single_element_full_keys | 15.1 | 0.1 |
| two_elements_chained | 9.6 | 0.1 |
| four_elements_chain | 18.0 | 0.2 |
| quoted_host | 11.2 | 0.1 |
| ipv6_literal | 8.4 | 0.1 |
| obs_folded | 16.4 | 0.1 |
| for_chained_four | 8.5 | 0.1 |
| multi_element_long | 43.1 | 0.2 |

## Honest interpretation

Naive `str.split(',')` is faster in absolute terms because it produces an
unstructured list of strings. forwarded-parse is slower by tens of
microseconds because it produces a typed `Forwarded` object with:

- proper obs-fold handling (RFC 7230 §3.2.4)
- quoted-string parsing with backslash escapes (RFC 7230 §3.2.6)
- obfuscated-token preservation (RFC 7239 §6.3)
- structured `ForwardedElement` records with named fields
- `format()` round-trip serializer for canonical output
- `normalize()` for deterministic ordering

**The naive baseline cannot express any of these features**, so the
comparison is really "raw nanoseconds" vs "RFC 7239 conformance". For
HTTP-header parsing on a real request path, both implementations are
negligible compared to TLS termination, body parsing, or JSON
serialisation — the bottleneck is rarely the header parser.

If you need raw speed and a structured `Forwarded` is overkill, use
`.split(',')`. If you need RFC 7239 conformance, use forwarded-parse.
