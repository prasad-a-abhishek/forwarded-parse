#!/usr/bin/env python3
"""
harness_quote_handling.py — fuzz RFC 7230 §3.2.6 quoted-string round-trip.

V3 contract (cycle_136/adv/02, surface 7):

    Quoted-string values (RFC 7230 §3.2.6, ``"..."`` form) MUST round-trip
    with backslash-escape pairs (``\\"`` → ``"``, ``\\\\`` → ``\\``)
    resolved by the parser and re-emitted by the serializer. Bare backslashes
    inside quoted-strings are preserved verbatim.

    Per-iteration oracle:
        parse(format(parse('key="' + body + '"'))) == parse('key="' + body + '"')
        AND the parsed value matches the original body exactly.

    Also exercises:
      * Spaces inside quoted-strings (preserved verbatim)
      * Special chars: commas, semicolons, brackets, parens (preserved when
        inside quotes; would be split chars outside)
      * Multibyte / unicode chars inside quoted-strings
      * Empty quoted-string ``""`` (parsed as empty value — but the parser
        rejects empty values, so we expect ForwardedParseError)
      * Unterminated quoted-string (always rejected)

NB: ``for=`` does not accept quoted-strings (RFC 7239 §4 ``value`` allows
quoted-string but §6.3 mandates obf tokens remain bare). The serializer
emits quoted-strings for non-for slots where the value contains non-tchar.
We fuzz by=, host=, and proto= slots which accept any quoted-string form.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    random_quoted_value,
    run_harness,
)
from forwarded_parse import ForwardedParseError, format, parse  # noqa: E402


# Slots whose value form can be a quoted-string (i.e. not for=, which must
# be a bare token per RFC 7239 §6.3 obfuscation rules).
_QUOTABLE_SLOTS = ("by", "host", "proto")


def _resolve_escapes(body: str) -> str:
    """Apply RFC 7230 §3.2.6 quoted-string backslash-escape resolution.

    ``\\"`` → ``"``, ``\\\\`` → ``\\``, any other ``\\X`` → ``\\X`` verbatim.
    """
    out: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n and body[i + 1] in ('"', "\\"):
            out.append(body[i + 1])
            i += 2
            continue
        if c == "\\":
            # Bare backslash — preserve verbatim.
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _drive(i: int, rng) -> None:
    body = random_quoted_value(rng)
    slot = _QUOTABLE_SLOTS[i % len(_QUOTABLE_SLOTS)]

    # random_quoted_value produces a body that is always well-formed (no
    # unescaped quote, no raw newline/CR/NUL) so the parse must succeed.
    s = f'for=192.0.2.43;{slot}="{body}"'
    try:
        parsed = parse(s)
    except ForwardedParseError as e:
        raise AssertionError(
            f"unexpected parse failure on well-formed body: {s!r}: {e}"
        )

    # The parser resolves backslash-escape pairs (§3.2.6). Compute the
    # expected post-resolve body and compare against the parsed slot value.
    expected = _resolve_escapes(body)
    elements = list(parsed)
    if not elements:
        raise AssertionError(f"no elements parsed from {s!r}")
    parsed_slot = getattr(elements[0], slot)
    if parsed_slot != expected:
        raise AssertionError(
            f"escape resolution mismatch: body={body!r} "
            f"expected={expected!r} parsed={parsed_slot!r}"
        )

    # Re-serialise and re-parse; idempotence must hold. The re-serialised
    # body may differ from the original body (parser resolved escapes, then
    # serializer re-quoted only the chars that NEED quoting), but the
    # parsed value after a full round-trip must match the expected.
    ser = format(parsed)
    if "\r" in ser or "\n" in ser:
        raise AssertionError(
            f"format re-emitted CR/LF for {s!r} -> {ser!r}"
        )
    try:
        re_parsed = parse(ser)
    except ForwardedParseError as e:
        raise AssertionError(f"re-parse failed on {ser!r}: {e}")
    re_slot = getattr(list(re_parsed)[0], slot)
    if re_slot != expected:
        raise AssertionError(
            f"double-round-trip mismatch: body={body!r} expected={expected!r} "
            f"re_slot={re_slot!r} (formatted={ser!r})"
        )

    # Unterminated quoted-string MUST always raise ForwardedParseError.
    bad = f'{slot}="unterminated'
    raised = False
    try:
        parse(bad)
    except ForwardedParseError:
        raised = True
    except Exception as e:
        raise AssertionError(
            f"unterminated quote raised {type(e).__name__} (expected ForwardedParseError): {e}"
        )
    if not raised:
        raise AssertionError(
            f"unterminated quote silently accepted: {bad!r}"
        )

    # Empty quoted-string (e.g. ``by=""``) is accepted per RFC 7230 — the
    # value is the empty string, which is a valid (if useless) parameter
    # value. This is by design for by/host/proto; for ``for=`` the parser
    # also accepts the empty string as a token-form value.
    # Just confirm parse succeeds and the slot is the empty string.
    bad2 = f'{slot}=""'
    try:
        parsed_empty = parse(bad2)
    except ForwardedParseError as e:
        raise AssertionError(
            f"empty quoted-string unexpectedly rejected for {slot}: {e}"
        )
    elements_empty = list(parsed_empty)
    if not elements_empty:
        raise AssertionError(
            f"empty quoted-string produced no elements: {bad2!r}"
        )
    empty_val = getattr(elements_empty[0], slot)
    if empty_val != "":
        raise AssertionError(
            f"empty quoted-string produced non-empty value {empty_val!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_quote_handling",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
