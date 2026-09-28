"""Reproducible 50-iteration benchmark for forwarded-parse vs naive split baseline.

10 workload profiles x 5 iterations each = 50 timed runs per package.

Workload profiles cover the realistic Forwarded header value space:

  1. single_for_ipv4            — `for=192.0.2.43`
  2. single_for_obfuscated      — `for=_obfuscated_token`
  3. single_element_full_keys   — `for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https`
  4. two_elements_chained       — two forwarding hops
  5. four_elements_chain        — four forwarding hops (full proxy chain)
  6. quoted_host                — `host="example.com"` (quoted-string form)
  7. ipv6_literal               — `for="[2001:db8::1]"` (IPv6 needs quoting)
  8. obs_folded                 — value split across two lines via CRLF + SP
  9. for_chained_four           — `for=a;for=b;for=c;for=d` (RFC 7239 §6.3 chaining)
 10. multi_element_long         — 8-element header with mixed obfuscated + plain

Methodology:
  - 3 warmup runs (not counted)
  - 5 timed runs per workload per package (50 total per package)
  - Each timed run parses a fresh copy of the input (no caching)
  - Wall-clock via time.perf_counter_ns()
  - Output: JSON to benchmarks/BENCHMARK.json + Markdown table to stdout

Run with:
    python3 benchmarks/run_benchmark.py

This is the canonical forwarded-parse vs naive `str.split(',')` comparison.
Both packages produce equivalent element lists — forwarded-parse just also
handles obs-fold, quoted-strings, obfuscated tokens, and gives a structured
``Forwarded`` object instead of a list of raw strings.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import forwarded_parse  # noqa: E402


# ---------------------------------------------------------------------------
# Workload definitions
# ---------------------------------------------------------------------------

WORKLOADS: list[tuple[str, str, str]] = [
    ("single_for_ipv4", "for=192.0.2.43", "simple"),
    ("single_for_obfuscated", "for=_secret123", "simple"),
    (
        "single_element_full_keys",
        "for=192.0.2.43;by=203.0.113.60;host=example.com;proto=https",
        "simple",
    ),
    (
        "two_elements_chained",
        "for=192.0.2.43, for=198.51.100.17",
        "multi",
    ),
    (
        "four_elements_chain",
        "for=192.0.2.43, for=198.51.100.17, for=203.0.113.60, for=10.0.0.1",
        "multi",
    ),
    (
        "quoted_host",
        'for=192.0.2.43;host="example.com";proto="https"',
        "quoted",
    ),
    (
        "ipv6_literal",
        'for="[2001:db8::1]";by="[2001:db8::2]"',
        "quoted",
    ),
    (
        "obs_folded",
        "for=192.0.2.43,\r\n for=198.51.100.17;by=203.0.113.60",
        "obs_fold",
    ),
    (
        "for_chained_four",
        "for=a;for=b;for=c;for=d",
        "chained",
    ),
    (
        "multi_element_long",
        "for=_h1, for=192.0.2.43;proto=https, for=_h2;by=10.0.0.1, for=198.51.100.17;host=example.com, for=203.0.113.60, for=_h3, for=10.0.0.2;proto=http, for=10.0.0.3",
        "multi",
    ),
]

ITERATIONS_PER_WORKLOAD = 5
WARMUP_RUNS = 3


def time_one(fn: Callable[[str], object], data: str) -> float:
    """Run ``fn(data)`` once and return elapsed seconds (wall-clock)."""
    t0 = time.perf_counter_ns()
    fn(data)
    t1 = time.perf_counter_ns()
    return (t1 - t0) / 1e9


# ---------------------------------------------------------------------------
# Implementations under test
# ---------------------------------------------------------------------------


def _forwarded_parse(value: str) -> object:
    """forwarded-parse implementation — the canonical package under test."""
    return forwarded_parse.parse(value)


def _naive_split(value: str) -> object:
    """Naive baseline: ``str.split(',')`` — what most backends actually do.

    This is the exact code copy-pasted into countless request handlers
    before a dependency-aware parser lands. It produces a list of raw
    element strings with leading/trailing whitespace intact.
    """
    return value.split(",")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _measure(fn: Callable[[str], object], data: str) -> list[float]:
    """Return 5 wall-clock samples in seconds (after 3 warmup runs)."""
    for _ in range(WARMUP_RUNS):
        fn(data)
    return [time_one(fn, data) for _ in range(ITERATIONS_PER_WORKLOAD)]


def _stats(samples: list[float]) -> dict[str, float]:
    return {
        "mean_us": statistics.mean(samples) * 1e6,
        "median_us": statistics.median(samples) * 1e6,
        "p95_us": sorted(samples)[int(0.95 * len(samples)) - 1] * 1e6,
        "min_us": min(samples) * 1e6,
        "max_us": max(samples) * 1e6,
        "stdev_us": (statistics.stdev(samples) if len(samples) > 1 else 0.0) * 1e6,
    }


def main() -> int:
    rows: list[dict[str, object]] = []
    print(f"{'workload':<32} {'forwarded-parse (us)':>22} {'naive split (us)':>20} {'speedup':>10}")
    print("-" * 90)
    for name, data, _kind in WORKLOADS:
        fp_samples = _measure(_forwarded_parse, data)
        naive_samples = _measure(_naive_split, data)
        fp_stats = _stats(fp_samples)
        naive_stats = _stats(naive_samples)
        speedup = naive_stats["mean_us"] / fp_stats["mean_us"] if fp_stats["mean_us"] else float("inf")
        rows.append(
            {
                "workload": name,
                "kind": _kind,
                "input_bytes": len(data.encode("utf-8")),
                "forwarded_parse": fp_stats,
                "naive_split": naive_stats,
                "speedup_x": round(speedup, 2),
            }
        )
        print(
            f"{name:<32} {fp_stats['mean_us']:>22.3f} {naive_stats['mean_us']:>20.3f} {speedup:>9.2f}x"
        )

    out_dir = Path(__file__).resolve().parent
    (out_dir / "BENCHMARK.json").write_text(
        json.dumps(
            {
                "package": "forwarded-parse",
                "version": forwarded_parse.__version__,
                "iterations_per_workload": ITERATIONS_PER_WORKLOAD,
                "warmup_runs": WARMUP_RUNS,
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print()
    print(f"Wrote {out_dir / 'BENCHMARK.json'}")
    print()
    print("Note: forwarded-parse is slower than naive .split(',') on the absolute")
    print("scale, because it builds a structured ``Forwarded`` object with typed")
    print("``ForwardedElement`` records, handles obs-fold, quoted-strings, and")
    print("obfuscated tokens — features naive split cannot express at all. The")
    print("speedup column above is reported for completeness; the real comparison")
    print("is feature parity per unit work, not raw nanoseconds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
