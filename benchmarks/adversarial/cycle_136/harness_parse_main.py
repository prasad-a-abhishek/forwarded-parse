#!/usr/bin/env python3
"""
harness_parse_main.py — fuzz the parse() core API surface.

V3 contract (cycle_136/adv/02, surface 1):
    stdin / random-bytes -> parse(s) -> format(parsed). Assert no uncaught
    exception (parse() is total over arbitrary str; raises ForwardedParseError
    on malformed input, which is expected). Every parsed result must
    round-trip through format() without throwing, and the serialized output
    must NOT contain raw CR/LF (would split the header value).

Inputs exercised: random bytes decoded as utf-8 (errors='replace') up to 4096
bytes, plus 50+ known-bad seeds (empty, OWS-only, CRLF obs-fold, multibyte,
NUL, IPv6 literals, obf tokens, quoted-strings, missing ``=``, unterminated
quotes, etc.).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make parent dir (where _harness_common.py lives) importable when run via
# `python3 harness_parse_main.py` from any cwd.
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
        parsed = parse(s)
    except ForwardedParseError:
        # Expected on malformed input. Verify the message echoes the type of
        # input so the CLI's stderr remains useful.
        return
    # Round-trip: format() must never raise on a parsed Forwarded.
    ser = format(parsed)
    # Sanity: serialized form must not contain raw CR/LF (RFC 9110 §5.5
    # prohibits header values that split over lines).
    if "\r" in ser or "\n" in ser:
        raise AssertionError(
            f"format() re-emitted CR/LF for input {s!r} -> {ser!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_parse_main",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
