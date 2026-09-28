#!/usr/bin/env python3
"""
harness_normalize_main.py — fuzz the normalize() surface.

V3 contract (cycle_136/adv/02, surface 3):
    parse(s) -> normalize(parsed) -> format() -> parse() must round-trip
    identically to parse(s) -> format() -> parse(). Normalisation is defined
    as: drop empty for_ values, lowercase known keys (already done by parser),
    preserve input order of elements and for_ chain.

Inputs exercised: same pool as harness_parse_main.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    adversarial_pool,
    random_str,
    run_harness,
)
from forwarded_parse import ForwardedParseError, format, normalize, parse  # noqa: E402


def _drive(i: int, rng) -> None:
    if i % 5 == 0:
        s = adversarial_pool(rng)
    else:
        s = random_str(rng)
    try:
        parsed = parse(s)
    except ForwardedParseError:
        return
    normed = normalize(parsed)
    # normalize() must not mutate the input Forwarded.
    if parsed != parse(s):
        # Defensive: parser itself should not mutate, but check via re-parse.
        raise AssertionError(
            f"parser non-idempotent on input {s!r}: {parsed.to_dict()} != {parse(s).to_dict()}"
        )
    # Normalized output must also round-trip.
    ser_norm = format(normed)
    if "\r" in ser_norm or "\n" in ser_norm:
        raise AssertionError(
            f"normalize+format re-emitted CR/LF: input={s!r} -> {ser_norm!r}"
        )
    try:
        re_parsed = parse(ser_norm)
    except ForwardedParseError as e:
        raise AssertionError(
            f"normalize+format did not round-trip: {ser_norm!r} -> {e}"
        )
    # The normalised form should be parseable to the same shape as the
    # original parse output (elements may differ only in that empty for_
    # entries are dropped — but the parser already rejects empty for=, so
    # for_ values are never empty in practice).
    if re_parsed != parsed and re_parsed != normed:
        # Allow the case where normalize dropped something the original
        # preserved; the reverse (re-parse gaining something) is the bug.
        raise AssertionError(
            f"normalize added/removed elements unexpectedly: "
            f"orig={parsed.to_dict()} norm={re_parsed.to_dict()}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_normalize_main",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
