#!/usr/bin/env python3
"""
harness_type_errors.py — fuzzy boundary: non-string input to type-checked APIs.

V3 contract (cycle_136/adv/02, surface 5 — TypeError boundary):

    Per Invariant 21 (Total Public API Exception Safety), the public API
    surface must be total: passing ``None``, ``int``, ``list``, ``bytes``,
    ``dict``, etc. to ``parse`` / ``format`` / ``normalize`` MUST raise
    ONLY ``TypeError`` or the library's typed ``ForwardedParseError``
    (which is a ``ValueError`` subclass). The downstream adversary phases
    treat ``AttributeError``, ``IndexError``, ``KeyError``, or uncaught
    ``Exception`` as a crash equivalent.

    Reality (from cycle_136/T1 audit, Info finding): ``parse()`` delegates
    to ``parse_forwarded()`` which raises ``ForwardedParseError`` (not
    ``TypeError``) for non-str input. The task body's V1/§4 requirement
    of "TypeError for parse()" is therefore inaccurate. This harness
    accepts either ``TypeError`` or ``ForwardedParseError`` for parse()
    on non-str input, and ``TypeError`` only for format()/normalize()
    (which DO perform explicit isinstance checks).

    ``format()`` and ``normalize()`` take a ``Forwarded`` instance and
    therefore the bad-input corpus for those is non-Forwarded values.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import DEFAULT_SEED, run_harness  # noqa: E402
from forwarded_parse import (  # noqa: E402
    Forwarded,
    ForwardedParseError,
    format,
    normalize,
    parse,
)


# Non-str inputs that must trigger ForwardedParseError (not AttributeError)
# from parse(). bytes is interesting because bytes looks "string-like" and
# is a common source of AttributeError regressions.
_NON_STR_PARSE_INPUTS = [
    None,
    0,
    1,
    -1,
    3.14,
    True,
    False,
    [],
    [""],
    ["*"],
    (),
    ("*",),
    b"",
    b"for=1.2.3.4",
    bytearray(b"for=1.2.3.4"),
    set(),
    object(),
    type("X", (), {})(),
    memoryview(b"x"),
    range(0),
    iter([]),
]


# Non-Forwarded inputs that must trigger TypeError from format() / normalize().
_NON_FORWARDED_INPUTS = [
    None,
    0,
    1,
    "string-not-Forwarded",
    b"bytes-not-Forwarded",
    [],
    (),
    {"elements": []},
    object(),
    True,
    False,
    3.14,
]


def _expect_parse_rejects(bad) -> None:
    """parse() on non-str input must raise ForwardedParseError, never AttributeError."""
    try:
        parse(bad)  # type: ignore[arg-type]
    except ForwardedParseError:
        return  # Expected — ForwardedParseError is the documented typed error.
    except TypeError as e:
        raise AssertionError(
            f"parse() raised TypeError on {bad!r} (expected ForwardedParseError): {e}"
        )
    except AttributeError as e:
        raise AssertionError(
            f"parse() raised AttributeError on {bad!r}: {e}"
        )
    except (IndexError, KeyError, RecursionError, MemoryError) as e:
        raise AssertionError(
            f"parse() raised {type(e).__name__} on {bad!r}: {e}"
        )
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            f"parse() raised unexpected {type(e).__name__} on {bad!r}: {e}"
        )
    else:
        raise AssertionError(
            f"parse() silently accepted non-str input {bad!r}"
        )


def _expect_format_rejects(bad) -> None:
    """format() on non-Forwarded input must raise TypeError (not AttributeError)."""
    try:
        format(bad)  # type: ignore[arg-type]
    except TypeError:
        return  # Expected.
    except AttributeError as e:
        raise AssertionError(
            f"format() raised AttributeError on {bad!r}: {e}"
        )
    except ForwardedParseError as e:
        raise AssertionError(
            f"format() raised ForwardedParseError on {bad!r} (expected TypeError): {e}"
        )
    except (IndexError, KeyError, RecursionError, MemoryError) as e:
        raise AssertionError(
            f"format() raised {type(e).__name__} on {bad!r}: {e}"
        )
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            f"format() raised unexpected {type(e).__name__} on {bad!r}: {e}"
        )
    else:
        raise AssertionError(
            f"format() silently accepted non-Forwarded input {bad!r}"
        )


def _expect_normalize_rejects(bad) -> None:
    """normalize() on non-Forwarded input must raise TypeError."""
    try:
        normalize(bad)  # type: ignore[arg-type]
    except TypeError:
        return
    except AttributeError as e:
        raise AssertionError(
            f"normalize() raised AttributeError on {bad!r}: {e}"
        )
    except ForwardedParseError as e:
        raise AssertionError(
            f"normalize() raised ForwardedParseError on {bad!r} (expected TypeError): {e}"
        )
    except (IndexError, KeyError, RecursionError, MemoryError) as e:
        raise AssertionError(
            f"normalize() raised {type(e).__name__} on {bad!r}: {e}"
        )
    except Exception as e:  # noqa: BLE001
        raise AssertionError(
            f"normalize() raised unexpected {type(e).__name__} on {bad!r}: {e}"
        )
    else:
        raise AssertionError(
            f"normalize() silently accepted non-Forwarded input {bad!r}"
        )


def _drive(i: int, rng) -> None:
    # Cycle through both pools.
    bad_parse = _NON_STR_PARSE_INPUTS[i % len(_NON_STR_PARSE_INPUTS)]
    bad_fmt = _NON_FORWARDED_INPUTS[i % len(_NON_FORWARDED_INPUTS)]
    _expect_parse_rejects(bad_parse)
    _expect_format_rejects(bad_fmt)
    _expect_normalize_rejects(bad_fmt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_type_errors",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
