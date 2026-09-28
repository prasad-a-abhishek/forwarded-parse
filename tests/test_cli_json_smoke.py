"""AC8 — CLI smoke tests for ``python -m forwarded_parse``."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


PYTHON = sys.executable
REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(input_str: str, *args: str) -> subprocess.CompletedProcess:
    """Invoke ``python -m forwarded_parse`` with stdin input."""
    return subprocess.run(
        [PYTHON, "-m", "forwarded_parse", *args],
        input=input_str,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/usr/local/bin"},
        timeout=15,
    )


def test_cli_json_smoke() -> None:
    """AC8 — ``--json`` mode emits valid JSON with ``elements`` list."""
    proc = _run_cli("for=_secret123, for=192.0.2.43;proto=https", "--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "elements" in data
    assert isinstance(data["elements"], list)
    assert len(data["elements"]) == 2
    assert data["elements"][0]["for"] == ["_secret123"]
    assert data["elements"][1]["for"] == ["192.0.2.43"]
    assert data["elements"][1]["proto"] == "https"


def test_cli_canonical_smoke() -> None:
    """Default mode prints the canonical round-tripped form."""
    proc = _run_cli("for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;proto=https")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == (
        "for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;proto=https"
    )


def test_cli_empty_input_yields_empty_json() -> None:
    proc = _run_cli("", "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data == {"elements": []}


def test_cli_obs_fold_json() -> None:
    proc = _run_cli("for=192.0.2.43;\r\n by=203.0.113.60", "--json")
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert len(data["elements"]) == 1
    assert data["elements"][0]["by"] == "203.0.113.60"


def test_cli_parse_error_exits_nonzero() -> None:
    """Malformed input → exit 1 + stderr message."""
    proc = _run_cli('host="unterminated', "--json")
    assert proc.returncode == 1
    assert "parse error" in proc.stderr.lower() or "error" in proc.stderr.lower()


@pytest.mark.parametrize(
    "input_str,expected_substr",
    [
        ("for=192.0.2.43", "192.0.2.43"),
        ("for=_opaque", "_opaque"),
        ('for="[2001:db8::1]"', "2001:db8::1"),
        ("for=192.0.2.43;proto=https", "https"),
    ],
)
def test_cli_json_contains_expected_substring(
    input_str: str, expected_substr: str
) -> None:
    proc = _run_cli(input_str, "--json")
    assert proc.returncode == 0
    assert expected_substr in proc.stdout
