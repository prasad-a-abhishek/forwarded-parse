"""Internal helper / unit tests for the parser primitives."""

from __future__ import annotations

import pytest

from forwarded_parse._errors import ForwardedParseError
from forwarded_parse._parser import (
    _is_obfuscated,
    _is_token_char,
    _parse_element,
    _parse_pair,
    _parse_value,
    _split_top_level,
    _strip_ows,
    iter_pairs,
    parse_forwarded,
    unfold_obs_fold,
)


# ---------------------------------------------------------------------------
# unfold_obs_fold
# ---------------------------------------------------------------------------


def test_unfold_obs_fold_no_change_when_no_crlf() -> None:
    assert unfold_obs_fold("for=192.0.2.43") == "for=192.0.2.43"


def test_unfold_obs_fold_joins_crlf_space() -> None:
    assert unfold_obs_fold("a\r\n b") == "a b"


def test_unfold_obs_fold_joins_crlf_tab() -> None:
    assert unfold_obs_fold("a\r\n\tb") == "a b"


def test_unfold_obs_fold_multiple_continuations() -> None:
    assert unfold_obs_fold("a\r\n b\r\n\tc") == "a b c"


def test_unfold_obs_fold_lf_only_unchanged() -> None:
    """Bare ``\\n`` without continuation is not an obs-fold."""
    assert unfold_obs_fold("a\nb") == "a\nb"


def test_unfold_obs_fold_crlf_no_whitespace_unchanged() -> None:
    """``\\r\\n`` not followed by SP/HTAB is not an obs-fold."""
    assert unfold_obs_fold("a\r\nb") == "a\r\nb"


def test_unfold_obs_fold_empty() -> None:
    assert unfold_obs_fold("") == ""


# ---------------------------------------------------------------------------
# _is_token_char
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "c",
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    + list("!#$%&'*+-.^_`|~"),
)
def test_is_token_char_accepts_tchar(c: str) -> None:
    assert _is_token_char(c) is True


@pytest.mark.parametrize("c", list(" \t\r\n,;:\\/<=>?@[]{}()\""))
def test_is_token_char_rejects_non_tchar(c: str) -> None:
    assert _is_token_char(c) is False


# ---------------------------------------------------------------------------
# _split_top_level
# ---------------------------------------------------------------------------


def test_split_top_level_basic() -> None:
    assert _split_top_level("a,b,c", ",") == ["a", "b", "c"]


def test_split_top_level_preserves_quoted_comma() -> None:
    assert _split_top_level('"a,b",c', ",") == ['"a,b"', "c"]


def test_split_top_level_preserves_quoted_semicolon() -> None:
    assert _split_top_level('"a;b";c', ";") == ['"a;b"', "c"]


def test_split_top_level_with_backslash_escapes() -> None:
    assert _split_top_level(r'"a\"b",c', ",") == [r'"a\"b"', "c"]


def test_split_top_level_no_separator() -> None:
    assert _split_top_level("abc", ",") == ["abc"]


def test_split_top_level_trailing_separator() -> None:
    assert _split_top_level("a,", ",") == ["a", ""]


def test_split_top_level_leading_separator() -> None:
    assert _split_top_level(",a", ",") == ["", "a"]


# ---------------------------------------------------------------------------
# _strip_ows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "s,expected",
    [
        ("", ""),
        ("   ", ""),
        ("\t\t", ""),
        ("abc", "abc"),
        ("  abc  ", "abc"),
        ("\tabc\t", "abc"),
        ("  abc\t", "abc"),
    ],
)
def test_strip_ows(s: str, expected: str) -> None:
    assert _strip_ows(s) == expected


# ---------------------------------------------------------------------------
# _parse_value
# ---------------------------------------------------------------------------


def test_parse_value_simple_token() -> None:
    assert _parse_value("abc") == "abc"


def test_parse_value_ip() -> None:
    assert _parse_value("192.0.2.43") == "192.0.2.43"


def test_parse_value_quoted() -> None:
    assert _parse_value('"hello"') == "hello"


def test_parse_value_quoted_with_space() -> None:
    assert _parse_value('"hello world"') == "hello world"


