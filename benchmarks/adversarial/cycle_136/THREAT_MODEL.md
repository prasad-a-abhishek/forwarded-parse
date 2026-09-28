# Threat model — cycle_136 / adv / 01

> Repository: `forwarded-parse` v0.1.0 (commit `d9417ba`)
> Date: 2026-09-28

## 1. Library role

`forwarded-parse` is a *content parser*. It does not touch the network,
the filesystem, the environment, or any process boundary. It receives a
Python `str` (one Forwarded header field value), returns a Python
object, optionally writes the canonical header string or a JSON
document to stdout. The attacker model is therefore:

> "A caller hands `parse()` an untrusted string. The caller wants to
>  use the result safely."

That is, the library sits in the *trust boundary* of a typical
web-server request pipeline: an upstream proxy or load balancer has
already accepted bytes off the network, isolated a single header field,
and is now handing the field value to `parse()`. Anything the library
does wrong at this point can:

* leak into audit logs (information disclosure)
* be concatenated into downstream headers (CRLF/header injection by
  caller carelessness)
* exhaust memory/CPU on the request handler thread (DoS)
* produce an exception type that confuses the caller's exception
  handler (logic bug)

The library **does not** see raw bytes from the wire, does not parse
HTTP framing, and does not have to defend against arbitrary octet
sequences — its caller is expected to have done that already.

## 2. Attacker capabilities (worst-case)

* Attacker fully controls the `Forwarded:` header value as it arrives
  at the parser (because they are upstream of the proxy / CDN).
* They can craft arbitrarily long strings (up to whatever limit the
  *proxy* imposes — the library imposes none).
* They can include any Unicode scalar value (Python `str` accepts
  anything that decodes as UTF-8/UTF-16/UTF-32 depending on the
  upstream reader — but typical proxy middlewares like `nginx` reject
  bytes that don't pass their own header validation before they ever
  reach user code).
* They can include RFC-invalid sequences (`for=;for=;`, multiple `==`,
  unbalanced quotes, embedded `\r\n` sequences, control characters,
  embedded NUL bytes, etc.).

## 3. Defender capabilities

* The library is single-threaded and stateless; no race surface.
* The library has no side effects except stdout writes (CLI mode) and
  stderr writes on parse error (CLI mode). The Python API has zero
  side effects.
* The library returns a strongly-typed `Forwarded` (frozen dataclass).
  Mutation requires rebuilding the object — there is no `append()`
  method on the dataclass, no in-place edit.

## 4. Worst-case impact matrix

| Attack | Pre-condition | Worst-case | Library defence | Residual risk |
|---|---|---|---|---|
| **ReDoS / CPU DoS** | Caller passes unbounded string | Thread stalls; proxy slows; whole fleet slows | Linear-time iterative parser, no backtracking regex | L-1: caller should cap input length (RFC 7239 §5: proxies SHOULD limit) |
| **Memory DoS** | Caller passes 1 GiB string | 1 GiB allocated | n/a — Python allocates what you give it | L-1: same; this is a Python `str` operation cost, not a library defect |
| **Header injection (CRLF)** | Caller writes `format(parsed)` to a header without further sanitising | Attacker injects a second header | `format()` never emits `CR`/`LF`; verified with 1M-element `format()` | I-7: documented limitation; the library cannot save a careless caller |
| **Code injection / RCE** | Any caller passes malformed input | n/a | No `eval`/`exec`/`pickle`/`subprocess`/`os.system` anywhere | None |
| **Exception type confusion** | Caller passes non-`str` to `parse()` | Caller's `except ValueError:` swallows `ForwardedParseError` (subclass — actually fine) or vice-versa | `ForwardedParseError` is a `ValueError` subclass; all exceptions inherit cleanly | None |
| **Information disclosure via error** | Caller logs exception string | Logs echo the malformed substring | Only the static `reason` phrase is logged by CLI; full raw input only in `__str__` of the exception object (caller must opt in) | I-8: documented Info — caller controls logging |
| **Unicode normalisation mismatch** | Caller compares parsed values byte-for-byte | False-negative equality checks | `_is_token_char` uses `.isalnum()` (locale-aware) — see I-9 | I-9: locale dependency could cause cross-environment mismatches |
| **Dataclass bypass** | Caller constructs `ForwardedElement` directly with non-string for_ tuple | Custom-element validation skipped | None at the dataclass; the parser validates inputs before producing dataclasses | None for normal use; only a concern for library callers who bypass `parse()` |

## 5. RFC compliance gaps that affect security

* **RFC 7239 §5** recommends proxies limit Forwarded header field
  size. The library does not. → L-1 (caller-side concern).
* **RFC 7239 §6.3** recommends that `for=` values be RFC-8252 URI
  references or RFC-5950 text / quoted IPv4:port. The library does
  *not* validate the syntax of values — it accepts any token char
  string and any quoted-string. This means a `for="DROP TABLE users"`
  payload is accepted. That is **by design** for a parser (the
  reference grammar is intentionally liberal) and not a security
  defect in the library itself — but downstream consumers MUST
  validate `for=` values before using them as IPs, hostnames, etc.
* **RFC 7230 §3.2.4** obs-fold unfolding is implemented correctly
  (only `CRLF + (SP|HTAB)+` is joined; bare `CRLF` is preserved).
* **RFC 7230 §3.2.6** backslash-escape resolution is implemented
  correctly (only `\"` and `\\` are escaped; bare backslashes are
  preserved verbatim per the RFC).

## 6. Cross-cycle distinctness

`forwarded-parse` is the **first RFC 7239 Forwarded header parser** in
the repo factory. Prior `*-parse` siblings cover: `accept-ch`,
`accept-encoding`, `accept-header`, `age`, `allow`, `alt-svc`,
`bearerparse`, `cache-control`, `content-range`, `digest-fields`,
`etag`, `etagparse`, `if-range`, `linkheader`, `permissions-policy`,
`ratelimit-headers`, `retry-after`, `sec-fetch`, `server-timing`,
`sfvparse`, `vary`. None of those parse `Forwarded`. This repo does
not duplicate any prior shipped parser's surface.

## 7. Trust boundary diagram

```
network →  proxy / WSGI server  →  forwarded_parse.parse()  →  caller business logic
                                  ▲                          ▲
                                  │                          │
                          trust boundary 1            trust boundary 2
                          (caller responsible         (caller responsible
                           for HTTP framing,           for using parsed
                           size limits,                values safely — don't
                           error logging)              pass `for="sql"` to
                                                       a SQL query)
```

The library sits *between* the two boundaries and does not own either
one. Its job is to never break the second boundary: it must not emit
output that the caller can accidentally use to construct a malformed
header value, an unparseable JSON document, or an exception type that
escapes caller-side validation.

It succeeds at this job.