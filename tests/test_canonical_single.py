"""AC2 / canonical single-pair parse tests."""

from __future__ import annotations

import pytest

from forwarded_parse import Forwarded, ForwardedElement, format, normalize, parse


def test_canonical_single() -> None:
    """AC2 — single ``for=`` parses to a one-element Forwarded."""
    parsed = parse("for=192.0.2.43")
    assert isinstance(parsed, Forwarded)
    assert len(parsed.elements) == 1
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43",)
    assert elem.by is None
    assert elem.host is None
    assert elem.proto is None


def test_canonical_single_with_leading_whitespace() -> None:
    parsed = parse("   for=192.0.2.43  ")
    assert parsed.elements[0].for_ == ("192.0.2.43",)


def test_canonical_single_with_by() -> None:
    parsed = parse("for=192.0.2.43;by=203.0.113.60")
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43",)
    assert elem.by == "203.0.113.60"
    assert elem.host is None
    assert elem.proto is None


def test_canonical_all_four_keys() -> None:
    parsed = parse("for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https")
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43",)
    assert elem.by == "203.0.113.60"
    assert elem.host == "example.com"
    assert elem.proto == "https"


def test_canonical_key_order_in_input() -> None:
    """Input order is preserved (no key reordering inside parse)."""
    parsed = parse("by=203.0.113.60;for=192.0.2.43")
    elem = parsed.elements[0]
    assert elem.by == "203.0.113.60"
    assert elem.for_ == ("192.0.2.43",)


def test_canonical_format_round_trip() -> None:
    """AC7 — format() round-trips a canonical input."""
    h = "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https"
    parsed = parse(h)
    canonical = format(parsed)
    # Re-parse and re-format must be stable.
    assert format(parse(canonical)) == canonical


def test_canonical_normalize_is_no_op_when_canonical() -> None:
    parsed = parse("for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https")
    canonical = format(parsed)
    assert normalize(parsed) == parsed
    assert format(normalize(parsed)) == canonical


def test_canonical_tuple_immutable() -> None:
    """``for_`` is a tuple — frozen after construction."""
    parsed = parse("for=192.0.2.43")
    elem = parsed.elements[0]
    assert isinstance(elem.for_, tuple)
    with pytest.raises((AttributeError, TypeError)):
        elem.for_ = ("other",)  # type: ignore[misc]


def test_canonical_dataclass_repr_stable() -> None:
    parsed = parse("for=192.0.2.43")
    elem = parsed.elements[0]
    assert "192.0.2.43" in repr(elem)


def test_canonical_to_dict_shape() -> None:
    parsed = parse("for=192.0.2.43;by=203.0.113.60")
    d = parsed.to_dict()
    assert d == {
        "elements": [
            {"for": ["192.0.2.43"], "by": "203.0.113.60", "host": None, "proto": None},
        ],
    }


def test_canonical_empty_input_yields_empty_forwarded() -> None:
    """Empty / whitespace input parses to zero elements."""
    assert parse("").elements == ()
    assert parse("   ").elements == ()


@pytest.mark.parametrize(
    "h",
    [
        "for=192.0.2.43",
        "for=192.0.2.43;by=203.0.113.60",
        "for=192.0.2.43;host=example.com",
        "for=192.0.2.43;proto=https",
        "by=203.0.113.60",
        "host=example.com",
        "proto=https",
    ],
)
def test_canonical_various_single_keys(h: str) -> None:
    """A range of single-key inputs all parse to exactly one element."""
    parsed = parse(h)
    assert len(parsed.elements) == 1
