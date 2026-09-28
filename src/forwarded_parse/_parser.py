"""RFC 7239 Forwarded header parser — internal state machine.

Implements the BNF in RFC 7239 §4:

    forwarded-pair     = token "=" value
    forwarded-element  = [ forwarded-pair ] *( ";" [ forwarded-pair ] )
    value              = nodename / node / quoted-string
    node               = nodename [ node-identifier ]
    node-identifier    = "=" nodename
    nodename           = token  (as defined in RFC 7230 §3.2.6)

The leading-underscore obfuscated form (``for=_anything``) is per RFC 7239
§6.3 — preserved verbatim as an opaque string; we never try to resolve or
sanitise it. Other parameters whose value begins with ``_`` are also
preserved verbatim because the RFC only requires the obfuscation for ``for=``
but we apply the same rule uniformly to avoid information loss.

obs-fold handling (RFC 7230 §3.2.4): a ``CRLF`` followed by ``SP`` or
``HTAB`` is joined to a single space before parsing. ``CRLF`` without
trailing whitespace is preserved as a normal end-of-line marker (we only
operate on the header value as passed in, so the caller is responsible for
isolating a single header field).

Unknown pair names (anything other than ``for`` / ``by`` / ``host`` /
``proto``) are silently ignored per the RFC's extension rule (forwarded-pair
is a token, but downstream consumers MUST NOT reject on unknown names — we
mirror that here so a future RFC adding ``proto-version`` etc. does not
break older parsers).
"""

from __future__ import annotations

from typing import Iterator, TypedDict

from ._errors import ForwardedParseError


class _ElementDict(TypedDict):
    for_: list[str]
    by: str | None
    host: str | None
    proto: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def unfold_obs_fold(value: str) -> str:
    """Join ``CRLF`` obs-fold continuations per RFC 7230 §3.2.4.

    A ``CRLF`` followed by one-or-more ``SP`` / ``HTAB`` characters is
    replaced by a single ``SP``. Bare ``CRLF`` (no continuation) is left
    alone so the caller can decide what to do (the parser only sees one
    logical header value at a time).
    """
    if "\r\n" not in value:
        return value
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        if i + 2 < n and value[i] == "\r" and value[i + 1] == "\n" and value[i + 2] in (" ", "\t"):
            # Consume ALL SP/HTAB after CRLF (one logical space).
            j = i + 2
            while j < n and value[j] in (" ", "\t"):
                j += 1
            out.append(" ")
            i = j
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _is_token_char(c: str) -> bool:
    """RFC 7230 §3.2.6 ``token`` character set.

    token = 1*tchar
    tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*"
          / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~"
          / DIGIT / ALPHA
    """
    if not c:
        return False
    if c.isalnum():
        return True
    return c in "!#$%&'*+-.^_`|~"


def _is_ows(c: str) -> bool:
    return c == " " or c == "\t"


# ---------------------------------------------------------------------------
# Low-level splitter that respects quoted-strings
# ---------------------------------------------------------------------------


def _split_top_level(value: str, sep: str) -> list[str]:
    """Split ``value`` on ``sep`` at the top level only.

    Quoted-strings (with backslash escapes) are skipped so ``sep`` inside
    them does not split. This is sufficient for ``,`` (element split) and
    ``;`` (pair split) since neither ``,`` nor ``;`` can appear inside an
    unquoted value per RFC 7230 token rules.

    OWS (SP / HTAB) immediately around the separator is consumed per
    RFC 7239 §4 ``forwarded-element = [ forwarded-pair ] *( ";" [ forwarded-pair ] )``
    — the OWS inside the element is optional, not required, but obs-fold
    unfolding may introduce spaces adjacent to a separator that must be
    tolerated.

    If ``sep == ";"`` we *also* split on runs of OWS at the top level —
    RFC 7239 §4 implicitly allows OWS between pairs (every other HTTP
    structured-header grammar in RFC 8941 does the same). This handles
    post-obs-fold values like ``"for=a by=b"`` where the obs-fold join
    introduced a single space between two pairs.
    """
    out: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(value)
    in_quotes = False
    while i < n:
        c = value[i]
        if c == "\\" and in_quotes and i + 1 < n:
            buf.append(c)
            buf.append(value[i + 1])
            i += 2
            continue
        if c == '"':
            in_quotes = not in_quotes
            buf.append(c)
            i += 1
            continue
        if not in_quotes and c == sep:
            # Strip OWS adjacent to the separator on the buf side.
            while buf and _is_ows(buf[-1]):
                buf.pop()
            # Skip OWS on the right side of the separator.
            j = i + 1
            while j < n and _is_ows(value[j]):
                j += 1
            out.append("".join(buf))
            buf = []
            i = j
            continue
        # Treat runs of OWS at top level as if they were the separator
        # — but ONLY when sep is ``;`` (pair split) AND the buffer ends
        # in a complete name=value pair (i.e. the buffer does NOT end
        # with ``=``, which would mean the value is still being parsed).
        # Whitespace between pairs is RFC-7239-acceptable per the §4
        # implicit-OWS rule, but whitespace inside a token value is
        # forbidden.
        if (
            not in_quotes
            and sep == ";"
            and _is_ows(c)
            and buf
            and buf[-1] != "="
            and not _is_ows(buf[-1])
        ):
            # Flush current buffer and consume the rest of the OWS run.
            out.append("".join(buf))
            buf = []
            j = i
            while j < n and _is_ows(value[j]):
                j += 1
            i = j
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf))
    return out


# ---------------------------------------------------------------------------
# Value parser
# ---------------------------------------------------------------------------


