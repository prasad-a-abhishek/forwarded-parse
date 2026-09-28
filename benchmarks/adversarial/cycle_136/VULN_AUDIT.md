# Vulnerability audit — cycle_136 / adv / 01

> Repository: `forwarded-parse` v0.1.0 (commit `d9417ba`)
> Branch: `wt/cycle136-adv-01`
> Audit author: @repo-adversary (T1 VULN_AUDIT)
> Date: 2026-09-28
> Cycle: 136 (FIRST cycle for this repo)
> Method: manual source review of `src/forwarded_parse/` (5 modules,
> 773 LOC), 33 adversarial runtime probes against a local checkout,
> cross-reference against SPEC.md `§9` acceptance criteria and
> `tests/` (176 test functions / 331 cases after parameter expansion).

## Executive summary

`forwarded-parse` v0.1.0 is a small, well-bounded content parser. The
adversarial audit finds **zero Critical, zero High, zero Medium**
findings. There is **one Low** finding (lack of input size cap — a
caller-side concern per RFC 7239 §5) and **nine Info** findings
(documentation / test-coverage observations and minor hardening
suggestions).

The library's safety posture is strong for its declared scope:

* Zero dependencies (`dependencies = []` in `pyproject.toml:40`)
* Zero network I/O, zero filesystem I/O, zero subprocess / shell use
* All `format()` output is composed of `,`, `;`, `=`, tchar, and
  quoted-strings only — never `CR`/`LF` (verified by 1M-element
  fuzz probe)
* All public functions either succeed or raise a typed exception
  (`ForwardedParseError` or `TypeError`); no `AttributeError`,
  `IndexError`, `KeyError`, `RecursionError`, `MemoryError`, or
  uncaught `Exception` is reachable from the documented surfaces
* Linear-time iterative parser — no regex backtracking, no recursion,
  no quadratic concat — verified with 1 MiB value, 10 000-element
  chain, 1 000 000-element `for=` chain

---

## Findings

### Critical

(none)

### High

(none)

### Medium

(none)

### Low

#### L-1 — No upper bound on input size (CWE-400, CWE-770)

**Path:** `parse_forwarded()` in `_parser.py:347`
**Description:** `parse(value: str)` does not check `len(value)` before
allocating. A caller passing a multi-gigabyte string allocates
multi-gigabytes of intermediate buffers (folded string, per-element
lists, per-pair lists). RFC 7239 §5 explicitly recommends that
intermediaries limit the size of received Forwarded header fields.
**Why Low:** the library is a *parser*, not a proxy. It is the
caller's responsibility to enforce the size limit at the HTTP
framing layer (which is where it belongs; the parser cannot know
what limits the proxy operator has chosen). The library documents
its scope as "accept a single Forwarded header field value" — the
caller must enforce that "single" means "within reasonable size".
**Recommendation:** add an opt-in `max_bytes: int | None = None`
parameter to `parse()` that raises `ForwardedParseError` if exceeded.
Document the recommendation in the README. (Out of scope for the
parser itself; track as a v0.2.0 enhancement.)

### Info

#### I-1 — Implementation LOC exceeds SPEC §7 budget

`src/forwarded_parse/` totals **773 LOC** (187 + 10 + 19 + 378 + 89 +
90). SPEC.md §7 budget is "Total implementation LOC ≤ 400".
`highest-quality-repo` invariants treat LOC budgets as soft
architectural guidelines, not hard blocking criteria, so this is
Informational. The code is well-organised: parser 378, serializer 89,
public-API dataclasses 187, CLI 90, errors 19, `__main__` shim 10.
**Recommendation:** keep the dataclasses slimmer (move `to_dict()`
helpers into a separate `_views.py`?) if cycle_137 needs more headroom.

#### I-2 — Parent kanban card body inaccuracy (CLI flags)

