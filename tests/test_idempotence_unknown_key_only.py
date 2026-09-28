"""Regression tests for F-001 / F-004 (cycle_136 adversary triage).

Forwarded elements whose pairs are *all* unknown extension keys
(e.g. ``foo=bar``, ``custom=value;another=x``) must be dropped by the
parser — not retained as a phantom ``ForwardedElement`` with
``for_=[]`` and ``by/host/proto=None``. Otherwise round-trip idempotence
(AC7) breaks:

    format(parse("foo=bar"))                 == ''
    format(parse(format(parse("foo=bar"))))  == ''     # parse('' ) → []
    but len(parse("foo=bar").elements)       == 1      # ← phantom
    →  format(parse("foo=bar"))  !=  format(parse(format(parse("foo=bar"))))

The CLI's ``if out: write`` guard then suppresses the empty stdout on
non-empty input, which the harness also asserts against.

The single root cause is ``_parse_element()``: previously it appended
the dict regardless of whether any recognised key had been observed.
The fix mirrors ``_parse_pair()``'s ``None`` convention for unknown-key
pairs and lets the outer ``parse_forwarded()`` loop drop the element
consistently.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from forwarded_parse import (
    Forwarded,
    ForwardedElement,
    format,
    normalize,
    parse,
)


# ---------------------------------------------------------------------------
# F-001: library-level behaviour
# ---------------------------------------------------------------------------


def test_parse_unknown_key_only_returns_empty_forwarded() -> None:
    """``parse("foo=bar")`` must return ``Forwarded(elements=())`` (no phantom)."""
    result = parse("foo=bar")
    assert result == Forwarded(elements=())
    assert len(result.elements) == 0


def test_parse_multiple_unknown_keys_returns_empty_forwarded() -> None:
    """``parse("custom=value;another=x")`` must return ``Forwarded(elements=())``."""
    result = parse("custom=value;another=x")
    assert result == Forwarded(elements=())
    assert len(result.elements) == 0


def test_parse_known_key_preserves_element() -> None:
    """``parse("for=a;unknown=x")`` keeps the element because ``for=`` is known."""
    result = parse("for=a;unknown=x")
    assert result == Forwarded(
        elements=(
            ForwardedElement(for_=("a",), by=None, host=None, proto=None),
        )
    )


def test_parse_unknown_then_known_orders_correctly() -> None:
    """Extension keys before/after a known key must not affect the known key's value."""
    result = parse("unknown=x;also_unknown=y;for=b")
    assert result == Forwarded(
        elements=(
            ForwardedElement(for_=("b",), by=None, host=None, proto=None),
        )
    )


def test_format_of_unknown_key_only_is_empty_string() -> None:
    """``format(parse("foo=bar"))`` must be ``''`` (not ``', '`` or similar)."""
    parsed = parse("foo=bar")
    assert format(parsed) == ""


@pytest.mark.parametrize(
    "header",
    [
        "foo=bar",
        "custom=value",
        "custom=value;another=x",
        "x=y;z=w",
    ],
)
def test_round_trip_idempotence_on_unknown_key_only_inputs(header: str) -> None:
    """AC7 holds on inputs containing only unknown keys: f(p(f(p(h)))) == f(p(h))."""
    once = format(parse(header))
    twice = format(parse(once))
    assert once == twice
    # And once parses back to an empty Forwarded (no phantom element).
    assert parse(once) == Forwarded(elements=())


def test_normalize_is_identity_on_unknown_key_only_input() -> None:
    """``normalize(parse("foo=bar"))`` equals ``parse("foo=bar")`` (both empty)."""
    parsed = parse("foo=bar")
    normalised = normalize(parsed)
    assert normalised == Forwarded(elements=())
    assert normalised == parsed


def test_known_keys_mixed_with_unknown_still_round_trip() -> None:
    """Regression guard: the fix must NOT drop elements that DO contain ``for=``."""
    header = "for=192.0.2.43;unknown=ext1;by=203.0.113.60;another=ext2"
    parsed = parse(header)
    canonical = format(parsed)
    # Two-round-trip property holds.
    assert format(parse(canonical)) == canonical
    # Unknown keys are dropped (RFC 7239 §4); known keys survive in canonical order.
    assert canonical == "for=192.0.2.43;by=203.0.113.60"


def test_mixed_elements_with_one_empty_unknown_only_drops_only_the_empty() -> None:
    """A real element and a phantom-only element in the same header — only the phantom is dropped."""
    # Real element first, then an unknown-only element after a comma.
    header = "for=192.0.2.43,foo=bar"
    parsed = parse(header)
    assert len(parsed.elements) == 1
    assert parsed == Forwarded(
        elements=(
            ForwardedElement(for_=("192.0.2.43",), by=None, host=None, proto=None),
        )
    )


# ---------------------------------------------------------------------------
# F-004: CLI-level behaviour
# ---------------------------------------------------------------------------


def _run_cli(input_str: str, json_mode: bool = False) -> subprocess.CompletedProcess:
    """Invoke ``python -m forwarded_parse`` in a subprocess with ``input_str`` on stdin."""
    cmd = [sys.executable, "-m", "forwarded_parse"]
    if json_mode:
        cmd.append("--json")
    return subprocess.run(
        cmd,
        input=input_str,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def test_cli_unknown_key_only_input_exits_zero_with_empty_stdout() -> None:
    """F-004 regression: ``echo foo=bar | forwarded-parse`` → exit 0, no stdout.

    The harness asserts non-empty input must produce non-empty stdout on
    exit 0. After the fix, ``parse("foo=bar")`` reduces to an empty
    Forwarded; ``format()`` returns ``''``; the CLI's ``if out: write``
    guard correctly suppresses the (legitimately empty) output.
    """
    proc = _run_cli("foo=bar")
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert proc.stderr == ""


def test_cli_real_input_still_emits_canonical_output() -> None:
    """Regression guard: real input still produces canonical round-trip output."""
    proc = _run_cli("for=_secret123")
    assert proc.returncode == 0
    assert proc.stdout == "for=_secret123\n"
    assert proc.stderr == ""


def test_cli_real_input_json_mode_emits_json() -> None:
    """Regression guard: ``--json`` still serialises real input correctly."""
    proc = _run_cli("for=_secret123", json_mode=True)
    assert proc.returncode == 0
    # JSON content is asserted by string match (don't depend on key ordering).
    assert '"elements"' in proc.stdout
    assert '"_secret123"' in proc.stdout
    assert proc.stderr == ""


def test_cli_unknown_then_known_input_emits_known_only() -> None:
    """CLI drops the unknown-key fragment and emits only the known one."""
    proc = _run_cli("unknown=x;for=192.0.2.43")
    assert proc.returncode == 0
    assert proc.stdout == "for=192.0.2.43\n"
    assert proc.stderr == ""