#!/usr/bin/env python3
"""
harness_obfuscated.py — fuzz RFC 7239 §6.3 obfuscated-token round-trip.

V3 contract (cycle_136/adv/02, surface 6):

    Obfuscated values (RFC 7239 §6.3, ``for=_anything``) MUST round-trip
    verbatim — the proxy forwards them without inspection. The serializer
    emits them as bare tokens (never quoted), and the parser preserves
    the leading-underscore form unchanged.

    Per-iteration oracle:
        parse(format(parse('for=' + obf))) == parse('for=' + obf)
        AND format(parse('for=' + obf)) starts with 'for=' + obf (no quotes)

    Also exercises the obf-as-by/host/proto case: ``by=_x`` (extension
    keys whose values begin with ``_`` are preserved verbatim per the
    parser docstring).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    random_obf_token,
    run_harness,
)
from forwarded_parse import ForwardedParseError, format, parse  # noqa: E402


def _drive(i: int, rng) -> None:
    # Vary the body so we cover short, long, all-alpha, alnum, with-dashes,
    # with-dots, with-tildes, with-hashes, etc.
    obf = random_obf_token(rng)

    # 1. for=obf alone (canonical §6.3 case)
    s = "for=" + obf
    parsed = parse(s)
    ser = format(parsed)
    if ser != s:
        raise AssertionError(
            f"obf round-trip mismatch: {s!r} -> {ser!r}"
        )
    # Must not be quoted.
    if '"' in ser:
        raise AssertionError(
            f"obf value was quoted on serialization: {ser!r}"
        )

    # 2. Mixed obf + named + chained for=
    if i % 3 == 0:
        obf2 = random_obf_token(rng)
        s2 = f"for={obf}, for=192.0.2.43;by=203.0.113.60;proto=https;for={obf2}"
        parsed2 = parse(s2)
        ser2 = format(parsed2)
        # Re-parse the serialized form and verify all obf tokens survive.
        try:
            re_parsed2 = parse(ser2)
        except ForwardedParseError as e:
            raise AssertionError(f"re-parse failed on {ser2!r}: {e}")
        # Every for_ value in re_parsed2 must appear in the original list.
        # NB: Forwarded is iterable but not indexable — use list() + iter.
        original_for: list[str] = []
        for elem in list(parsed2):
            original_for.extend(elem.for_)
        re_for: list[str] = []
        for elem in list(re_parsed2):
            re_for.extend(elem.for_)
        if sorted(original_for) != sorted(re_for):
            raise AssertionError(
                f"obf chain mismatch: orig={original_for} re={re_for} "
                f"(input={s2!r}, formatted={ser2!r})"
            )

    # 3. Obf in other parameter slots (by=, host=, proto=)
    if i % 5 == 0:
        for slot in ("by", "host", "proto"):
            s3 = f"for=192.0.2.43;{slot}={obf}"
            parsed3 = parse(s3)
            ser3 = format(parsed3)
            # Re-parse the serialized form; the obf value MUST be preserved.
            try:
                re3 = parse(ser3)
            except ForwardedParseError as e:
                raise AssertionError(
                    f"re-parse failed on {ser3!r}: {e}"
                )
            re_val = getattr(list(re3)[0], slot)
            if re_val != obf:
                raise AssertionError(
                    f"obf in {slot}= round-trip mismatch: {obf!r} -> {re_val!r} "
                    f"(formatted={ser3!r})"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_obfuscated",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
