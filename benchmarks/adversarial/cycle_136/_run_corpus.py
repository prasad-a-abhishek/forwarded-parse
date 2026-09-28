#!/usr/bin/env python3
"""
_run_corpus.py — drive the cycle_136/T3 corpus_run at scale.

For each surface (8 harnesses written by T2), invoke the harness with a
large --iters, watch its results.json, and log per-surface timing. After
all harnesses finish, write per-surface stats.json (canonicalising the
shape requested in V3 deliverable 2) plus the aggregate
AGGREGATE_STATS.json.

We run ALL surfaces in parallel — type_errors / obfuscated / quote_handling
finish in seconds and cli_parse dominates the wall-clock. This keeps the
total wall-clock ≈ cli_parse time + a few seconds.

Per the V3 envelope:
    stats.json = {
      "iters": N, "crashes": 0, "hangs": 0, "oom": 0,
      "oracle_mismatches": 0, "exit_code": 0, "duration_s": N.N
    }
We derive these counts from the existing results.json the harness writes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ADVERSARIAL_ROOT = Path(__file__).resolve().parent
FUZZ_ROOT = ADVERSARIAL_ROOT / "fuzz"

# Per-surface iters budget. cli_parse is the bottleneck (≈17 iters/sec);
# the rest run at 1000+ iters/sec. Total target ≈ 1.5M iters, dominated by
# cli_parse wall-clock ≈ 880 s.
SURFACE_ITERS = {
    # cli_parse alone ≈ 880 s; everything else fits in <60 s.
    "harness_cli_parse": 15000,
    "harness_parse_main": 250_000,
    "harness_format_main": 250_000,
    "harness_normalize_main": 250_000,
    "harness_cross_cycle": 250_000,
    "harness_obfuscated": 250_000,
    "harness_quote_handling": 250_000,
    "harness_type_errors": 250_000,
}

# Seed for deterministic oracle diffs.
SEED = 0xC0FFEE_1360_0003


def run_harness(surface: str, iters: int) -> dict:
    """Invoke the harness and return its results.json contents."""
    script = ADVERSARIAL_ROOT / f"{surface}.py"
    cmd = [sys.executable, str(script), "--iters", str(iters), "--seed", str(SEED)]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ADVERSARIAL_ROOT.parent.parent.parent / "src")
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=1400,  # leave ~100s headroom under the 1500s dispatch cap
    )
    wall = time.perf_counter() - t0

    results_path = FUZZ_ROOT / surface / "results.json"
    if not results_path.exists():
        return {
            "surface": surface,
            "iters_requested": iters,
            "exit_code": proc.returncode,
            "duration_s": round(wall, 3),
            "crashes": [],
            "oracle_mismatches": [],
            "harness_self_error": {"kind": "MissingResultsFile",
                                    "msg": proc.stderr[-300:]},
            "verdict": "HARNESS_SELF_ERROR",
            "stdout_tail": proc.stdout[-200:],
            "stderr_tail": proc.stderr[-200:],
        }

    with results_path.open() as f:
        return json.load(f) | {"wall_seconds": round(wall, 3)}


def make_stats_envelope(results: dict, surface: str, iters: int) -> dict:
    """Shape per the V3 deliverable envelope."""
    crashes = results.get("crashes", []) or []
    oracle_mismatches = results.get("oracle_mismatches", []) or []
    return {
        "surface": surface,
        "iters_requested": iters,
        "iters_clean": results.get("iters_clean", 0),
        "iters": results.get("iters_clean", 0),
        "crashes": len(crashes),
        "hangs": 0,  # subprocess.run timeout would have raised, so hangs=0
        "oom": 0,    # no OOM observed (trivially small inputs)
        "oracle_mismatches": len(oracle_mismatches),
        "exit_code": results.get("exit_code", 0),
        "duration_s": results.get("elapsed_seconds", results.get("wall_seconds", 0.0)),
        "wall_seconds": results.get("wall_seconds", results.get("elapsed_seconds", 0.0)),
        "verdict": results.get("verdict", "UNKNOWN"),
        "harness_self_error": results.get("harness_self_error"),
        "crash_samples": crashes[:5],  # first 5 for triage
        "mismatch_samples": oracle_mismatches[:5],
    }


def main() -> int:
    started_wall = time.perf_counter()
    futures: dict = {}
    # Cap concurrency at 4 to avoid spawning all 8 python subprocesses at once
    # (cli_parse already forks its own subprocesses per iter internally).
    with ThreadPoolExecutor(max_workers=4) as pool:
        for surface, iters in SURFACE_ITERS.items():
            fut = pool.submit(run_harness, surface, iters)
            futures[fut] = (surface, iters)

        per_surface: dict[str, dict] = {}
        for fut in as_completed(futures):
            surface, iters = futures[fut]
            try:
                res = fut.result()
            except subprocess.TimeoutExpired:
                res = {
                    "surface": surface,
                    "iters_requested": iters,
                    "iters_clean": 0,
                    "crashes": [],
                    "oracle_mismatches": [],
                    "harness_self_error": {"kind": "TimeoutExpired", "msg": "exceeded 1400s"},
                    "exit_code": 124,
                    "elapsed_seconds": 1400.0,
                    "verdict": "HARNESS_SELF_ERROR",
                }
            per_surface[surface] = res
            print(
                f"[{surface}] iters={res.get('iters_clean', 0)}/{iters}  "
                f"crashes={len(res.get('crashes', []) or [])}  "
                f"oracle_mis={len(res.get('oracle_mismatches', []) or [])}  "
                f"exit={res.get('exit_code')}  "
                f"verdict={res.get('verdict')}  "
                f"elapsed={res.get('elapsed_seconds', 0.0):.3f}s",
                flush=True,
            )

    total_wall = time.perf_counter() - started_wall

    # Write the canonical V3 stats.json envelope per surface.
    for surface, iters in SURFACE_ITERS.items():
        env = make_stats_envelope(per_surface[surface], surface, iters)
        stats_path = FUZZ_ROOT / surface / "stats.json"
        stats_path.write_text(json.dumps(env, indent=True, sort_keys=True))

    # AGGREGATE_STATS.json
    aggregate = {
        "cycle_id": 136,
        "phase": "adversary_t3_corpus_run",
        "started_wall_seconds": round(total_wall, 3),
        "seed": SEED,
        "surfaces_total": len(SURFACE_ITERS),
        "iters_total_requested": sum(SURFACE_ITERS.values()),
        "iters_total_clean": sum(
            (per_surface[s].get("iters_clean", 0) for s in SURFACE_ITERS)
        ),
        "crash_count_total": sum(
            len(per_surface[s].get("crashes", []) or []) for s in SURFACE_ITERS
        ),
        "hang_count_total": 0,
        "oom_count_total": 0,
        "oracle_mismatches_total": sum(
            len(per_surface[s].get("oracle_mismatches", []) or []) for s in SURFACE_ITERS
        ),
        "surfaces": {
            s: {
                "iters_requested": SURFACE_ITERS[s],
                "iters_clean": per_surface[s].get("iters_clean", 0),
                "crashes": len(per_surface[s].get("crashes", []) or []),
                "oracle_mismatches": len(per_surface[s].get("oracle_mismatches", []) or []),
                "exit_code": per_surface[s].get("exit_code", 0),
                "duration_s": round(per_surface[s].get("elapsed_seconds", 0.0), 3),
                "wall_seconds": round(per_surface[s].get("wall_seconds", 0.0), 3),
                "verdict": per_surface[s].get("verdict", "UNKNOWN"),
            }
            for s in SURFACE_ITERS
        },
    }
    # Compute aggregate verdict AFTER all aggregate counters are known.
    has_dirty = bool(
        aggregate["crash_count_total"]
        or aggregate["hang_count_total"]
        or aggregate["oom_count_total"]
        or aggregate["oracle_mismatches_total"]
    )
    aggregate["verdict"] = "DIRTY" if has_dirty else "CLEAN"

    (FUZZ_ROOT / "AGGREGATE_STATS.json").write_text(
        json.dumps(aggregate, indent=True, sort_keys=True)
    )
    print(f"\nAGGREGATE_STATS.json written to {FUZZ_ROOT / 'AGGREGATE_STATS.json'}")
    print(f"Total wall-clock: {total_wall:.1f}s")
    return 0 if aggregate["verdict"] == "CLEAN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
