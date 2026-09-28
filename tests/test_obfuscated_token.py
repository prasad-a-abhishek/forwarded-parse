"""AC3 — RFC 7239 §6.3 obfuscated token form."""

from __future__ import annotations

import pytest

from forwarded_parse import format, parse


def test_obfuscated_token_basic() -> None:
    """Single ``for=_quoted`` parses to a verbatim opaque token."""
    parsed = parse("for=_secret123")
    assert parsed.elements[0].for_ == ("_secret123",)


def test_obfuscated_token_with_by() -> None:
    """``for=_quoted;by=_xy1234`` (SPEC §9 AC3 example)."""
    parsed = parse("for=_quoted;by=_xy1234")
    elem = parsed.elements[0]
    assert elem.for_ == ("_quoted",)
    assert elem.by == "_xy1234"


def test_obfuscated_token_chained_for() -> None:
    """Obfuscated ``for`` can chain with regular ``for`` in one element."""
    parsed = parse("for=_secret123, for=192.0.2.43")
    assert parsed.elements[0].for_ == ("_secret123",)
    assert parsed.elements[1].for_ == ("192.0.2.43",)


def test_obfuscated_token_format_preserves_verbatim() -> None:
    """Format() emits the obfuscated value as a bare token (no quotes)."""
    parsed = parse("for=_secret123")
    assert format(parsed) == "for=_secret123"


def test_obfuscated_token_with_all_params() -> None:
    """Obfuscated ``for`` alongside every other parameter."""
    parsed = parse("for=_hidden;by=_proxy42;host=_internal;proto=_vpn")
    elem = parsed.elements[0]
    assert elem.for_ == ("_hidden",)
    assert elem.by == "_proxy42"
    assert elem.host == "_internal"
    assert elem.proto == "_vpn"


@pytest.mark.parametrize(
    "token",
    [
        "_",
        "_a",
        "_abc123",
        "_quoted",
        "_xy1234",
        "_x",
        "_9",
    ],
)
def test_obfuscated_token_various_shapes(token: str) -> None:
    """All obfuscated tokens start with ``_`` and are preserved verbatim."""
    parsed = parse(f"for={token}")
    assert parsed.elements[0].for_ == (token,)


def test_obfuscated_token_round_trip() -> None:
    """AC7 round-trip on an obfuscated input."""
    h = "for=_secret123, for=192.0.2.43;proto=https"
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_obfuscated_token_quoted_string_value_still_obfuscated() -> None:
    """``for="_anything"`` (quoted) — the leading ``_`` is still opaque."""
    parsed = parse('for="_opaque"')
    # The underscore is in the value; the RFC says the value MUST start
    # with ``_`` to be opaque — quoted form still preserves the underscore.
    assert parsed.elements[0].for_ == ("_opaque",)


def test_obfuscated_token_format_with_underscore_in_value() -> None:
    """Format emits obfuscated values verbatim, never as quoted-strings."""
    parsed = parse("for=_opaque")
    assert format(parsed) == "for=_opaque"


def test_obfuscated_token_non_underscore_does_not_obfuscate() -> None:
    """A non-underscore leading character is a normal token, not opaque."""
    parsed = parse("for=secret123")
    assert parsed.elements[0].for_ == ("secret123",)
    assert format(parsed) == "for=secret123"
