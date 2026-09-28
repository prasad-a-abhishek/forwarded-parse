"""AC1 / import-smoke tests for forwarded-parse."""

from __future__ import annotations

import importlib
import importlib.resources
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_import_top_level_api() -> None:
    """AC1 — every public name is importable from the top-level package."""
    from forwarded_parse import (  # noqa: F401
        Forwarded,
        ForwardedElement,
        ForwardedParseError,
        format,
        normalize,
        parse,
    )


def test_version_string_present() -> None:
    """Package version is exposed as ``__version__``."""
    import forwarded_parse

    assert hasattr(forwarded_parse, "__version__")
    assert isinstance(forwarded_parse.__version__, str)
    assert forwarded_parse.__version__ == "0.1.0"


def test_py_typed_marker_present() -> None:
    """The package ships ``py.typed`` for PEP 561 compliance."""
    import forwarded_parse

    # importlib.resources.files is the canonical PEP 561 way to check.
    pkg_root = importlib.resources.files("forwarded_parse")
    assert (pkg_root / "py.typed").is_file()


def test_reimport_is_idempotent() -> None:
    """Importing twice does not double-register the module."""
    import forwarded_parse as fp

    fp2 = importlib.import_module("forwarded_parse")
    assert fp is fp2


def test_no_third_party_dependencies() -> None:
    """Importing forwarded_parse in an isolated subprocess loads no third-party deps.

    Run in a fresh subprocess so we don't conflate pytest's own imports
    with the package's import footprint. We allow stdlib modules (incl.
    PEP 660 editable-install finders registered globally in this env)
    and only fail on known third-party HTTP/parsing libraries.
    """
    import subprocess
    import sys

    forbidden = (
        "werkzeug",
        "requests",
        "urllib3",
        "flask",
        "django",
        "starlette",
        "fastapi",
        "aiohttp",
        "httpx",
        "beautifulsoup",
        "lxml",
        "pyforwarded",
        "http_header",
    )
    code = (
        "import sys\n"
        "import forwarded_parse\n"
        "loaded = sorted([m for m in sys.modules if any(m == n or m.startswith(n + '.') for n in ("
        + ", ".join(repr(n) for n in forbidden)
        + "))])\n"
        "print('FORBIDDEN:', loaded)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
        cwd=str(REPO_ROOT),
    )
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert "FORBIDDEN: []" in out.stdout, out.stdout


@pytest.mark.parametrize(
    "name",
    ["parse", "format", "normalize", "Forwarded", "ForwardedElement", "ForwardedParseError"],
)
def test_all_public_names_resolve(name: str) -> None:
    """Every name in ``__all__`` is accessible."""
    import forwarded_parse

    assert name in forwarded_parse.__all__
    assert getattr(forwarded_parse, name) is not None
