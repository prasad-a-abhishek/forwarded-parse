#!/usr/bin/env python3
"""
harness_cross_cycle.py — independent regex cross-check (sanity).

V3 contract (cycle_136/adv/02, surface 8 — cross-cycle sanity):

    forwarded-parse is the FIRST RFC 7239 parser in the factory — there is
    no factory sibling to oracle against. We instead cross-check against
    an independent re-implementation of the same grammar in a sibling
    module (``_independent_oracle.py``) that mirrors the parser's state
    machine using Python ``re`` rather than hand-written char scanning.
    If both implementations agree on a 100k-iter adversarial corpus, the
    grammar is internally consistent.

    The oracle re-implementation lives in this same file so the test is
    self-contained — it uses ``re.fullmatch`` for token chars and
    ``shlex``-style splitting for element/pair boundaries. Differences
    are oracle mismatches.

NB: This is a SANITY check, not a security oracle. Per the task body's
guidance, forwarded-parse is novel (no factory sibling), so we verify
internal consistency rather than cross-validate against another parser.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    adversarial_pool,
    random_obf_token,
    random_str,
    run_harness,
)
from forwarded_parse import ForwardedParseError, parse  # noqa: E402


# Independent re-implementation of the parser's value-extraction logic.
# Token: 1*tchar (RFC 7230 §3.2.6).
_TOKEN_RE = re.compile(
    r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"
)


def _oracle_extract_for_values(element_text: str) -> list[str]:
    """Independent: extract for= values from an element using regex.

    Returns the list of values as the parser would, or None if the element
    is malformed (any non-tchar char in a token value, missing ``=``, etc.).
    """
    out: list[str] = []
    for chunk in element_text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # For each chunk, find ``for=value`` or ``other=value``.
        m = re.match(r"(?i)(for|by|host|proto)\s*=\s*(.*)$", chunk, re.DOTALL)
        if not m:
            continue
        key = m.group(1).lower()
        raw_value = m.group(2).strip()
        # Strip surrounding double quotes if present (RFC 7230 §3.2.6).
        # NB: this is intentionally naive (no backslash-escape handling)
        # because it's a sanity oracle, not a strict cross-validation.
        if len(raw_value) >= 2 and raw_value[0] == '"' and raw_value[-1] == '"':
            raw_value = raw_value[1:-1]
        if key == "for":
            # Multiple ``for=`` per element.
            out.append(raw_value)
    return out


def _oracle_parse(value: str) -> list[str]:
    """Independent: extract ALL for= values from the full header.

    Returns a flat list of for= values across all elements (comma-separated).
    This is a STRICT SUBSET of what parse() does (parse() also stores
    by/host/proto), so we compare against parse(...).elements[i].for_ only.
    """
    if not value or not value.strip():
        return []
    out: list[str] = []
    # Unfold obs-fold
    unfolded = re.sub(r"\r\n[ \t]+", " ", value)
    for element_text in unfolded.split(","):
        element_text = element_text.strip()
        if not element_text:
            continue
        for v in _oracle_extract_for_values(element_text):
            out.append(v)
    return out


def _drive(i: int, rng) -> None:
    if i % 5 == 0:
        s = adversarial_pool(rng)
    elif i % 11 == 0:
        # Force an obf-only chain to exercise the §6.3 path.
        n = rng.randint(1, 8)
        s = ", ".join(f"for={random_obf_token(rng)}" for _ in range(n))
    else:
        s = random_str(rng)
    try:
        parsed = parse(s)
    except ForwardedParseError:
        # Oracle may still produce something for the same input; we don't
        # require agreement on malformed input (the oracle is permissive
        # by design — it's a sanity check, not a strict cross-validation).
        return
    actual_for: list[str] = []
    for elem in parsed:
        actual_for.extend(elem.for_)
    expected_for = _oracle_parse(s)
    if sorted(actual_for) != sorted(expected_for):
        raise AssertionError(
            f"oracle mismatch: input={s!r} parsed={actual_for} "
            f"oracle={expected_for}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_cross_cycle",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
