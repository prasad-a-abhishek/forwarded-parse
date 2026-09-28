# F-001: Idempotence violation on elements with no recognised keys

## Severity: HIGH

## Surface(s)
- `harness_format_main` (810/810 mismatches on idempotence assertion)
- `harness_normalize_main` (810/810 mismatches on normalize-adds/removes assertion)

## Smallest reproducer
```python
>>> parse("foo=bar")
Forwarded(elements=(ForwardedElement(for_=(), by=None, host=None, proto=None),))
>>> format(parse("foo=bar"))
''
>>> parse(format(parse("foo=bar")))
Forwarded(elements=())
```

## Root cause

In `src/forwarded_parse/_parser.py`, `_parse_pair()` (line 260) handles unknown
keys by parsing-and-discarding the value, then returning `None`. In
`_parse_element()` (line 312), the caller iterates pairs and continues on `None`
— so the element dict is created with default empty values (`for_=[]`,
`by/host/proto=None`) and then **appended** to the elements list, regardless of
whether any recognised key was ever seen.

In `src/forwarded_parse/_serializer.py`, `format_element()` (line 71) emits
`';'.join(parts)` where `parts` is built from the dict's fields. For an
all-unknown element, `parts=[]` and the result is `''`. Empty elements
concatenated with `", "` then leave behind just the `, ` separator, which
`_split_top_level(",")` happily returns as a single empty element — but
`_parse_element("")` returns `None` and that element is filtered out, leaving
`elements=()`.

## Why this is a real bug (not "by design")

1. **Breaks AC7 round-trip idempotence** (`spec.md` §Acceptance Criteria).
   `format(parse(format(parse(h)))) != format(parse(h))` whenever `h` contains
   only unknown keys (or an element whose unknown keys collectively leave
   no recognised data).
2. **The extension rule is asymmetric.** RFC 7239 §4 says downstream consumers
   MUST NOT reject on unknown names. The library applies this at the PAIR
   level (skip unknown pairs) but does NOT apply it symmetrically: unknown
   pairs that leave an element "empty of known keys" should similarly be
   treated as "no element" by the parser, not as an element that happens to
   have no recognised data.
3. **Existing test suite misses it** because no test asserts round-trip on
   inputs containing only unknown keys (331 tests pass; zero assertions on
   `foo=bar`-style inputs).

## Fix direction

In `_parse_element()`, after the pair loop, if the element has `for_=[]` AND
all of `by/host/proto is None`, return `None` — making it equivalent to a
fully-empty element. This mirrors how `_parse_pair()` returns `None` for
unknown-key pairs and lets the outer `parse_forwarded()` loop drop the element
consistently.

## Test gap
- Add `test_idempotence_unknown_key_only.py` covering: `foo=bar`, `=value`
  (rejected), `custom=value`, `for=a;unknown=x` (still works — `for=` keeps
  it), `unknown=x;also_unknown=y` (drop).
- Add a normalisation assertion that `normalize(parse("foo=bar"))` equals
  `Forwarded(elements=())` (no phantom empty element).

## Scale evidence
- 1620 hits across 1,765,000 fuzzer iterations on 10 surfaces (≈0.092 % of
  all random inputs trigger it — concentrated on surfaces with multi-pair
  generation).
- Library verified CLEAN at 250 000 iters on surfaces that don't generate
  unknown keys (parse_main, type_errors, obfuscated).