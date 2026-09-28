"""Entry point so ``python -m forwarded_parse`` works.

Delegates to :func:`forwarded_parse.cli.main`.
"""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
