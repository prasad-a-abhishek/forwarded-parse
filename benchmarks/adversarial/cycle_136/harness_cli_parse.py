#!/usr/bin/env python3
"""
harness_cli_parse.py — fuzz the CLI subprocess surface.

V3 contract (cycle_136/adv/02, surface 4 — CLI entrypoint):

    forwarded-parse (a.k.a. ``python3 -m forwarded_parse``) reads a header
    value from stdin and emits either the canonical round-tripped form
    (default) or a JSON object (with ``--json``).

    NB: the task body mentioned ``--parse <val>`` / ``--format <val>`` /
    ``--normalize <val>`` flags but the actual CLI is stdin-only with a
    ``--json`` toggle (see ``src/forwarded_parse/cli.py``). This harness
    exercises the real surface — stdin + optional ``--json``.

    Every iteration picks a random-or-seed input, spawns the CLI as a
    subprocess, and asserts:
      * exit 0 on parseable input (canonical form or JSON on stdout)
      * exit 1 on malformed input (parse error message on stderr)
      * exit 0 with empty output on whitespace-only / empty input
      * no uncaught exception (returncode 2 means usage error — also a
        finding; ``--help`` returns 0 and is not part of fuzzing)

Inputs exercised: same adversarial pool + every 11th iteration injects a
1MiB-scale payload to exercise large-input robustness; NUL bytes filtered
out (cannot reach argv / env; we only use stdin so NUL IS allowed, but
some shells strip it).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    SRC_ROOT,
    adversarial_pool,
    random_str,
    run_harness,
)


# Locate the python interpreter that has forwarded-parse importable via
# PYTHONPATH=src. Falling back to sys.executable.
_CLI_CMD = [sys.executable, "-m", "forwarded_parse"]


def _run_cli(value: str, *, use_json: bool) -> tuple[int, str, str]:
    """Invoke the CLI with ``value`` on stdin; return (returncode, stdout, stderr)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = list(_CLI_CMD)
    if use_json:
        cmd.append("--json")
    proc = subprocess.run(
        cmd,
        input=value,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _drive(i: int, rng) -> None:
    # Every 11th iter: 1 MiB random bytes (exercises large-input path).
    if i % 11 == 0:
        n = 1_048_576 + rng.randint(0, 4096)
        raw = bytes(rng.randint(0, 255) for _ in range(n))
        s = raw.decode("utf-8", errors="replace")
    elif i % 5 == 0:
        s = adversarial_pool(rng)
    else:
        s = random_str(rng)

    use_json = (i % 2 == 0)
    rc, out, err = _run_cli(s, use_json=use_json)

    # Acceptable return codes:
    #   0 = success or empty input
    #   1 = parse error (ForwardedParseError)
    # Anything else (2 = usage error, negative = signal) is a finding.
    if rc not in (0, 1):
        raise AssertionError(
            f"unexpected CLI exit {rc} for input len={len(s)} json={use_json}: "
            f"stderr={err[:200]!r}"
        )

    # On exit 0 with empty/whitespace-only input, stdout should be empty
    # (or "{}"/"{"elements":[],"}" for --json).
    stripped = s.strip()
    if rc == 0 and not stripped:
        if use_json:
            # Expect a JSON object with empty elements array.
            import json as _json
            try:
                obj = _json.loads(out)
            except Exception as e:
                raise AssertionError(
                    f"--json did not produce valid JSON for empty input: {out!r} ({e})"
                )
            if obj.get("elements") != []:
                raise AssertionError(
                    f"--json empty input produced non-empty elements: {out!r}"
                )
        else:
            if out.strip():
                raise AssertionError(
                    f"empty input produced non-empty stdout: {out!r}"
                )
        return

    # On exit 1, stderr should contain 'parse error' (CLI contract).
    if rc == 1:
        if "parse error" not in err.lower():
            raise AssertionError(
                f"exit 1 but stderr missing 'parse error': {err!r}"
            )
        return

    # On exit 0 with non-empty input: stdout must be parseable (canonical
    # form or JSON).
    if not out.strip():
        raise AssertionError(
            f"exit 0 with non-empty input but empty stdout: input={s[:200]!r}"
        )
    if use_json:
        import json as _json
        try:
            obj = _json.loads(out)
        except Exception as e:
            raise AssertionError(
                f"--json stdout not valid JSON: {out!r} ({e})"
            )
        if "elements" not in obj or not isinstance(obj["elements"], list):
            raise AssertionError(
                f"--json stdout missing 'elements' array: {out!r}"
            )
    else:
        # Canonical form must not contain raw CR/LF.
        if "\r" in out or "\n" in out:
            # CR/LF in stdout means the CLI failed to strip a trailing newline.
            # The CLI adds a single trailing \n via stdout.write(out + "\n").
            # We allow exactly ONE trailing \n.
            if out.count("\n") > 1 or "\r" in out:
                raise AssertionError(
                    f"CLI stdout contains unexpected CR/LF: {out!r}"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_cli_parse",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
