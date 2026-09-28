"""Serializer-specific tests (canonical format rules)."""

from __future__ import annotations

import pytest

from forwarded_parse import Forwarded, ForwardedElement, format


def test_format_single_element_minimal() -> None:
    fwd = Forwarded(elements=(ForwardedElement(for_=("192.0.2.43",)),))
    assert format(fwd) == "for=192.0.2.43"


def test_format_single_element_full() -> None:
    fwd = Forwarded(
        elements=(
            ForwardedElement(
                for_=("192.0.2.43",),
                by="203.0.113.60",
                host="example.com",
                proto="https",
            ),
        )
    )
    assert (
        format(fwd)
        == "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https"
    )


def test_format_key_order_for_by_host_proto() -> None:
    """The canonical key order is ``for``, ``by``, ``host``, ``proto``."""
    # Construct with shuffled key order.
    fwd = Forwarded(
        elements=(
            ForwardedElement(
                for_=("192.0.2.43",),
                proto="https",
                host="example.com",
                by="203.0.113.60",
            ),
        )
    )
    assert (
        format(fwd)
        == "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https"
    )


def test_format_skips_missing_keys() -> None:
    """Missing keys are simply omitted (not serialised as ``key=``)."""
    fwd = Forwarded(
        elements=(
            ForwardedElement(for_=("192.0.2.43",), host="example.com"),
        )
    )
    assert format(fwd) == "for=192.0.2.43;host=example.com"


def test_format_multiple_elements_joins_with_comma_space() -> None:
    fwd = Forwarded(
        elements=(
            ForwardedElement(for_=("192.0.2.43",)),
            ForwardedElement(for_=("198.51.100.17",), proto="https"),
        )
    )
    assert format(fwd) == "for=192.0.2.43, for=198.51.100.17;proto=https"


def test_format_for_chaining_emits_all() -> None:
    fwd = Forwarded(
        elements=(
            ForwardedElement(
                for_=("192.0.2.43", "198.51.100.17"), by="203.0.113.60"
            ),
        )
    )
    assert format(fwd) == "for=192.0.2.43;for=198.51.100.17;by=203.0.113.60"


def test_format_obfuscated_value_unquoted() -> None:
    """Obfuscated ``for=`` values are emitted as bare tokens (no quotes)."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=("_secret123",)),)
    )
    assert format(fwd) == "for=_secret123"


def test_format_ipv6_literal_quoted() -> None:
    """IPv6 literals (with ``[``/``]``) require quoting per RFC 7230."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=("[2001:db8::1]",)),)
    )
    assert format(fwd) == 'for="[2001:db8::1]"'


def test_format_quoted_string_with_quote_inside() -> None:
    """A ``"`` inside a quoted value is backslash-escaped."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host='example"com'),)
    )
    assert format(fwd) == r'host="example\"com"'


def test_format_empty() -> None:
    assert format(Forwarded()) == ""


def test_format_non_forwarded_raises() -> None:
    with pytest.raises(TypeError):
        format("not a Forwarded")  # type: ignore[arg-type]


def test_format_zero_for_in_element() -> None:
    """An element with no ``for_`` values skips ``for=`` entirely."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host="example.com"),)
    )
    assert format(fwd) == "host=example.com"


def test_format_single_element_no_spaces_around_semicolons() -> None:
    """No OWS around ``;`` in the canonical form."""
    fwd = Forwarded(
        elements=(
            ForwardedElement(for_=("a",), by="b", host="c", proto="d"),
        )
    )
    out = format(fwd)
    assert " " not in out


def test_format_single_element_no_spaces_around_commas_in_value_list() -> None:
    """Elements are separated by ``, `` but pairs inside an element are not."""
    fwd = Forwarded(
        elements=(
            ForwardedElement(for_=("a",)),
            ForwardedElement(for_=("b",)),
        )
    )
    out = format(fwd)
    assert out == "for=a, for=b"


def test_format_value_with_special_chars_quoted() -> None:
    """A ``host`` value containing ``;`` must be quoted."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host="example;com"),)
    )
    assert format(fwd) == 'host="example;com"'


def test_format_value_with_colon_quoted() -> None:
    """A ``host`` value containing ``:`` is quoted."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host="example:8080"),)
    )
    # ``:`` is not a tchar → quoted.
    assert format(fwd) == 'host="example:8080"'


def test_format_value_with_bracket_quoted() -> None:
    """A ``host`` value containing ``[`` is quoted."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), host="[host]"),)
    )
    assert format(fwd) == 'host="[host]"'


def test_format_proto_quoted_when_contains_slash() -> None:
    """A ``proto`` value with ``/`` is quoted (e.g. ``https/2``)."""
    fwd = Forwarded(
        elements=(ForwardedElement(for_=(), proto="https/2"),)
    )
    assert format(fwd) == 'proto="https/2"'
