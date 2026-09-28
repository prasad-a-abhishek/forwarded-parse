#!/usr/bin/env python3
"""
_seed_corpus_gen.py — generate diverse seed corpora for cycle_136/T3.

Each surface under benchmarks/adversarial/cycle_136/fuzz/<surface>/corpus/
gets its own directory of seed inputs that exercise the input distribution
described in the V1 plan of the T3 task body.

Surface layout:
  parse_main        : utf-8 text inputs (raw .txt files)
  format_main       : parseable text inputs (raw .txt files — input to parse()
                      whose output is then format()ed)
  normalize_main    : same as parse_main/format_main
  cli_parse         : stdin bytes (raw .txt files, may include NUL)
  cli_format        : (alias; same shape as cli_parse)
  cli_normalize     : (alias; same shape as cli_parse)
  type_errors       : JSON files containing the type-error candidate
  obfuscated        : raw obf tokens (the harness prepends 'for='); saved as
                      full `for=_obf` strings for clarity
  quote_handling    : full quoted-string assignments like `for="..."` and
                      `host="..."`
  cross_cycle       : same shape as parse_main

The task body spec says dirs are `<surface>/`, but T2 produced `harness_<surface>/`.
We honour T2's on-disk layout (renaming would orphan the results.json files T2 wrote).
The `surface` JSON tag and the directory name are aligned via the manifest in
CORPUS_RUN.md.

Each input file contains either:
  - UTF-8 text bytes (possibly with raw control chars or unprintable bytes
    for the cli_parse surfaces), one input per file
  - JSON (for type_errors surface)

All inputs are written deterministically via a fixed seed (DEFAULT_SEED) so
re-running produces identical corpora.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Re-use the well-vetted generators from T2.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    FUZZ_ROOT,
    adversarial_pool,
    random_obf_token,
    random_quoted_value,
    random_str,
)

# --- Per-surface corpus builders ------------------------------------------


def build_parse_like_corpus(rng: random.Random, n: int) -> list[str]:
    """Build a corpus of strings that exercise the parse() input distribution.

    Mixes random utf-8 strings with the known-bad adversarial pool. Random
    strings may be empty (rng.randint(0, max_len)).
    """
    inputs: list[str] = []
    for _ in range(n):
        if rng.random() < 0.3:
            inputs.append(adversarial_pool(rng))
        else:
            inputs.append(random_str(rng, max_len=4096))
    return inputs


def build_cli_corpus(rng: random.Random, n: int) -> list[str]:
    """Build a corpus of stdin payloads for the CLI subprocess surface.

    Includes a few 1MiB-scale entries (every 11th in the harness; here we
    pick a fixed handful to exercise the large-input path).
    """
    inputs: list[str] = []
    for i in range(n):
        if i % 5 == 0:
            # 1MiB random bytes, decoded with errors='replace'
            n_bytes = 1_048_576 + rng.randint(0, 4096)
            raw = bytes(rng.randint(0, 255) for _ in range(n_bytes))
            inputs.append(raw.decode("utf-8", errors="replace"))
        elif i % 3 == 0:
            inputs.append(adversarial_pool(rng))
        else:
            inputs.append(random_str(rng, max_len=4096))
    return inputs


def build_type_errors_corpus(rng: random.Random, n: int) -> list[dict]:
    """Build a corpus of non-str candidates for parse() / format() / normalize().

    Each entry is a JSON object describing what the candidate was — the
    harness re-creates the Python value at fuzz-time via the type tags.
    """
    type_choices = [
        {"tag": "none"},
        {"tag": "bool_true"},
        {"tag": "bool_false"},
        {"tag": "int"},
        {"tag": "float"},
        {"tag": "empty_str"},
        {"tag": "non_empty_str"},  # for format()/normalize(): this IS a str,
                                    # but not a Forwarded instance.
        {"tag": "empty_list"},
        {"tag": "empty_tuple"},
        {"tag": "empty_dict"},
        {"tag": "empty_set"},
        {"tag": "empty_bytes"},
        {"tag": "empty_bytearray"},
        {"tag": "empty_memoryview"},
        {"tag": "non_empty_list"},
        {"tag": "non_empty_tuple"},
        {"tag": "non_empty_dict"},
        {"tag": "non_empty_bytes"},
        {"tag": "non_empty_bytearray"},
        {"tag": "range"},
        {"tag": "iterator"},
        {"tag": "object"},
        {"tag": "type_instance_int"},
        {"tag": "type_instance_str"},
    ]
    candidates: list[dict] = []
    for _ in range(n):
        candidates.append(rng.choice(type_choices))
    return candidates


def build_obfuscated_corpus(rng: random.Random, n: int) -> list[str]:
    """Build a corpus of `for=<obf>` strings.

    Most entries are bare `for=_obf`; some are multi-element chains with
    obf tokens in `for=`, `by=`, `host=`, and `proto=` slots.
    """
    inputs: list[str] = []
    for i in range(n):
        obf = random_obf_token(rng)
        roll = rng.random()
        if roll < 0.7:
            inputs.append(f"for={obf}")
        elif roll < 0.85:
            obf2 = random_obf_token(rng)
            inputs.append(f"for={obf}, for=192.0.2.43;by={obf2}")
        else:
            slot = rng.choice(("by", "host", "proto"))
            inputs.append(f"for=192.0.2.43;{slot}={obf}")
    return inputs


def build_quote_handling_corpus(rng: random.Random, n: int) -> list[str]:
    """Build a corpus of quoted-string assignments for various parameter keys.

    Empty `""` values are included too (per RFC 7230 §3.2.6 they ARE accepted).
    """
    inputs: list[str] = []
    param_keys = ("for", "by", "host", "proto")
    for _ in range(n):
        key = rng.choice(param_keys)
        roll = rng.random()
        if roll < 0.85:
            body = random_quoted_value(rng)
            inputs.append(f'{key}="{body}"')
        elif roll < 0.95:
            # Empty quoted-string (valid per RFC 7230 §3.2.6)
            inputs.append(f'{key}=""')
        else:
            # Unterminated — guard case. The parser must reject these.
            body = random_quoted_value(rng)
            inputs.append(f'{key}="{body}')
    return inputs


# --- Driver --------------------------------------------------------------

# Surfaces covered by T2's harnesses. Each maps to the harness directory name
# AND the input generator to use.
SURFACE_PLAN: list[tuple[str, callable]] = [
    ("harness_parse_main", build_parse_like_corpus),
    ("harness_format_main", build_parse_like_corpus),
    ("harness_normalize_main", build_parse_like_corpus),
    ("harness_cli_parse", build_cli_corpus),
    # The T2 task body listed CLI surfaces for format/normalize too, but T2
    # only built harness_cli_parse (since the CLI reads stdin and does parse
    # internally). For T3 we add equivalent corpora under their natural
    # surface names. Saved under cli_parse/ and aliased via the manifest.
    ("harness_cli_format", build_cli_corpus),
    ("harness_cli_normalize", build_cli_corpus),
    ("harness_type_errors", build_type_errors_corpus),
    ("harness_obfuscated", build_obfuscated_corpus),
    ("harness_quote_handling", build_quote_handling_corpus),
    ("harness_cross_cycle", build_parse_like_corpus),
]

# Number of seed inputs per surface. ≥10 required by V3 deliverable; we use
# 32 to comfortably exceed the floor and give the human reviewer a clear
# picture of the input distribution.
SEEDS_PER_SURFACE = 32


def write_text_corpus(dirpath: Path, inputs: list[str]) -> int:
    """Write text inputs as one file per input.

    Files are named 00.txt, 01.txt, ... ; byte content is utf-8.
    NUL bytes are preserved (libFuzzer convention; cli_parse harness
    reads stdin so NUL is OK).
    """
    dirpath.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(inputs):
        fp = dirpath / f"{i:02d}.txt"
        # errors='replace' keeps everything safely encodable as utf-8
        # while preserving arbitrary bytes (including NUL, raw CR/LF).
        fp.write_bytes(s.encode("utf-8", errors="replace"))
    return len(inputs)


def write_json_corpus(dirpath: Path, entries: list[dict]) -> int:
    """Write type-error candidates as one JSON file per entry."""
    dirpath.mkdir(parents=True, exist_ok=True)
    for i, entry in enumerate(entries):
        fp = dirpath / f"{i:02d}.json"
        fp.write_text(json.dumps(entry, sort_keys=True))
    return len(entries)


def main() -> int:
    rng = random.Random(DEFAULT_SEED)
    manifest: list[dict] = []

    for surface, builder in SURFACE_PLAN:
        corpus_dir = FUZZ_ROOT / surface / "corpus"
        if builder is build_type_errors_corpus:
            entries = builder(rng, SEEDS_PER_SURFACE)
            n = write_json_corpus(corpus_dir, entries)
            kind = "json"
        else:
            inputs = builder(rng, SEEDS_PER_SURFACE)
            n = write_text_corpus(corpus_dir, inputs)
            kind = "text"
        manifest.append(
            {"surface": surface, "corpus_kind": kind, "seed_count": n}
        )
        print(f"wrote {n:3d} seeds to {corpus_dir.relative_to(FUZZ_ROOT.parent.parent)}")

    # Persist a manifest of seed corpora at fuzz/_corpus_manifest.json so the
    # T3 report and the T4/T5 reviewer can see at a glance which surfaces
    # exist and how many seeds each contains.
    manifest_path = FUZZ_ROOT / "_corpus_manifest.json"
    manifest_path.write_text(json.dumps(
        {"seed_per_surface": SEEDS_PER_SURFACE, "surfaces": manifest},
        indent=True,
        sort_keys=True,
    ))
    print(f"manifest written to {manifest_path.relative_to(FUZZ_ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
