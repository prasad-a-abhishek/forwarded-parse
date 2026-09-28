"""AC4 — RFC 7230 §3.2.4 obs-fold handling."""

from __future__ import annotations

import pytest

from forwarded_parse import format, parse


def test_obs_fold_basic() -> None:
    """A ``\\r\\n\\t`` continuation is joined before parsing."""
    folded = "for=192.0.2.43,\r\n\tfor=198.51.100.17"
    parsed = parse(folded)
    assert len(parsed.elements) == 2
    assert parsed.elements[0].for_ == ("192.0.2.43",)
    assert parsed.elements[1].for_ == ("198.51.100.17",)


def test_obs_fold_space_continuation() -> None:
    """A ``\\r\\n  `` continuation is joined before parsing."""
    folded = "for=192.0.2.43;\r\n  by=203.0.113.60"
    parsed = parse(folded)
    assert len(parsed.elements) == 1
    assert parsed.elements[0].for_ == ("192.0.2.43",)
    assert parsed.elements[0].by == "203.0.113.60"


def test_obs_fold_equivalent_to_unfolded() -> None:
    """AC4 — folded and unfolded headers parse to the same result."""
    unfolded = "for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https"
    folded = "for=192.0.2.43,\r\n for=198.51.100.17;by=203.0.113.60;\r\n\thost=example.com;proto=https"
    assert format(parse(unfolded)) == format(parse(folded))


def test_obs_fold_multiple_continuations() -> None:
    """Chained ``\\r\\n \\r\\n \\r\\n \\t`` are all joined."""
    folded = "for=192.0.2.43;\r\n by=\r\n \r\n \t203.0.113.60"
    parsed = parse(folded)
    assert parsed.elements[0].for_ == ("192.0.2.43",)
    assert parsed.elements[0].by == "203.0.113.60"


def test_obs_fold_inside_quoted_string_preserved() -> None:
    """obs-fold join runs before tokenization; quoted content is preserved."""
    folded = 'host="example.com";\r\n proto=https'
    parsed = parse(folded)
    assert parsed.elements[0].host == "example.com"
    assert parsed.elements[0].proto == "https"


def test_obs_fold_lf_only_is_not_obs_fold() -> None:
    """Bare ``\\n`` is NOT an obs-fold — only ``\\r\\n`` + SP/HTAB counts.

    Bare ``\\n`` inside an unquoted token is a parse error (tokens cannot
    contain CR or LF per RFC 7230 §3.2.6).
    """
    import pytest

    from forwarded_parse import ForwardedParseError

    with pytest.raises(ForwardedParseError):
        parse("for=192.0.2.43\nfor=198.51.100.17")


def test_obs_fold_format_round_trip() -> None:
    """AC7 — format() then re-parse must match."""
    folded = "for=192.0.2.43;\r\n by=203.0.113.60;\r\n\thost=example.com"
    canonical = format(parse(folded))
    assert format(parse(canonical)) == canonical


def test_obs_fold_only_folded_yields_one_element() -> None:
    """A fully folded continuation collapses to a single element."""
    folded = "for=192.0.2.43;\r\n by=203.0.113.60;\r\n host=example.com;\r\n proto=https"
    parsed = parse(folded)
    assert len(parsed.elements) == 1
    elem = parsed.elements[0]
    assert elem.for_ == ("192.0.2.43",)
    assert elem.by == "203.0.113.60"
    assert elem.host == "example.com"
    assert elem.proto == "https"


@pytest.mark.parametrize(
    "continuation",
    ["\r\n ", "\r\n\t", "\r\n    "],
)
def test_obs_fold_continuation_variants(continuation: str) -> None:
    """Any whitespace continuation (1+ SP/HTAB) joins per RFC 7230."""
    folded = "for=192.0.2.43" + continuation + "by=203.0.113.60"
    parsed = parse(folded)
    assert parsed.elements[0].by == "203.0.113.60"


def test_obs_fold_does_not_split_quoted_comma() -> None:
    """A comma inside a quoted-string is NOT a splitter even across folds."""
    # obs-fold inside a quoted-string — the comma inside the quotes should
    # remain part of the value, not trigger a new element.
    folded = 'host="example,com";\r\n proto=https'
    parsed = parse(folded)
    assert parsed.elements[0].host == "example,com"
    assert parsed.elements[0].proto == "https"
