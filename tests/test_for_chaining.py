"""RFC 7239 §6.3 — multiple ``for=`` chained within a single element."""

from __future__ import annotations

import pytest

from forwarded_parse import format, parse


def test_for_chaining_two_in_one_element() -> None:
    parsed = parse("for=192.0.2.43;for=198.51.100.17")
    assert len(parsed.elements) == 1
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43", "198.51.100.17")


def test_for_chaining_three_in_one_element() -> None:
    parsed = parse("for=192.0.2.43;for=198.51.100.17;for=203.0.113.60")
    assert parsed.elements[0].for_ == ("192.0.2.43", "198.51.100.17", "203.0.113.60")


def test_for_chaining_with_other_params() -> None:
    parsed = parse(
        "for=192.0.2.43;for=198.51.100.17;by=203.0.113.60;proto=https"
    )
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43", "198.51.100.17")
    assert elem.by == "203.0.113.60"
    assert elem.proto == "https"


def test_for_chaining_input_order_preserved() -> None:
    parsed = parse("for=last;for=first;for=second")
    assert parsed.elements[0].for_ == ("last", "first", "second")


def test_for_chaining_format_round_trip() -> None:
    h = "for=192.0.2.43;for=198.51.100.17;by=203.0.113.60"
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_for_chaining_with_obfuscated_and_clear() -> None:
    parsed = parse("for=_secret123;for=192.0.2.43")
    assert parsed.elements[0].for_ == ("_secret123", "192.0.2.43")


def test_for_chaining_format_emits_each_for_value() -> None:
    parsed = parse("for=192.0.2.43;for=198.51.100.17;by=203.0.113.60")
    out = format(parsed)
    assert out == "for=192.0.2.43;for=198.51.100.17;by=203.0.113.60"


def test_for_chaining_not_split_as_elements() -> None:
    """``;`` separates ``for=`` pairs within an element — not as comma-elements."""
    parsed = parse("for=192.0.2.43;for=198.51.100.17")
    assert len(parsed.elements) == 1  # still one element


def test_for_chaining_via_quotation_marks() -> None:
    parsed = parse('for="192.0.2.43";for="198.51.100.17"')
    assert parsed.elements[0].for_ == ("192.0.2.43", "198.51.100.17")


@pytest.mark.parametrize("count", [2, 3, 5, 10])
def test_for_chaining_various_lengths(count: int) -> None:
    parts = ";".join(f"for=10.0.0.{i}" for i in range(count))
    parsed = parse(parts)
    assert len(parsed.elements) == 1
    assert len(parsed.elements[0].for_) == count
    assert parsed.elements[0].for_ == tuple(f"10.0.0.{i}" for i in range(count))
