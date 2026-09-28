"""
Shared harness utilities for the forwarded-parse adversary workstream (cycle_136).

Cycle_133-135 established the "subprocess-harness + JSON results envelope" pattern,
which avoids requiring Atheris/libFuzzer and produces artifacts readable by the
TRIAGE + FUZZING_REPORT phases.

Conventions
-----------
- Each harness script writes its results to ``fuzz/<surface>/results.json``
  beside ``benchmarks/adversarial/cycle_136/``.
- Exit codes: 0 = clean (no crash, no oracle mismatch); 1 = crash (uncaught
  exception or oracle mismatch); 2 = harness self-error (bad config).
- The seed-PRNG is fixed so a re-run is bit-identical (helpful for oracle diffs).
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


# Fixed seed for deterministic oracle diffs across re-runs.
DEFAULT_SEED = 0xC0FFEE_1360_0001

# Anchor to the benchmark root so subprocess invocations from CI land the
# results.json file next to the harness_*.py source — matches the V4 deliverable.
ADVERSARIAL_ROOT = Path(__file__).resolve().parent
FUZZ_ROOT = ADVERSARIAL_ROOT / "fuzz"

# Anchor to the src/ tree of this worktree so subprocess harnesses don't need a
# venv install — they run via ``PYTHONPATH=src python3 -m forwarded_parse``.
SRC_ROOT = ADVERSARIAL_ROOT.parent.parent.parent / "src"


def adversarial_root() -> Path:
    return ADVERSARIAL_ROOT


def fuzz_root() -> Path:
    return FUZZ_ROOT


def ensure_fuzz_dir(surface: str) -> Path:
    out = FUZZ_ROOT / surface
    out.mkdir(parents=True, exist_ok=True)
    return out


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_results(surface: str, payload: dict[str, Any]) -> Path:
    out = ensure_fuzz_dir(surface) / "results.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return out


def run_harness(
    *,
    surface: str,
    iters: int,
    fn: Callable[[int, random.Random], None],
    seed: int = DEFAULT_SEED,
) -> int:
    """Drive ``fn(iters, rng)`` and write results.json. Returns exit code.

    ``fn`` should raise on any unexpected (uncaught) exception or oracle
    mismatch — ``run_harness`` will translate that into exit code 1 and write
    a crash record into the results.
    """
    started = utc_now_iso()
    t0 = time.perf_counter()
    rng = random.Random(seed)
    crashes: list[dict[str, Any]] = []
    oracle_mismatches: list[dict[str, Any]] = []
    clean_iters = 0
    try:
        for i in range(iters):
            try:
                fn(i, rng)
                clean_iters += 1
            except AssertionError as e:
                oracle_mismatches.append(
                    {"iter": i, "kind": "AssertionError", "msg": str(e)}
                )
                # Continue rather than abort — count every mismatch.
            except Exception as e:  # noqa: BLE001 — uncaught means harness crash
                crashes.append(
                    {
                        "iter": i,
                        "kind": type(e).__name__,
                        "msg": str(e)[:500],
                    }
                )
    except Exception as e:  # noqa: BLE001 — harness self-error
        # Bad: the harness itself blew up. Write a degraded result and exit 2.
        elapsed = time.perf_counter() - t0
        write_results(
            surface,
            {
                "surface": surface,
                "iters_requested": iters,
                "iters_clean": clean_iters,
                "crashes": crashes,
                "oracle_mismatches": oracle_mismatches,
                "harness_self_error": {
                    "kind": type(e).__name__,
                    "msg": str(e)[:500],
                },
                "seed": seed,
                "started_utc": started,
                "ended_utc": utc_now_iso(),
                "elapsed_seconds": round(elapsed, 6),
                "exit_code": 2,
                "verdict": "HARNESS_SELF_ERROR",
            },
        )
        print(f"HARNESS_SELF_ERROR ({type(e).__name__}): {e}", file=sys.stderr)
        return 2

    elapsed = time.perf_counter() - t0
    exit_code = 0 if (not crashes and not oracle_mismatches) else 1
    verdict = "CLEAN" if exit_code == 0 else "DIRTY"
    write_results(
        surface,
        {
            "surface": surface,
            "iters_requested": iters,
            "iters_clean": clean_iters,
            "crashes": crashes,
            "oracle_mismatches": oracle_mismatches,
            "harness_self_error": None,
            "seed": seed,
            "started_utc": started,
            "ended_utc": utc_now_iso(),
            "elapsed_seconds": round(elapsed, 6),
            "exit_code": exit_code,
            "verdict": verdict,
            "python": sys.version.split()[0],
            "argv": sys.argv[1:],
        },
    )
    return exit_code


def random_str(rng: random.Random, *, max_len: int = 4096) -> str:
    """Generate a random str using a byte stream decoded as utf-8 with errors='replace'.

    This mirrors what an HTTP server typically sees after recv + decode: any
    byte is possible, including NUL, CR, LF, and arbitrary multi-byte sequences
    that decode to replacement chars.
    """
    n = rng.randint(0, max_len)
    raw = bytes(rng.randint(0, 255) for _ in range(n))
    return raw.decode("utf-8", errors="replace")


def adversarial_pool(rng: random.Random) -> str:
    """Pick a known-bad seed string from a small corpus.

    Mixes "interesting" Forwarded-header values: empty, OWS-only, CRLF obs-fold,
    multibyte, NUL, obf tokens, IPv6 literals (require quoting), quoted-string
    escapes, multi-element chains, missing ``=``, etc. Mirrors the seed pool
    style from cycle_135 (vary-parse).
    """
    seeds = [
        "",
        " ",
        "\t",
        "\r\n",
        "\r\n \r\n",
        "\x00",
        "\x00\x00\x00",
        # Canonical RFC 7239 §7 examples
        "for=192.0.2.43",
        "for=192.0.2.43, for=198.51.100.17",
        "for=192.0.2.43, for=198.51.100.17;by=203.0.113.60;proto=https;host=example.com",
        # Obfuscated tokens (RFC 7239 §6.3) — must round-trip verbatim
        "for=_SEVK1",
        "for=_ProXe",
        "for=_secret123",
        "for=_abc, for=_def",
        # Quoted-string values (RFC 7230 §3.2.6)
        'for="192.0.2.43"',
        'by="203.0.113.60"',
        'host="example.com"',
        'proto="https"',
        'for="Hello\\"World"',
        'for="with\\\\backslash"',
        'for="Hello\\World"',  # bare backslash inside quoted-string (preserve verbatim)
        # IPv6 literal — must be quoted
        'for="[2001:db8::1]"',
        'by="[fe80::1]"',
        # Multi-element chain
        "for=_a, for=_b, for=_c, by=_d",
        "for=1.1.1.1;for=2.2.2.2;for=3.3.3.3",
        # OWS variations
        "  for=192.0.2.43  ",
        "\tfor=192.0.2.43\t",
        "  for=192.0.2.43  ,  for=198.51.100.17  ",
        # Mixed-case key (parser normalises to lowercase)
        "For=192.0.2.43",
        "FOR=_secret",
        "By=203.0.113.60",
        # Obs-fold (RFC 7230 §3.2.4)
        "for=192.0.2.43\r\n , for=198.51.100.17",
        "for=_a\r\n\t;by=_b",
        # Unknown / extension keys (silently dropped per RFC 7239 §4)
        "foo=bar",
        "for=_a;custom=value",
        "for=_a;proto-version=2",
        # Missing or malformed pairs
        "for=",
        "for",
        "=value",
        "for=192.0.2.43;",
        "for=192.0.2.43,,",
        # Unterminated quoted-string
        'for="unterminated',
        'for="with"quote',
        # Token char violations
        "for=has space",
        "for=has,comma",
        "for=has;semi",
        "for=has(paren)",
        "for=has[bracket]",
        # Multibyte / unicode
        "for=中文.example.com",
        "for=example.中文",
        # Very long obfuscated token
        "for=" + "_" * 256,
        # Empty / whitespace-only
        "",
        " ",
        "\t\t",
        ",\t,",
        # NUL byte
        "for=\x00",
        "for=_a\x00_b",
        # Mixed obf + named
        "for=_secret, for=192.0.2.43;by=203.0.113.60",
        # Multiple for= chains with mixed obf and named
        "for=_a;for=b;for=_c;for=d",
    ]
    return rng.choice(seeds)


def random_obf_token(rng: random.Random) -> str:
    """Generate a random obfuscated token (RFC 7239 §6.3 leading-underscore form).

    The body chars come from tchar + a small pool of extension chars that
    proxies commonly embed inside obf tokens (alphanumeric + a few separators).
    """
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
    n = rng.randint(1, 64)
    body = "".join(rng.choice(alphabet) for _ in range(n))
    return "_" + body


def random_quoted_value(rng: random.Random) -> str:
    """Generate a random RFC 7230 §3.2.6 quoted-string body (without surrounding quotes).

    The body is **always well-formed** when wrapped in ``"…"`` and fed to
    the parser. Specifically:

    * No unescaped ``"`` (every ``"`` is preceded by ``\\``).
    * No raw ``\\n`` / ``\\r`` / ``\\t`` / NUL.
    * A bare ``\\`` is never followed by ``"`` — that would make the
      ``"`` look like the closing quote to the RFC scanner. (We track
      state so an escape pair is atomic from the parser's view.)

    May include backslash-escapes for ``"`` (``\\"`` → ``"``) and ``\\``
    (``\\\\`` → ``\\``), plus arbitrary non-control chars. Bare backslashes
    (no escape target) are emitted verbatim to exercise the parser's
    "preserve verbatim on bare backslash" branch — but only when followed
    by a non-quote, non-backslash safe char (RFC 7230 allows
    ``\\<other>`` preserved verbatim, but the parser scans ``\\X``
    greedily, so ``\\"`` and ``\\\\`` are escape pairs and ``\\X`` for any
    other X is bare-backslash + literal X).
    """
    # Plain chars: alnum + safe punctuation + spaces. NO ``"`` here — that
    # would terminate the quoted-string. NO raw control chars.
    alphabet = (
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789 -._~!@#$%^&*()[]{}:;<>,?/"
    )
    n = rng.randint(1, 64)
    body_chars: list[str] = []
    # State: True iff the previous char emitted was a lone ``\\`` that the
    # parser will treat as a bare-backslash (followed by a non-escape
    # target). In that state the NEXT char must not be ``"`` (it would be
    # consumed as the escape target by the parser, NOT preserved).
    last_was_bare_backslash = False
    for _ in range(n):
        # Compute available choices given state.
        if last_was_bare_backslash:
            # Cannot emit ``"`` (would be consumed as escape target).
            choices = ["safe", "escape_backslash"]
            weights = [0.85, 0.15]
        else:
            choices = ["safe", "escape_quote", "escape_backslash", "bare_backslash"]
            weights = [0.7, 0.1, 0.1, 0.1]
        r = rng.random()
        cum = 0.0
        pick = "safe"
        for c, w in zip(choices, weights):
            cum += w
            if r < cum:
                pick = c
                break
        if pick == "safe":
            body_chars.append(rng.choice(alphabet))
            last_was_bare_backslash = False
        elif pick == "escape_quote":
            body_chars.append('\\"')  # → parser resolves to ``"``
            last_was_bare_backslash = False
        elif pick == "escape_backslash":
            body_chars.append("\\\\")  # → parser resolves to ``\``
            last_was_bare_backslash = False
        elif pick == "bare_backslash":
            body_chars.append("\\")  # bare ``\`` — parser preserves verbatim
            last_was_bare_backslash = True
    return "".join(body_chars)
