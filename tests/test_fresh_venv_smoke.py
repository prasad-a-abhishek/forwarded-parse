"""AC9 — fresh-venv install smoke (subset of the full CI script).

The canonical AC9 test lives in ``scripts/ci_fresh_venv.sh`` (run by the
CI / ship pipeline). These tests reproduce the key assertions in-process
so the suite catches regressions without requiring a separate shell run.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fresh_venv_install_and_import(tmp_path: Path) -> None:
    """Spawn a clean venv, ``pip install -e .``, then import the package."""
    venv = tmp_path / "fv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    pip = venv / "bin" / "pip"
    py = venv / "bin" / "python"
    subprocess.run(
        [str(pip), "install", "-e", str(REPO_ROOT), "-q"],
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        [str(py), "-c", "from forwarded_parse import parse; print(parse('for=192.0.2.43').elements[0].for_)"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert "192.0.2.43" in out.stdout


def test_fresh_venv_no_third_party_imports(tmp_path: Path) -> None:
    """A clean venv install + import must not pull in werkzeug, requests, etc."""
    venv = tmp_path / "fv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    pip = venv / "bin" / "pip"
    py = venv / "bin" / "python"
    subprocess.run(
        [str(pip), "install", "-e", str(REPO_ROOT), "-q"],
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        [
            str(py),
            "-c",
            "import sys, forwarded_parse\n"
            "third = [m for m in sys.modules if m.startswith(('werkzeug', 'requests', 'urllib3', 'flask', 'django'))]\n"
            "print('THIRD_PARTY:', third)",
        ],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert "THIRD_PARTY: []" in out.stdout


def test_fresh_venv_pip_dependency_count(tmp_path: Path) -> None:
    """``pip show`` lists zero third-party deps."""
    venv = tmp_path / "fv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    pip = venv / "bin" / "pip"
    py = venv / "bin" / "python"
    subprocess.run(
        [str(pip), "install", "-e", str(REPO_ROOT), "-q"],
        check=True,
        capture_output=True,
    )
    out = subprocess.run(
        [str(pip), "show", "forwarded-parse"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0
    # ``Requires:`` line MUST be absent or empty (no runtime deps).
    requires_lines = [
        line for line in out.stdout.splitlines() if line.startswith("Requires:")
    ]
    assert requires_lines, out.stdout
    assert requires_lines[0].strip() == "Requires:", out.stdout


def test_fresh_venv_spec_example(tmp_path: Path) -> None:
    """The exact example from SPEC §6 / V3 step 4 must work in a fresh venv."""
    venv = tmp_path / "fv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    pip = venv / "bin" / "pip"
    py = venv / "bin" / "python"
    subprocess.run(
        [str(pip), "install", "-e", str(REPO_ROOT), "-q"],
        check=True,
        capture_output=True,
    )
    snippet = (
        "from forwarded_parse import parse; "
        "r = parse('for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;host=example.com;proto=https'); "
        "print(len(r.elements), [list(e.for_) for e in r.elements])"
    )
    out = subprocess.run(
        [str(py), "-c", snippet],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, (out.stdout, out.stderr)
    assert out.stdout.strip() == "2 [['192.0.2.43'], ['198.51.100.17']]"


def test_fresh_venv_install_is_quiet_and_fast(tmp_path: Path) -> None:
    """A fresh install completes within a reasonable time (no network for deps)."""
    venv = tmp_path / "fv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=True,
        capture_output=True,
    )
    pip = venv / "bin" / "pip"
    subprocess.run(
        [str(pip), "install", "-e", str(REPO_ROOT), "-q"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    # No third-party wheels should be downloaded — only setuptools/wheel
    # for the build backend (already cached).
    list_out = subprocess.run(
        [str(pip), "list"],
        capture_output=True,
        text=True,
    )
    assert list_out.returncode == 0
    listed = [
        line.split()[0]
        for line in list_out.stdout.splitlines()[2:]
        if line.strip()
    ]
    # Only setuptools / wheel / pip / forwarded-parse should be present.
    allowed = {"forwarded-parse", "pip", "setuptools", "wheel"}
    extra = set(listed) - allowed
    assert not extra, f"unexpected packages installed: {extra}"
