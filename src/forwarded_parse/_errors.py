"""Typed exceptions raised by forwarded-parse."""

from __future__ import annotations


class ForwardedParseError(ValueError):
    """Raised on malformed Forwarded header values.

    Carries a ``position`` offset (best-effort — 0 when not applicable)
    and a human-readable ``reason``.
    """

    def __init__(self, reason: str, position: int = 0) -> None:
        super().__init__(f"{reason} (at position {position})")
        self.reason = reason
        self.position = position

    def __repr__(self) -> str:
        return f"ForwardedParseError(reason={self.reason!r}, position={int(self.position)})"
