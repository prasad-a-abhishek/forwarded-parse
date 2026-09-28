"""AC7 — format() round-trip property on RFC 7239 §7 reference examples."""

from __future__ import annotations

import pytest

from forwarded_parse import format, normalize, parse


# RFC 7239 §7 reference examples (paraphrased; see SPEC §9 AC7).
# Each tuple is (input_header, expected_canonical).
RFC7239_SECTION7_EXAMPLES: list[tuple[str, str]] = [
    # §7 single node example
    (
        "For=192.0.2.43;by=203.0.113.60;proto=https;host=example.com",
        "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https",
    ),
    # §7 chained for= example
    (
        "For=192.0.2.43, For=198.51.100.17;By=203.0.113.60;Host=example.com;Proto=https",
        "for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https",
    ),
    # §7 obfuscated example
    (
        "For=_hidden;By=203.0.113.60",
        "for=_hidden;by=203.0.113.60",
    ),
    # §7 IPv6 literal example
    (
        'For="[2001:db8::1]:443";By=203.0.113.60',
        'for="[2001:db8::1]:443";by=203.0.113.60',
    ),
    # §7 host quoted-string example
    (
        'Host="example.com";Proto=https',
        "host=example.com;proto=https",
    ),
]


def test_rfc7239_section7_single_node() -> None:
    """The canonical RFC 7239 §7 single-node example round-trips."""
    h = "For=192.0.2.43;by=203.0.113.60;proto=https;host=example.com"
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical
    assert canonical == (
        "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https"
    )


def test_rfc7239_section7_chained_for() -> None:
    """RFC 7239 §7 chained-for example round-trips."""
    h = (
        "For=192.0.2.43, For=198.51.100.17;By=203.0.113.60;"
        "Host=example.com;Proto=https"
    )
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_rfc7239_section7_obfuscated() -> None:
    """RFC 7239 §7 obfuscated-token example round-trips."""
    h = "For=_hidden;By=203.0.113.60"
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_rfc7239_section7_ipv6_literal() -> None:
    """RFC 7239 §7 IPv6 literal example round-trips."""
    h = 'For="[2001:db8::1]";By=203.0.113.60'
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


def test_rfc7239_section7_host_quoted() -> None:
    """RFC 7239 §7 host quoted-string example round-trips."""
    h = 'Host="example.com";Proto=https'
    canonical = format(parse(h))
    assert format(parse(canonical)) == canonical


@pytest.mark.parametrize(
    "h,expected_canonical",
    RFC7239_SECTION7_EXAMPLES,
    ids=[
        "single-node",
        "chained-for",
        "obfuscated",
        "ipv6-literal",
        "host-quoted",
    ],
)
def test_rfc7239_section7_examples_round_trip(
    h: str, expected_canonical: str
) -> None:
    """AC7 — every RFC 7239 §7 example is fixed-point under parse→format→parse→format."""
    canonical = format(parse(h))
    assert canonical == expected_canonical
    # Re-parse and re-format must match.
    assert format(parse(canonical)) == canonical


def test_rfc7239_section7_double_parse_idempotent() -> None:
    """``format(parse(format(parse(h)))) == format(parse(h))`` for every §7 example."""
    for h, _ in RFC7239_SECTION7_EXAMPLES:
        once = format(parse(h))
        twice = format(parse(once))
        thrice = format(parse(twice))
        assert once == twice == thrice


def test_rfc7239_section7_normalize_is_idempotent() -> None:
    """Normalize is idempotent on §7 examples."""
    for h, _ in RFC7239_SECTION7_EXAMPLES:
        n1 = normalize(parse(h))
        n2 = normalize(n1)
        assert format(n1) == format(n2)


@pytest.mark.parametrize(
    "h",
    [
        "for=192.0.2.43",
        "for=192.0.2.43;by=203.0.113.60",
        "for=192.0.2.43, for=198.51.100.17",
        "for=_secret",
        'for="[2001:db8::1]"',
        'host="example.com";proto=https',
        "for=192.0.2.43;for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https",
    ],
)
def test_round_trip_idempotent(h: str) -> None:
    """Format→parse→format is idempotent on a representative set of inputs."""
    once = format(parse(h))
    twice = format(parse(once))
    thrice = format(parse(twice))
    assert once == twice == thrice


@pytest.mark.parametrize(
    "h",
    [
        "for=192.0.2.43",
        "for=192.0.2.43;by=203.0.113.60",
        "for=_opaque, for=192.0.2.43",
        'for="[2001:db8::1]"',
    ],
)
def test_format_re_parsing_yields_same_elements(h: str) -> None:
    """After format→parse, the elements list is unchanged (by content)."""
    from forwarded_parse import ForwardedElement

    once = parse(h)
    twice = parse(format(once))
    assert len(once.elements) == len(twice.elements)
    for a, b in zip(once.elements, twice.elements):
        assert isinstance(a, ForwardedElement)
        assert a.for_ == b.for_
        assert a.by == b.by
        assert a.host == b.host
        assert a.proto == b.proto
