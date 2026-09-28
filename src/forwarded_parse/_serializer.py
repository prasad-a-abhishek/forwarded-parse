"""RFC 7239 Forwarded header canonical serializer.

The canonical form is:

* Elements separated by ``, `` (comma + single space).
* Within each element, pairs separated by ``;`` (no surrounding whitespace).
* ``for=`` values appear before ``by=``, ``host=``, ``proto=`` (this
  matches the order in RFC 7239 §7 reference examples).
* Within the ``for=`` list, values are emitted in input order
  (preserving the proxy chain).
* All four known keys (``for`` / ``by`` / ``host`` / ``proto``) are
  emitted in this fixed order; ``for`` repeats if necessary.
* Obfuscated values (leading ``_``) are preserved verbatim and always
  emitted as bare tokens — RFC 7239 §6.3 prohibits quoting them.

The serializer is the **round-trip oracle**: ``format(parse(h)) ==
format(parse(format(parse(h))))`` for every input ``h``.
"""

from __future__ import annotations

from ._parser import _ElementDict


# Characters that require quoting when serialising back to a header value.
# Per RFC 7230 §3.2.6, a token is composed of tchar only — anything else
# inside a value MUST be wrapped in double quotes. We conservatively quote
# when any non-tchar (besides underscore, which is part of tchar) appears.
_QUOTE_REQUIRED = set('"(),;:\\/<=>?@[]{} \t')


def _needs_quoting(value: str) -> bool:
    if not value:
        return True
    for c in value:
        if c in _QUOTE_REQUIRED:
            return True
    return False


def _quote(value: str) -> str:
    """Serialise a value: token form if possible, quoted-string otherwise.

    Backslash and double-quote are escaped inside quoted-strings per
    RFC 7230 §3.2.6.
    """
    if _needs_quoting(value):
        escaped: list[str] = []
        for c in value:
            if c in ('"', "\\"):
                escaped.append("\\")
            escaped.append(c)
        return '"' + "".join(escaped) + '"'
    return value


def _format_for(value: str) -> str:
    """Format a single ``for=`` value — tokens verbatim, never quoted."""
    # Obfuscated (leading ``_``) values: bare token, never quoted. RFC
    # 7239 §6.3 explicitly says proxies MUST forward obfuscated tokens
    # without inspection.
    if value and value[0] == "_":
        return "for=" + value
    # Non-obfuscated ``for=`` values that contain non-tchar bytes (e.g.
    # IPv6 literal ``[2001:db8::1]``) require quoting per RFC 7230.
    if _needs_quoting(value):
        return "for=" + _quote(value)
    return "for=" + value


def format_element(element: _ElementDict) -> str:
    """Serialise a single forwarding element to its canonical string."""
    parts: list[str] = []
    for v in element["for_"]:
        parts.append(_format_for(v))
    if element["by"] is not None:
        parts.append("by=" + _quote(element["by"]))
    if element["host"] is not None:
        parts.append("host=" + _quote(element["host"]))
    if element["proto"] is not None:
        parts.append("proto=" + _quote(element["proto"]))
    return ";".join(parts)


def format_forwarded(elements: list[_ElementDict]) -> str:
    """Serialise a list of element dicts to the canonical Forwarded form."""
    if not elements:
        return ""
    return ", ".join(format_element(e) for e in elements)
