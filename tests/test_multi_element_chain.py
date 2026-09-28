"""AC5 — multiple comma-separated elements parse to N ForwardedElement records in input order."""

from __future__ import annotations

import pytest

from forwarded_parse import format, parse


def test_multi_element_chain_two() -> None:
    parsed = parse("for=192.0.2.43, for=198.51.100.17")
    assert len(parsed.elements) == 2
    assert parsed.elements[0].for_ == ("192.0.2.43",)
    assert parsed.elements[1].for_ == ("198.51.100.17",)


def test_multi_element_chain_three() -> None:
    parsed = parse(
        "for=192.0.2.43, for=198.51.100.17, for=203.0.113.60"
    )
    assert len(parsed.elements) == 3
    assert [e.for_[0] for e in parsed.elements] == [
        "192.0.2.43",
        "198.51.100.17",
        "203.0.113.60",
    ]


def test_multi_element_with_full_params_each() -> None:
    parsed = parse(
        "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https, "
        "for=198.51.100.17;by=203.0.113.61;host=example.org;proto=http"
    )
    assert len(parsed.elements) == 2
    a, b = parsed.elements
    assert a.for_ == ("192.0.2.43",)
    assert a.by == "203.0.113.60"
    assert a.host == "example.com"
    assert a.proto == "https"
    assert b.for_ == ("198.51.100.17",)
    assert b.by == "203.0.113.61"
    assert b.host == "example.org"
    assert b.proto == "http"


def test_multi_element_input_order_preserved() -> None:
    """The element list preserves input order (no reordering)."""
    parsed = parse("for=last, for=first, for=second")
    assert [e.for_[0] for e in parsed.elements] == ["last", "first", "second"]


def test_multi_element_format_uses_comma_space() -> None:
    """Canonical format joins elements with ``, ``."""
    parsed = parse("for=192.0.2.43, for=198.51.100.17")
    assert format(parsed) == "for=192.0.2.43, for=198.51.100.17"


def test_multi_element_format_round_trip() -> None:
    h = (
        "for=192.0.2.43;by=203.0.113.60, "
        "for=198.51.100.17;host=example.com;proto=https"
    )
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_multi_element_with_obfuscated_first() -> None:
    parsed = parse("for=_secret, for=192.0.2.43")
    assert parsed.elements[0].for_ == ("_secret",)
    assert parsed.elements[1].for_ == ("192.0.2.43",)


def test_multi_element_with_empty_spaces() -> None:
    """Leading / trailing whitespace between elements is ignored."""
    parsed = parse("  for=192.0.2.43  ,  for=198.51.100.17  ")
    assert len(parsed.elements) == 2


def test_multi_element_trailing_comma_yields_no_extra() -> None:
    """A trailing comma after the last element does not create an empty element."""
    parsed = parse("for=192.0.2.43,")
    assert len(parsed.elements) == 1


def test_multi_element_leading_comma_yields_no_extra() -> None:
    """A leading comma is ignored."""
    parsed = parse(", for=192.0.2.43")
    assert len(parsed.elements) == 1


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 10])
def test_multi_element_chains_of_various_lengths(count: int) -> None:
    parts = [f"for=192.0.2.{i}" for i in range(count)]
    h = ", ".join(parts)
    parsed = parse(h)
    assert len(parsed.elements) == count
    assert [e.for_[0] for e in parsed.elements] == [
        f"192.0.2.{i}" for i in range(count)
    ]