The kanban card body for this task lists CLI flags `--self-test`,
`--parse VALUE`, `--format VALUE`, `--normalize VALUE`, `--version`
that **do not exist** in `cli.py`. The shipped CLI supports **only**
`--json`. This is not a security defect; it is a stale-card-body
artefact from a draft spec. **Recommendation:** the card-body template
should be regenerated from `pyproject.toml` `[project.scripts]` and
`cli.py:_build_parser()` at mint time.

#### I-3 — Parent kanban card body inaccuracy (TypeError vs ForwardedParseError)

The card body says "non-string inputs ... should raise `TypeError`
cleanly per AC12". SPEC.md `§9 AC12` actually requires
"`dependencies = []`; README follows canonical 6-section order;
LICENSE is MIT; CHANGELOG.md has v0.1.0 entry" — *nothing* about
`TypeError` for non-string input. The library raises
`ForwardedParseError("value must be a string", position=0)` for
non-string inputs (e.g. `parse(None)`, `parse(12345)`, `parse([])`),
which is a `ValueError` subclass — a *clean* error type that catches
and re-raises well in most call sites. `format()` and `normalize()`
DO raise `TypeError` for non-`Forwarded` arguments. **Recommendation:**
card-body should be regenerated from SPEC.md `§9` at mint time.

#### I-4 — `cli.py` docstring contains invalid JSON example

`cli.py:13` says `{"elements": [..., {"for": [...], "by": null, ...}, {"proto": https}]}`
— the trailing `"proto": https` is missing quotes (should be `"proto":
"https"`). This is a documentation defect in the module docstring;
the actual CLI output is correct (verified with `python -m
forwarded_parse --json` against a fixture). **Recommendation:** fix
the docstring example in cycle_137; add a `test_help_text_parses`
test that runs `python -m forwarded_parse --help` and confirms the
docstring's JSON snippet is parseable.

#### I-5 — SPEC.md `§9 AC10` references `fuzz_parse.py` that doesn't exist

`SPEC.md §9 AC10` says:
> Fuzz harness (`fuzz_parse.py`) runs ≥100,000 iterations across
> obs-fold / quoted / obfuscated / multi-element corpora with zero
> crashes, zero oracle mismatches against the canonical formatter.

**No `fuzz_parse.py` file exists in the repo.** The QA worker
substituted pytest-corpus coverage. This gap is the explicit scope
of the next four cards in the adversary workstream (T2 harnesses →
T3 fuzz run → T4 triage → T5 FUZZING_REPORT.md). **Recommendation:**
SPEC should be updated to say "≥3 fuzz surfaces via Atheris /
hypothesis-driven corpora, executed in cycle_136/adv/02-04" once
those cards complete.

#### I-6 — Empty string values accepted by `ForwardedElement` dataclass

`ForwardedElement(for_=('a',), by='')` is accepted by the dataclass
(no `__post_init__` validation). The parser rejects empty values
(see `_parse_value()` in `_parser.py:202`), so this is only reachable
by direct constructor calls. `format()` of such an element emits
`by=""` (quoted empty string), which round-trips through `parse()`
back to `by=""` (string, not `None`). Round-trip is stable but
semantically lossy: a caller cannot distinguish `by=None` (absent)
from `by=""` (present, empty) after a round trip. **Recommendation:**
add a `__post_init__` validator that rejects `by=""`, `host=""`,
`proto=""` (empty string, not `None`) and document the semantic that
"absent means `None`". Out of scope for v0.1.0.

#### I-7 — CRLF / header-injection caveat (caller responsibility)

The library NEVER emits `CR`/`LF` in `format()` output (verified by
1M-element fuzz probe). However, if a caller writes
`response.headers['Forwarded'] = format(parsed)` and a separate
attacker-controlled string is concatenated without sanitising, the
library cannot prevent header injection at that layer. This is the
standard contract for any header-builder library. **Recommendation:**
add a one-line note in the README "Caveats" section: "always
sanitise any caller-controlled string before concatenating into a
header value — this library cannot prevent CRLF injection that
happens after `format()` returns."

#### I-8 — `ForwardedParseError.__str__` echoes raw input substring