def _strip_ows(s: str) -> str:
    """Strip optional whitespace (RFC 7230 §3.2.3 OWS) from both ends."""
    left = 0
    right = len(s)
    while left < right and _is_ows(s[left]):
        left += 1
    while right > left and _is_ows(s[right - 1]):
        right -= 1
    return s[left:right]


def _parse_value(raw: str) -> str:
    """Parse a single parameter value, supporting token and quoted-string.

    Returns the unquoted (with backslash-escapes resolved) value.
    Raises :class:`ForwardedParseError` on malformed quoted-string.
    """
    s = _strip_ows(raw)
    if not s:
        raise ForwardedParseError(
            "empty value",
            position=0,
        )
    if s[0] == '"':
        if len(s) < 2 or s[-1] != '"':
            raise ForwardedParseError(
                "unterminated quoted-string",
                position=0,
            )
        inner = s[1:-1]
        # RFC 7230 §3.2.6: backslash-escapes only ``"`` and ``\\``.
        out: list[str] = []
        i = 0
        while i < len(inner):
            c = inner[i]
            if c == "\\" and i + 1 < len(inner) and inner[i + 1] in ('"', "\\"):
                out.append(inner[i + 1])
                i += 2
                continue
            if c == "\\":
                # Bare backslash inside quoted-string — preserve verbatim.
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
        return "".join(out)
    # token form: each char must be a tchar.
    for idx, c in enumerate(s):
        if not _is_token_char(c):
            raise ForwardedParseError(
                f"invalid character {c!r} in token value",
                position=idx,
            )
    return s


def _is_obfuscated(value: str) -> bool:
    """RFC 7239 §6.3 obfuscated token form.

    A value is opaque-to-proxy if its first character (after optional
    leading underscore) is ``_`` — i.e. it begins with ``_``. We treat
    *any* value starting with ``_`` as opaque and preserve it verbatim
    because the RFC says the proxy MUST forward it without inspection.
    """
    return bool(value) and value[0] == "_"


# ---------------------------------------------------------------------------
# Pair parser
# ---------------------------------------------------------------------------


_KNOWN_KEYS = frozenset({"for", "by", "host", "proto"})


def _parse_pair(raw: str) -> tuple[str, str] | None:
    """Parse a single ``name=value`` pair (inside one element).

    Returns ``(name, value)`` or ``None`` for empty / malformed input
    (which the caller treats as a missing pair).

    Per RFC 7230 §3.2.6, parameter names (the token on the left of ``=``)
    are case-insensitive. The library normalises known names to lowercase;
    values are preserved verbatim because RFC 7239 §6.3 (e.g. obfuscated
    tokens) is value-case-sensitive.
    """
    s = _strip_ows(raw)
    if not s:
        return None
    eq = s.find("=")
    if eq <= 0:
        # ``=`` missing or leading — not a valid forwarded-pair.
        raise ForwardedParseError(
            f"malformed forwarded-pair: {raw!r} (expected token=value)",
            position=0,
        )
    name = _strip_ows(s[:eq])
    if not name:
        raise ForwardedParseError(
            f"empty pair name in {raw!r}",
            position=0,
        )
    for idx, c in enumerate(name):
        if not _is_token_char(c):
            raise ForwardedParseError(
                f"invalid character {c!r} in pair name",
                position=idx,
            )
    # Normalise known parameter names to lowercase.
    name_lower = name.lower()
    if name_lower not in _KNOWN_KEYS:
        # Unknown key: silently ignore per RFC 7239 §4 (forwarded-pair is
        # extensible; downstream consumers MUST NOT reject on unknown names).
        # We still must consume the value to advance the parser, but we do
        # not store it.
        # Parse the value for side-effect validation, then discard.
        _parse_value(s[eq + 1 :])
        return None
    value = _parse_value(s[eq + 1 :])
    return (name_lower, value)


# ---------------------------------------------------------------------------
# Element parser
# ---------------------------------------------------------------------------


def _parse_element(raw: str) -> _ElementDict | None:
    """Parse a single comma-separated forwarding element.

    Returns a dict with keys ``for_`` (list[str]), ``by`` (str | None),
    ``host`` (str | None), ``proto`` (str | None); or ``None`` for an
    empty element.
    """
    s = _strip_ows(raw)
    if not s:
        return None
    pairs_raw = _split_top_level(s, ";")
    out: _ElementDict = {
        "for_": [],
        "by": None,
        "host": None,
        "proto": None,
    }
    for pr in pairs_raw:
        parsed = _parse_pair(pr)
        if parsed is None:
            continue
        name, value = parsed
        if name == "for":
            # Multiple ``for=`` allowed per RFC 7239 §6.3.
            out["for_"].append(value)
        else:
            out[name] = value
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_forwarded(value: str) -> list[_ElementDict]:
    """Parse a single Forwarded header value into a list of element dicts.

    Empty / whitespace-only input yields an empty list.
    """
    if value is None:
        raise ForwardedParseError("value must be a string", position=0)
    if not isinstance(value, str):
        raise ForwardedParseError(
            f"value must be str, got {type(value).__name__}",
            position=0,
        )
    unfolded = unfold_obs_fold(value)
    raw_elements = _split_top_level(unfolded, ",")
    elements: list[_ElementDict] = []
    for raw in raw_elements:
        element = _parse_element(raw)
        if element is not None:
            elements.append(element)
    return elements


def iter_pairs(value: str) -> Iterator[tuple[str, str]]:
    """Yield ``(name, value)`` tuples for every known pair (test helper)."""
    for element in parse_forwarded(value):
        for_ = element["for_"]
        for v in for_:
            yield ("for", v)
        for k in ("by", "host", "proto"):
            v = element[k]
            if v is not None:
                yield (k, v)
