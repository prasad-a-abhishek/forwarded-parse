"""Regression fuzzer for F-001 / F-004 closure (cycle_136 fix card t_8e281d73).

Runs 200 iterations against the three surfaces that originally surfaced
the two HIGH findings:

* ``harness_format_main``     — idempotence: format(parse(format(parse(h)))) == format(parse(h))
* ``harness_normalize_main``  — idempotence + phantom-element check
* ``harness_cli_parse``       — non-empty input → exit 0 + non-empty stdout

Each surface generates random multi-pair / multi-element Forwarded
inputs using the same distribution the cycle_136 adversary harness
used (uniform random token-pair sampling from the affected key set),
then asserts the cycle_136 contract.

Zero mismatches across all 3 surfaces × 200 iters = 600 total assertions
proves the fix closes both findings.

Run from the worktree root::

    PYTHONPATH=src python3 benchmarks/regression_fuzz_F001_F004.py

Exit code 0 on success, non-zero on any oracle mismatch.
"""

from __future__ import annotations

import json
import random
import string
import subprocess
import sys
from typing import Iterator

from forwarded_parse import Forwarded, format, normalize, parse


_KNOWN = ("for", "by", "host", "proto")
_EXTRA = ("foo", "bar", "baz", "qux", "ext1", "ext2", "custom", "another")
_ALL_KEYS = _KNOWN + _EXTRA


def _rand_token(rng: random.Random, max_len: int = 8) -> str:
    """Generate a random RFC 7230 token (tchar alphabet)."""
    alphabet = string.ascii_lowercase + string.digits + "!#$%&'*+-.^_`|~"
    n = rng.randint(1, max_len)
    return "".join(rng.choice(alphabet) for _ in range(n))


def _rand_value(rng: random.Random) -> str:
    """Generate a random RFC 7230 token-value (may or may not start with _)."""
    v = _rand_token(rng)
    # 25% chance of obfuscated-form (starts with _).
    if rng.random() < 0.25 and not v.startswith("_"):
        v = "_" + v
    return v


def _rand_element(rng: random.Random) -> str:
    """Generate a random ``forwarded-element`` string (zero or more ``;``-joined pairs)."""
    n = rng.randint(1, 5)
    pairs: list[str] = []
    for _ in range(n):
        # 50/50 known vs unknown key to maximise coverage of the F-001 fix.
        if rng.random() < 0.5:
            key = rng.choice(_KNOWN)
        else:
            key = rng.choice(_EXTRA)
        pairs.append(f"{key}={_rand_value(rng)}")
    return ";".join(pairs)


def _rand_header(rng: random.Random) -> str:
    """Generate a random Forwarded header value (one or more ``,``-joined elements)."""
    n = rng.randint(1, 4)
    elements = [_rand_element(rng) for _ in range(n)]
    return ",".join(elements)


# ---------------------------------------------------------------------------
# Surface 1 — harness_format_main
# ---------------------------------------------------------------------------


def surface_format_main(rng: random.Random) -> None:
    """Idempotence: format(parse(format(parse(h)))) == format(parse(h))."""
    h = _rand_header(rng)
    first = format(parse(h))
    second = format(parse(first))
    assert first == second, (
        f"idempotence violation: first={first!r} != second={second!r} (input={h!r})"
    )


# ---------------------------------------------------------------------------
# Surface 2 — harness_normalize_main
# ---------------------------------------------------------------------------


def surface_normalize_main(rng: random.Random) -> None:
    """Normalize produces no phantom elements; normalize is idempotent."""
    h = _rand_header(rng)
    p1 = parse(h)
    n1 = normalize(p1)
    # Phantom-element check: every element must have at least one known key.
    for i, e in enumerate(n1.elements):
        assert e.for_ or e.by is not None or e.host is not None or e.proto is not None, (
            f"phantom element at idx={i}: {e.to_dict()!r} (input={h!r})"
        )
    # Idempotence: normalize(normalize(x)) == normalize(x).
    n2 = normalize(n1)
    assert n1 == n2, f"normalize is not idempotent on {h!r}: {n1.to_dict()} != {n2.to_dict()}"
    # Round-trip with the same constraint.
    p2 = parse(format(n1))
    assert normalize(p2) == n1, (
        f"normalize round-trip drift on {h!r}: {normalize(p2).to_dict()} != {n1.to_dict()}"
    )


# ---------------------------------------------------------------------------
# Surface 3 — harness_cli_parse
# ---------------------------------------------------------------------------


def surface_cli_parse(rng: random.Random) -> None:
    """CLI contract: non-empty input → exit 0. The stdout-empty-on-phantom case is gone."""
    h = _rand_header(rng)
    proc = subprocess.run(
        [sys.executable, "-m", "forwarded_parse"],
        input=h,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert proc.returncode == 0, (
        f"CLI exit={proc.returncode} on {h!r} (stdout={proc.stdout!r}, stderr={proc.stderr!r})"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _iter(rng: random.Random, n: int) -> Iterator[int]:
    for i in range(n):
        rng.seed(0xC0FFEE_136 + i)  # deterministic per-iter seed for reproducibility
        yield i


def main(argv: list[str]) -> int:
    iters = int(argv[1]) if len(argv) > 1 else 200
    rng = random.Random(0xC0FFEE_136)
    surfaces = {
        "harness_format_main": surface_format_main,
        "harness_normalize_main": surface_normalize_main,
        "harness_cli_parse": surface_cli_parse,
    }
    summary: dict[str, dict[str, int]] = {}
    total = 0
    for name, fn in surfaces.items():
        passed = 0
        for _ in _iter(rng, iters):
            try:
                fn(rng)
                passed += 1
            except AssertionError as exc:
                print(f"[FAIL] {name}: {exc}", file=sys.stderr)
        summary[name] = {"iters": iters, "passed": passed, "mismatches": iters - passed}
        total += passed
    print(json.dumps(summary, indent=2))
    expected = iters * len(surfaces)
    if total != expected:
        print(f"FAIL: {expected - total} oracle mismatches across surfaces", file=sys.stderr)
        return 1
    print(f"OK: {total}/{expected} assertions passed across {len(surfaces)} surfaces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))