"""forwarded-parse — pure-Python, zero-dependency RFC 7239 Forwarded header parser, serializer, and normalizer.

Public API:

    from forwarded_parse import (
        parse, format, normalize,
        Forwarded, ForwardedElement, ForwardedParseError,
    )

    parsed = parse("for=192.0.2.43, for=198.51.100.17;by=203.0.113.60")
    canonical = format(parsed)
    normalised = normalize(parsed)

See README.md for installation and examples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from ._errors import ForwardedParseError
from ._parser import _ElementDict, parse_forwarded
from ._serializer import format_forwarded


__all__ = [
    "Forwarded",
    "ForwardedElement",
    "ForwardedParseError",
    "format",
    "normalize",
    "parse",
]

__version__ = "0.1.1"


# Canonical key order within an element (matches RFC 7239 §7 examples).
_KEY_ORDER = ("for", "by", "host", "proto")


@dataclass(frozen=True, slots=True)
class ForwardedElement:
    """A single comma-separated forwarding entry from a Forwarded header.

    ``for_`` is a tuple of one-or-more values (RFC 7239 §6.3 permits
    chained ``for=`` parameters within one element). The trailing
    underscore avoids clashing with the ``for`` keyword.

    The other three fields are scalar optionals. ``None`` means the
    parameter was absent in the input (not the empty string).
    """

    for_: tuple[str, ...]
    by: str | None = None
    host: str | None = None
    proto: str | None = None

    def __post_init__(self) -> None:
        # Accept list for ergonomic construction; freeze as tuple.
        if not isinstance(self.for_, tuple):
            object.__setattr__(self, "for_", tuple(self.for_))

    def to_dict(self) -> dict[str, object]:
        """Return a plain dict (handy for JSON serialisation)."""
        return {
            "for": list(self.for_),
            "by": self.by,
            "host": self.host,
            "proto": self.proto,
        }


@dataclass(frozen=True, slots=True)
class Forwarded:
    """A parsed Forwarded header — an ordered list of forwarding elements.

    Empty ``elements`` is the canonical representation of an absent or
    empty Forwarded header value (e.g. ``Forwarded:`` with nothing after
    the colon, or a single obs-fold that collapses to whitespace).
    """

    elements: tuple[ForwardedElement, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.elements, tuple):
            object.__setattr__(self, "elements", tuple(self.elements))

    def __len__(self) -> int:
        return len(self.elements)

    def __iter__(self) -> Iterator[ForwardedElement]:
        return iter(self.elements)

    def __bool__(self) -> bool:
        return bool(self.elements)

    def to_dict(self) -> dict[str, list[dict[str, object]]]:
        """Return a JSON-friendly dict ``{"elements": [...]}``."""
        return {"elements": [e.to_dict() for e in self.elements]}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def parse(value: str) -> Forwarded:
    """Parse a Forwarded header value into a :class:`Forwarded` instance.

    Handles obs-fold (RFC 7230 §3.2.4) by joining CRLF + SP/HTAB
    continuations before parsing. Raises :class:`ForwardedParseError` on
    malformed input (unterminated quoted-string, invalid token chars,
    missing ``=`` in a pair, etc.).
    """
    elements = parse_forwarded(value)
    return Forwarded(
        elements=tuple(
            ForwardedElement(
                for_=tuple(e["for_"]),
                by=e["by"],
                host=e["host"],
                proto=e["proto"],
            )
            for e in elements
        )
    )


def format(parsed: Forwarded) -> str:
    """Serialise a :class:`Forwarded` instance back to canonical header form.

    Round-trip property (AC7):
        ``format(parse(h)) == format(parse(format(parse(h))))``
    for any valid Forwarded header value ``h``.
    """
    if not isinstance(parsed, Forwarded):
        raise TypeError(
            f"format() requires Forwarded, got {type(parsed).__name__}"
        )
    raw_elements: list[_ElementDict] = [
        {
            "for_": list(e.for_),
            "by": e.by,
            "host": e.host,
            "proto": e.proto,
        }
        for e in parsed.elements
    ]
    return format_forwarded(raw_elements)


def normalize(parsed: Forwarded) -> Forwarded:
    """Return a normalised copy of ``parsed``.

    Normalisation rules:

    * Elements are emitted in input order (RFC 7239 §6.3 chain order).
    * ``for_`` values within an element are emitted in input order
      (the proxy chain).
    * Known parameters (``for`` / ``by`` / ``host`` / ``proto``) are
      emitted in canonical key order.
    * Empty strings in ``for_`` are dropped (a value-less ``for=`` is
      not a valid forwarded-pair and the parser already rejects it, but
      a downstream caller may have constructed an empty tuple via the
      dataclass constructor).
    """
    if not isinstance(parsed, Forwarded):
        raise TypeError(
            f"normalize() requires Forwarded, got {type(parsed).__name__}"
        )
    normalised_elements: list[ForwardedElement] = []
    for e in parsed.elements:
        for_ = tuple(v for v in e.for_ if v)
        # Preserve original ordering of by/host/proto relative to each
        # other only when they were present; if any are missing they are
        # simply omitted. The serializer handles canonical key order.
        normalised_elements.append(
            ForwardedElement(
                for_=for_,
                by=e.by,
                host=e.host,
                proto=e.proto,
            )
        )
    return Forwarded(elements=tuple(normalised_elements))
