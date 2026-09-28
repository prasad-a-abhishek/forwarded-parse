"""Error / edge-case path tests."""

from __future__ import annotations

import pytest

from forwarded_parse import (
    Forwarded,
    ForwardedElement,
    ForwardedParseError,
    format,
    normalize,
    parse,
)


def test_error_unterminated_quoted_string() -> None:
    with pytest.raises(ForwardedParseError):
        parse('host="example.com')


def test_error_invalid_char_in_token_value() -> None:
    """A space inside an unquoted token value is invalid."""
    with pytest.raises(ForwardedParseError):
        parse("for=192.0.2.43 space")


def test_error_missing_equals_in_pair() -> None:
    """``for_192.0.2.43`` has no ``=`` — malformed pair."""
    with pytest.raises(ForwardedParseError):
        parse("for_192.0.2.43")


def test_error_empty_value() -> None:
    """``for=`` (empty value) raises (no zero-length tokens)."""
    with pytest.raises(ForwardedParseError):
        parse("for=")


def test_error_non_string_input() -> None:
    with pytest.raises(ForwardedParseError):
        parse(12345)  # type: ignore[arg-type]


def test_error_none_input() -> None:
    with pytest.raises(ForwardedParseError):
        parse(None)  # type: ignore[arg-type]


def test_error_unknown_key_with_invalid_value_still_parses() -> None:
    """Unknown keys with valid values are silently ignored (no error)."""
    parsed = parse("for=192.0.2.43;future_key=ok;proto=https")
    assert parsed.elements[0].for_ == ("192.0.2.43",)
    assert parsed.elements[0].proto == "https"


def test_error_unknown_key_does_not_break_subsequent_pairs() -> None:
    parsed = parse("for=192.0.2.43;unknown=value;by=203.0.113.60")
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43",)
    assert elem.by == "203.0.113.60"


def test_edge_only_whitespace_inside_element() -> None:
    parsed = parse("   ,  for=192.0.2.43  ,   ")
    assert len(parsed.elements) == 1
    assert parsed.elements[0].for_ == ("192.0.2.43",)


def test_edge_empty_string_yields_empty_forwarded() -> None:
    parsed = parse("")
    assert isinstance(parsed, Forwarded)
    assert len(parsed) == 0
    assert not parsed  # __bool__


def test_edge_whitespace_only_yields_empty_forwarded() -> None:
    parsed = parse("   \t  ")
    assert len(parsed) == 0


def test_edge_format_empty_forwarded_yields_empty_string() -> None:
    assert format(parse("")) == ""
    assert format(Forwarded()) == ""


def test_edge_normalize_empty_forwarded_yields_empty() -> None:
    assert normalize(parse("")) == Forwarded()


def test_edge_format_non_forwarded_raises_type_error() -> None:
    with pytest.raises(TypeError):
        format("for=192.0.2.43")  # type: ignore[arg-type]


def test_edge_normalize_non_forwarded_raises_type_error() -> None:
    with pytest.raises(TypeError):
        normalize("for=192.0.2.43")  # type: ignore[arg-type]


def test_edge_element_dataclass_frozen() -> None:
    """``ForwardedElement`` is frozen — attribute assignment fails."""
    elem = ForwardedElement(for_=("192.0.2.43",))
    with pytest.raises((AttributeError, Exception)):
        elem.by = "203.0.113.60"  # type: ignore[misc]


def test_edge_forwarded_dataclass_frozen() -> None:
    """``Forwarded`` is frozen."""
    fwd = Forwarded()
    with pytest.raises((AttributeError, Exception)):
        fwd.elements = ()  # type: ignore[misc]


def test_edge_iter_yields_elements_in_order() -> None:
    parsed = parse("for=192.0.2.43, for=198.51.100.17, for=203.0.113.60")
    seen = [e.for_[0] for e in parsed]
    assert seen == ["192.0.2.43", "198.51.100.17", "203.0.113.60"]


def test_edge_normalize_strips_empty_for_values() -> None:
    """``normalize`` drops empty strings inside ``for_``."""
    fwd = Forwarded(
        elements=(
            ForwardedElement(for_=("192.0.2.43", ""), by="203.0.113.60"),
        )
    )
    n = normalize(fwd)
    assert n.elements[0].for_ == ("192.0.2.43",)


def test_edge_normalize_empty_for_tuple_yields_empty_element() -> None:
    """An element with no ``for_`` entries round-trips with empty ``for_``."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host="example.com"),)
    )
    n = normalize(fwd)
    # Format will omit the empty ``for=`` entirely, producing ``host=...``
    # only — that is still a single element.
    assert format(n) == "host=example.com"