def test_parse_value_quoted_with_escaped_quote() -> None:
    assert _parse_value(r'"a\"b"') == 'a"b'


def test_parse_value_unterminated_raises() -> None:
    with pytest.raises(ForwardedParseError):
        _parse_value('"abc')


def test_parse_value_invalid_char_raises() -> None:
    with pytest.raises(ForwardedParseError):
        _parse_value("abc def")


def test_parse_value_empty_raises() -> None:
    with pytest.raises(ForwardedParseError):
        _parse_value("")


# ---------------------------------------------------------------------------
# _is_obfuscated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "v,expected",
    [
        ("_x", True),
        ("_secret123", True),
        ("_", True),
        ("secret", False),
        ("x_secret", False),
        ("", False),
        ("[2001:db8::1]", False),
    ],
)
def test_is_obfuscated(v: str, expected: bool) -> None:
    assert _is_obfuscated(v) is expected


# ---------------------------------------------------------------------------
# _parse_pair
# ---------------------------------------------------------------------------


def test_parse_pair_simple() -> None:
    assert _parse_pair("for=192.0.2.43") == ("for", "192.0.2.43")


def test_parse_pair_with_whitespace() -> None:
    assert _parse_pair("  for=192.0.2.43  ") == ("for", "192.0.2.43")


def test_parse_pair_unknown_returns_none() -> None:
    assert _parse_pair("future_key=value") is None


def test_parse_pair_obfuscated() -> None:
    assert _parse_pair("for=_opaque") == ("for", "_opaque")


def test_parse_pair_no_equals_raises() -> None:
    with pytest.raises(ForwardedParseError):
        _parse_pair("novalue")


def test_parse_pair_empty_name_raises() -> None:
    with pytest.raises(ForwardedParseError):
        _parse_pair("=value")


def test_parse_pair_empty_returns_none() -> None:
    assert _parse_pair("") is None


# ---------------------------------------------------------------------------
# _parse_element
# ---------------------------------------------------------------------------


def test_parse_element_single_for() -> None:
    elem = _parse_element("for=192.0.2.43")
    assert elem == {"for_": ["192.0.2.43"], "by": None, "host": None, "proto": None}


def test_parse_element_full() -> None:
    elem = _parse_element(
        "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https"
    )
    assert elem == {
        "for_": ["192.0.2.43"],
        "by": "203.0.113.60",
        "host": "example.com",
        "proto": "https",
    }


def test_parse_element_for_chaining() -> None:
    elem = _parse_element("for=192.0.2.43;for=198.51.100.17")
    assert elem is not None
    assert elem["for_"] == ["192.0.2.43", "198.51.100.17"]


def test_parse_element_empty_returns_none() -> None:
    assert _parse_element("") is None
    assert _parse_element("   ") is None


def test_parse_element_only_unknown_keys() -> None:
    # F-001 fix: an element whose pairs are all unknown extension keys
    # (RFC 7239 §4) must be dropped by the parser, not retained as a
    # phantom dict with for_=[] and all scalars None. ``_parse_element``
    # returns ``None`` so the outer ``parse_forwarded`` loop filters it.
    assert _parse_element("foo=bar;baz=qux") is None


# ---------------------------------------------------------------------------
# parse_forwarded (top-level)
# ---------------------------------------------------------------------------


def test_parse_forwarded_basic() -> None:
    elements = parse_forwarded("for=192.0.2.43, for=198.51.100.17")
    assert len(elements) == 2


def test_parse_forwarded_invalid_type() -> None:
    with pytest.raises(ForwardedParseError):
        parse_forwarded(b"bytes")  # type: ignore[arg-type]


def test_iter_pairs_yields_all_known() -> None:
    pairs = list(iter_pairs("for=192.0.2.43;for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https"))
    assert pairs == [
        ("for", "192.0.2.43"),
        ("for", "198.51.100.17"),
        ("by", "203.0.113.60"),
        ("host", "example.com"),
        ("proto", "https"),
    ]


def test_iter_pairs_skips_none_fields() -> None:
    pairs = list(iter_pairs("for=192.0.2.43"))
    assert pairs == [("for", "192.0.2.43")]