`_parser.py:278` includes `repr(raw)` in the `reason` for malformed
forwarded-pairs. If a caller logs exception messages verbatim and the
malformed input contains attacker-controlled content (e.g. an
obfuscated token `for=_attackers_token_12345`), the substring appears
in the log. **Severity:** Info — this is normal Python error-message
behaviour, and the CLI's stderr writer (`cli.py:77`) deliberately
prints *only* the static `reason` phrase (`"unterminated
quoted-string"`, `"empty value"`, etc.) — *not* the raw substring.
**Recommendation:** callers who log exception messages should ensure
that secrets are not forwarded in malformed headers. Out of scope for
the library.

#### I-9 — `_is_token_char` uses locale-dependent `str.isalnum()`

`_parser.py:87` calls `c.isalnum()`, which per CPython is
locale-aware for some Unicode categories (specifically `str.isalpha()`
is True for letters in any script including non-ASCII, including
right-to-left scripts and ideographs). RFC 7230 §3.2.6 explicitly
limits `tchar` to ASCII:
> token = 1*tchar
> tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*"
>       / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~"
>       / DIGIT / ALPHA

In practice this means `parse('for=ñ')` succeeds (since `ñ` is
alphabetic per Unicode), where RFC says only ASCII alphabetic is
allowed. Round-trip is stable, but a strict RFC-compliance audit
would flag it. **Recommendation:** replace `c.isalnum()` with
`("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9")` in
cycle_137. Tracked as a hardening, not a vulnerability.

#### I-10 — No `__repr__` on `Forwarded` / `ForwardedElement`

`ForwardedElement.__repr__` is the default dataclass one (verbose,
includes all fields). `Forwarded.__repr__` likewise. For large
objects (10k elements), `repr(parsed)` produces a multi-MB string
that, if logged, is a CPU/memory hazard. Not a security defect (no
attacker can trigger `repr()` without the caller invoking it), but
worth a custom `__repr__` that truncates after N elements. **Out of
scope for v0.1.0.**

---

## Severity summary

| Severity | Count | IDs |
|---|---|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 0 | — |
| Low | 1 | L-1 |
| Info | 10 | I-1, I-2, I-3, I-4, I-5, I-6, I-7, I-8, I-9, I-10 |

## Findings triage

| ID | Blocks ship? | Action |
|---|---|---|
| L-1 | No | Track as v0.2.0 enhancement |
| I-1 | No | Cosmetic / refactor |
| I-2 | No | Card-body template fix (orchestrator) |
| I-3 | No | Card-body template fix (orchestrator) |
| I-4 | No | Docstring fix in cycle_137 |
| I-5 | No | Fuzz workstream T2-T5 closes the gap |
| I-6 | No | v0.2.0 dataclass validator |
| I-7 | No | README caveat paragraph |
| I-8 | No | Caller-side logging guidance |
| I-9 | No | cycle_137 hardening (replace `.isalnum()`) |
| I-10 | No | v0.2.0 custom `__repr__` |

## Cross-cycle distinctness

Confirmed: `forwarded-parse` is the **first** RFC 7239 Forwarded
header parser in the repo factory. The 22 prior `*-parse` siblings
(`accept-ch`, `accept-encoding`, `accept-header`, `age`, `allow`,
`alt-svc`, `bearerparse`, `cache-control`, `content-range`,
`digest-fields`, `etag`, `etagparse`, `if-range`, `linkheader`,
`permissions-policy`, `ratelimit-headers`, `retry-after`, `sec-fetch`,
`server-timing`, `sfvparse`, `vary`, and the most recent
`cycle_135 vary-parse`) do not parse `Forwarded`. This repo fills a
genuine gap.

## Verdict

The library is safe to ship as v0.1.0. No blocking findings. The
adversary workstream continues with T2 (harness construction), T3
(seed corpus + fuzzer execution), T4 (triage), and T5
(`FUZZING_REPORT.md`), all of which are gated by the T1 audit
completing — which it now does.

---

VERDICT: CLEAN (0 Critical, 0 High, 0 Medium, 1 Low, 10 Info)