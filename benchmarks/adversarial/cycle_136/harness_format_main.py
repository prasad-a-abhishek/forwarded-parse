#!/usr/bin/env python3
"""
harness_format_main.py — fuzz the format() idempotence oracle.

V3 contract (cycle_136/adv/02, surface 2):
    parse(s) -> format() -> parse() must produce an identical Forwarded
    instance to the first parse. This is the AC7 round-trip property.

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
from forwarded_parse import ForwardedParseError, format, parse  # noqa: E402


def _drive(i: int, rng) -> None:
    if i % 5 == 0:
        s = adversarial_pool(rng)
    else:
        s = random_str(rng)
    try:
        first = parse(s)
    except ForwardedParseError:
        return  # expected on bad input — idempotence only checked on parseable
    ser = format(first)
    # Idempotence: parse(format(parse(s))) == parse(s)
    try:
        second = parse(ser)
    except ForwardedParseError as e:
        raise AssertionError(
            f"idempotence violation: re-parse failed on formatted {ser!r}: {e}"
        )
    if first != second:
        raise AssertionError(
            f"idempotence violation: first={first.to_dict()} != second={second.to_dict()} "
            f"(input={s!r}, formatted={ser!r})"
        )
    # And format is itself idempotent: format(first) == format(second)
    if ser != format(second):
        raise AssertionError(
            f"format-not-idempotent: first={ser!r} != second={format(second)!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_format_main",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
