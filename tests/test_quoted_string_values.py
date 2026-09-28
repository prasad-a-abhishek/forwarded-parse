"""AC6 — quoted-string values (RFC 7230 §3.2.6)."""

from __future__ import annotations

import pytest

from forwarded_parse import ForwardedParseError, format, parse


def test_quoted_string_host_basic() -> None:
    parsed = parse('host="example.com"')
    assert parsed.elements[0].host == "example.com"


def test_quoted_string_proto_basic() -> None:
    parsed = parse('proto="https"')
    assert parsed.elements[0].proto == "https"


def test_quoted_string_host_and_proto() -> None:
    parsed = parse('host="example.com";proto="https"')
    elem = parsed.elements[0]
    assert elem.host == "example.com"
    assert elem.proto == "https"


def test_quoted_string_for_ipv6_literal() -> None:
    parsed = parse('for="[2001:db8::1]"')
    assert parsed.elements[0].for_ == ("[2001:db8::1]",)


def test_quoted_string_for_ipv6_with_port() -> None:
    parsed = parse('for="[2001:db8::1]:443"')
    assert parsed.elements[0].for_ == ("[2001:db8::1]:443",)


def test_quoted_string_backslash_escapes_quote() -> None:
    """``\\\\"`` inside a quoted-string decodes to ``"``."""
    parsed = parse(r'host="example\"com"')
    assert parsed.elements[0].host == 'example"com'


def test_quoted_string_backslash_escapes_backslash() -> None:
    """``\\\\\\\\`` inside a quoted-string decodes to ``\\``."""
    parsed = parse(r'host="example\\com"')
    assert parsed.elements[0].host == "example\\com"


def test_quoted_string_with_spaces() -> None:
    """Quoted-strings preserve interior whitespace."""
    parsed = parse('host="example . com"')
    assert parsed.elements[0].host == "example . com"


def test_quoted_string_with_semicolon_inside() -> None:
    """``;`` inside a quoted-string is NOT a pair separator."""
    parsed = parse('host="example;com";proto=https')
    assert parsed.elements[0].host == "example;com"
    assert parsed.elements[0].proto == "https"


def test_quoted_string_with_comma_inside() -> None:
    """``-`` inside a quoted-string is NOT a list separator."""
    parsed = parse('host="example,com";proto=https')
    assert parsed.elements[0].host == "example,com"


def test_quoted_string_round_trip_with_special_chars() -> None:
    """Quoted-strings re-emit as quoted-strings when they contain ``;`` or ``,``."""
    h = 'host="example.com";proto=https'
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_quoted_string_round_trip_ipv6() -> None:
    h = 'for="[2001:db8::1]"'
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical
    assert canonical == 'for="[2001:db8::1]"'


def test_quoted_string_unterminated_raises() -> None:
    """An unterminated quoted-string raises ``ForwardedParseError``."""
    with pytest.raises(ForwardedParseError):
        parse('host="example.com')


def test_quoted_string_with_only_open_quote() -> None:
    """A lonely opening quote raises."""
    with pytest.raises(ForwardedParseError):
        parse('host="')


def test_quoted_string_empty_value() -> None:
    """An empty quoted-string ``""`` is a valid (empty) value."""
    parsed = parse('host=""')
    assert parsed.elements[0].host == ""


@pytest.mark.parametrize(
    "h,expected",
    [
        ('host="example.com"', "example.com"),
        ('host="a"', "a"),
        ('host="a-b_c.d"', "a-b_c.d"),
        ('host="123"', "123"),
        ('host="ABC"', "ABC"),
    ],
)
def test_quoted_string_various(h: str, expected: str) -> None:
    parsed = parse(h)
    assert parsed.elements[0].host == expected
