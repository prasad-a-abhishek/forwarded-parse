"""Command-line interface for forwarded-parse.

Two modes:

* default — read a Forwarded header value from stdin, print the canonical
  round-tripped form to stdout.
* ``--json`` — read from stdin and emit a JSON object ``{"elements": [...]}``.

Examples:

    $ echo 'for=_secret123, for=192.0.2.43;proto=https' \\
        | python -m forwarded_parse --json
    {"elements": [{"for": ["_secret123"], "by": null, "host": null, "proto": null}, {"for": ["192.0.2.43"], "by": null, "host": null, "proto": https}]}

Exit codes:

* 0 — success (including empty input → empty output).
* 1 — parse error (ForwardedParseError).
* 2 — usage error (missing stdin or argparse failure).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import ForwardedParseError, format, parse


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forwarded-parse",
        description=(
            "Parse an RFC 7239 Forwarded header value. Reads the header "
            "value from stdin (use single quotes to preserve ; and ,). "
            "Without --json, prints the canonical round-tripped form. "
            "With --json, prints a JSON object with an elements array."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of the canonical header string",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if sys.stdin.isatty():
        sys.stderr.write(
            "forwarded-parse: reading from stdin (Ctrl-D to end)...\n"
        )
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        if args.json:
            sys.stdout.write(json.dumps({"elements": []}, indent=2) + "\n")
        else:
            sys.stdout.write("\n")
        return 0

    # Accept a multi-line input (the whole field value is on one logical
    # line, but the caller may have line-wrapped it). Strip trailing
    # newlines so an obs-fold in the middle survives (we only join
    # CRLF + SP/HTAB inside the parser, not bare newlines).
    value = raw.rstrip("\n")
    if value.endswith("\r"):
        value = value[:-1]

    try:
        parsed = parse(value)
    except ForwardedParseError as exc:
        sys.stderr.write(f"forwarded-parse: parse error: {exc.reason}\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(parsed.to_dict(), indent=2) + "\n")
    else:
        out = format(parsed)
        if out:
            sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
