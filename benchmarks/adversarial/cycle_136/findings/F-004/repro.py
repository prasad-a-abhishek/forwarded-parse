#!/usr/bin/env python3
"""F-004: Minimal reproducer for CLI empty-stdout contract violation.

The CLI contract (per cli.py:54-65) is: exit 0 + non-empty input -> non-empty
stdout. But for inputs that parse to elements with no recognised keys, format()
returns '' (see F-001), and the CLI's `if out:` guard (line 84) suppresses
writing — leaving exit 0 + empty stdout.

This is NOT an independent library bug — it is the CLI's expected behaviour
on a 'round-trip-to-empty' input. The fix is F-001 (parser drops all-unknown
elements); once that's fixed, the CLI's `if out:` guard correctly fires only
for genuinely-empty input (which the caller knows they passed empty).
"""
import sys, subprocess
sys.path.insert(0, "src")

# Smallest trigger — same as F-001
INPUT = "foo=bar"

res = subprocess.run(
    [sys.executable, "-m", "forwarded_parse"],
    input=INPUT, capture_output=True, text=True,
    env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
)
print(f"INPUT:        {INPUT!r}")
print(f"exit code:    {res.returncode}")
print(f"stdout:       {res.stdout!r}")
print(f"stderr:       {res.stderr!r}")
print()

assert res.returncode == 0, "should exit 0 (parse succeeds)"
assert res.stdout != "", "BUG: exit 0 with non-empty input but empty stdout"
print("BUG CONFIRMED: CLI exits 0 but writes no output for input that has only unknown forward-pair names.")