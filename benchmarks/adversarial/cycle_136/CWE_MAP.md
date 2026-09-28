# CWE map — cycle_136 / adv / 01

> Repository: `forwarded-parse` v0.1.0 (commit `d9417ba`)
> Date: 2026-09-28
> Method: manual review of `src/forwarded_parse/` + 33 adversarial
> runtime probes against a local checkout, plus static analysis of
> all branch paths in the parser/serializer.

CWE entries below are the ones actually considered during the audit;
"applies" means there is a concrete path that *could* trigger the
weakness, not that the path is necessarily reachable.

| CWE | Name | Applies? | Notes |
|---|---|---|---|
| CWE-20 | Improper Input Validation | **No** | `parse_forwarded` (line 354) validates `isinstance(value, str)`; `_parse_value` validates token-char range; `_parse_pair` rejects empty name and missing `=`; `_split_top_level` correctly handles quoted-string state. |
| CWE-22 | Path Traversal | **No** | Library has no filesystem I/O. |
| CWE-74 | Injection | **No** | Output is JSON via `json.dumps` (which escapes) or plain header value (which the caller appends to an HTTP header value, not an HTTP response line — see CWE-93 below for nuance). |
| CWE-77 | Command Injection | **No** | CLI uses `argparse.parse_args`; no `os.system`, `subprocess.*`, `eval`, `exec`. |
| CWE-78 | OS Command Injection | **No** | As above. |
| CWE-79 | Cross-Site Scripting | **No** | Header value parser, no HTML/JS context. |
| CWE-88 | Argument Injection | **No** | Single-flag CLI, no shell. |
| CWE-93 | CRLF Injection | **No (with caveat)** | If a caller does `response.headers['Forwarded'] = format(parsed) + injected_crlf`, the library does NOT prevent the caller from doing that. But the library itself never emits `CRLF` in `format()` output (verified: 1M-element `format()` contains only `,`, `;`, `=`, and tchar — see `serializer.py:30` quoting set, no `\r\n`). Caveat is documented as Info-level (I-7). |
| CWE-94 | Code Injection | **No** | No `eval`/`exec`/dynamic import anywhere in `src/`. |
| CWE-113 | Header Injection | **No** | `format()` never emits `CR`/`LF`. Verified with fuzz probe. |
| CWE-117 | Log Injection | **No** | No logging. |
| CWE-119 | Buffer Overflow | **No** | Python + dataclass; no fixed buffers. |
| CWE-125 | Out-of-bounds Read | **No** | Parser uses index-into-str with explicit bounds checks (`i + 1 < n`, `len(s) < 2`, `eq <= 0`). All lookups guarded. |
| CWE-190 | Integer Overflow | **No** | `position` is `int` but used only as a human-readable offset (no arithmetic). `len(value)` is bounded by available memory. |
| CWE-200 | Information Exposure | **No** | No `repr()` of user input in error paths that could leak secrets into logs (the error body uses `repr(raw)` of the malformed substring; for non-secret input this is fine; for secret-bearing input the caller is responsible for sanitising the error). Not a library defect. |
| CWE-209 | Information Exposure Through Error Messages | **Partial — Info** | `ForwardedParseError.__str__` includes `{reason} (at position {position})`. For typical cases (e.g. `"unterminated quoted-string"`) the message is generic. For `malformed forwarded-pair: '<raw>' (expected token=value)` (`_parser.py:278`) the raw substring is included. This is helpful for debugging but could echo caller-controlled content into stderr if the caller logs exceptions verbatim. Severity: Info. Documented in `VULN_AUDIT.md` I-8. |
| CWE-233 | Parameter Injection | **No** | No parameters parsed from external input. |
| CWE-248 | Uncaught Exception | **No** | All public entry points have explicit error paths; `format()`/`normalize()` raise `TypeError` on bad arg types; `parse()` raises `ForwardedParseError` (a `ValueError` subclass) on bad inputs. Verified with 33 probes. |
| CWE-287 | Authentication Bypass | **N/A** | Not an auth library. |
| CWE-295 | Improper Cert Validation | **N/A** | No TLS. |
| CWE-319 | Cleartext Transmission | **N/A** | No I/O. |
| CWE-352 | CSRF | **N/A** | Not a web handler. |
| CWE-367 | Time-of-check Time-of-use Race | **No** | No filesystem or shared state. |
| CWE-369 | Divide By Zero | **No** | No division. |
| CWE-377 | Insecure Temp File | **No** | No tempfile. |
| CWE-400 | Uncontrolled Resource Consumption | **Partial — Low** | `parse(value)` does not bound `len(value)`. A caller passing a 1 GiB string allocates ~1 GiB of UTF-8/UTF-16 internal buffers. RFC 7239 §5 explicitly says proxies SHOULD limit Forwarded header size. The library does not enforce this. **Severity: Low** — the library is not a proxy; the caller is the proxy/edge handler. `VULN_AUDIT.md` L-1. |
| CWE-401 | Resource Leak | **No** | All resources are Python objects with deterministic lifetime. |
| CWE-409 | Improper Handling of Highly Compressed Data | **No** | No decompression. |
| CWE-426 | Untrusted Search Path | **No** | No dynamic loading. |
| CWE-444 | Inconsistent Interpretation of HTTP Requests | **No** | Library receives an already-isolated header value; not an HTTP parser. |
| CWE-476 | NULL Pointer Deref | **No** | Python; only `None` cases are explicit (`is None` checks). |
| CWE-502 | Deserialization of Untrusted Data | **No** | No `pickle.load`, `yaml.load`, `marshal.loads`, `shelve.open` anywhere. |
| CWE-522 | Insufficiently Protected Credentials | **N/A** | Library does not handle credentials. |
| CWE-532 | Information Exposure Through Log Files | **Partial — Info** | See CWE-209 — same data path. The library writes to stderr only via `cli.py`, and the only stderr line on parse error is `forwarded-parse: parse error: {exc.reason}\n`. The `reason` is a static phrase (`"unterminated quoted-string"`, `"empty value"`, etc.) — not the raw input. The raw input appears only in `__str__` of the exception (CWE-209). CLI mode does NOT echo raw input. Severity: Info. |
| CWE-562 | Return of Stack Variable Address | **No** | Python; no raw addresses. |
| CWE-601 | Open Redirect | **N/A** | No URL handling. |
| CWE-611 | XXE | **N/A** | No XML. |
| CWE-674 | Uncontrolled Recursion | **No** | Parser is iterative (`while i < n`). Verified: `parse('for=' + 'a' * 1_000_000)` and `parse('for=a;for=b;...;for=z' * 100_000)` both run iteratively with stack depth = constant. |
| CWE-704 | Incorrect Type Conversion | **No** | All numeric conversions are explicit and checked. |
| CWE-732 | Incorrect Permission Assignment | **N/A** | No file/permission operations. |
| CWE-754 | Improper Check for Unusual or Exceptional Conditions | **No** | Empty input, whitespace input, None input, non-string input, empty value, missing `=`, unterminated quoted-string, invalid token char, bare CRLF all have explicit branches. |
| CWE-770 | Allocation of Resources Without Limits | **Partial — Low** | Same as CWE-400. No upper bound on input length, output element count, or per-element pair count. Severity: Low (caller-side concern). Documented as L-1. |
| CWE-776 | Improper Restriction of Recursion | **No** | Iterative parser. |
| CWE-783 | Operator Precedence Logic Error | **No** | No arithmetic operators; only string concatenation, indexing, comparison. |
| CWE-786 | Access of Memory Location Before Start of Buffer | **No** | All index accesses are bounds-checked (`i < n`, `i + 1 < n`, `len(s) < 2`). |
| CWE-787 | Out-of-bounds Write | **No** | Python strings are immutable; no `ctypes`/`array` writes. |
| CWE-835 | Infinite Loop | **No** | All `while` loops in `_parser.py` advance `i` on every iteration (`i += 1` or `i += 2`); tested with adversarial inputs (`1M for-chain`, `100k comma chain`, `deep obs-fold`, `\r\n\r\n`, empty input) — all return in finite time. |
| CWE-908 | Use of Uninitialized Resource | **No** | All variables assigned before use; `out: list[str] = []` style initializers everywhere. |
| CWE-915 | Improperly Controlled Modification of Dynamically-Determined Object Attributes | **No** | `@dataclass(frozen=True, slots=True)` prevents attribute assignment; `__post_init__` only assigns to the same field that was passed in. No `setattr` outside dataclass machinery. |
| CWE-916 | Use of Password Hash With Insufficient Computational Effort | **N/A** | No password handling. |
| CWE-918 | Server-Side Request Forgery | **N/A** | No HTTP client. |
| CWE-1041 | Reliance on Untrusted Inputs in Security Decision | **No** | Library does not make security decisions. |
| CWE-1173 | Improper Use of Validation Framework | **No** | Manual validation per RFC 7239 ABNF. |
| CWE-1188 | Insecure Default Initialization of Resource | **No** | All defaults are safe (empty tuple, `None`). |

## Summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 (CWE-400/770: unbounded input — library-level concern, NOT a proxy defect) |
| Info | 2 (CWE-209/532: error message echoes malformed substring) |

The library's safety posture is **strong** for its declared scope:
*zero-dependency RFC 7239 parser/serializer*. All control characters
are rejected cleanly. No code-injection, no shell-injection, no
deserialization, no filesystem operations, no network I/O.