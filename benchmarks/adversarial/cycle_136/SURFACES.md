# Surface enumeration — cycle_136 / adv / 01

> Repository: `forwarded-parse` v0.1.0 (commit `d9417ba`)
> Branch: `wt/cycle136-adv-01`
> Audit author: @repo-adversary (T1 VULN_AUDIT)
> Date: 2026-09-28

## 1. Module surface — `import forwarded_parse`

Public symbols declared in `src/forwarded_parse/__init__.py:__all__`:

| Symbol | Kind | Defined at | Notes |
|---|---|---|---|
| `Forwarded` | frozen slotted dataclass | `__init__.py:75` | fields: `elements: tuple[ForwardedElement, ...]`; supports `len()`, `iter()`, `bool()`, `to_dict()` |
| `ForwardedElement` | frozen slotted dataclass | `__init__.py:43` | fields: `for_: tuple[str, ...]`, `by: str \| None`, `host: str \| None`, `proto: str \| None`; `to_dict()` |
| `ForwardedParseError` | exception (subclass of `ValueError`) | `_errors.py:6` | fields: `reason: str`, `position: int`; `__repr__` overridden |
| `parse(value: str) -> Forwarded` | function | `__init__.py:109` | raises `ForwardedParseError` on malformed/non-string input |
| `format(parsed: Forwarded) -> str` | function | `__init__.py:131` | raises `TypeError` on non-`Forwarded` argument |
| `normalize(parsed: Forwarded) -> Forwarded` | function | `__init__.py:154` | raises `TypeError` on non-`Forwarded` argument |

`__version__ = "0.1.0"`. No internal symbols are exported. The internal
helpers (`_parser.parse_forwarded`, `_parser.unfold_obs_fold`,
`_parser.iter_pairs`, `_parser._split_top_level`, `_parser._is_token_char`,
`_parser._parse_value`, `_parser._parse_pair`, `_parser._parse_element`,
`_serializer.format_forwarded`, `_serializer.format_element`,
`_serializer._format_for`) live in `_*`-prefixed modules and are not in
`__all__`; they are importable but conventional Python privacy markers
discourage downstream use.

## 2. CLI surface

Defined in `src/forwarded_parse/cli.py` and re-exported by
`src/forwarded_parse/__main__.py`. Console-script entry point in
`pyproject.toml`:

```
[project.scripts]
forwarded-parse = "forwarded_parse.__main__:main"
```

Behaviour (from `cli.py:main`):

| Invocation | Behaviour | Exit |
|---|---|---|
| `forwarded-parse` (no args) | Reads Forwarded header value from stdin, prints canonical round-tripped form to stdout | 0 success / 1 parse error / 2 usage error |
| `forwarded-parse --json` | Reads stdin, prints JSON `{"elements": [...]}` to stdout | same |
| Stdin is a TTY | Prints `forwarded-parse: reading from stdin (Ctrl-D to end)...` to stderr, then reads | same |
| Empty stdin or whitespace-only stdin | Prints `"{}"` (with `--json`) or `"\n"` (without `--json`) | 0 |
| Stdin contains malformed Forwarded | Prints `forwarded-parse: parse error: <reason>\n` to stderr | 1 |
| argparse error | argparse-default | 1 (argparse), counted as usage error |

The CLI **only** supports `--json`. It does **not** support the flags
listed in the parent kanban card body (`--self-test`, `--parse VALUE`,
`--format VALUE`, `--normalize VALUE`, `--version`) — those flags are
not declared in `_build_parser()`. This is documented as Finding I-2 in
`VULN_AUDIT.md` (task-body inaccuracy, not a vulnerability).

The CLI does not invoke any shell, does not `os.system`, does not call
`subprocess`. All argv processing is via `argparse.parse_args(argv)`,
which only stores values into Python attributes. No `eval()`,
`exec()`, or `pickle.load`/`yaml.load` calls exist anywhere in
`src/forwarded_parse/`.

## 3. Files & call graph

```
src/forwarded_parse/
├── __init__.py        (187 LOC) — public API, dataclasses
├── __main__.py        ( 10 LOC) — `python -m` shim
├── _errors.py         ( 19 LOC) — ForwardedParseError exception
├── _parser.py         (378 LOC) — state-machine parser, obs-fold, splitter
├── _serializer.py     ( 89 LOC) — canonical format, quote/escape logic
├── cli.py             ( 90 LOC) — argparse, stdin/stdout, JSON output
└── py.typed           (marker)
```

External symbols referenced from stdlib only: `dataclasses`, `typing`,
`argparse`, `json`, `sys`, `__future__`. `dependencies = []` in
`pyproject.toml`.

## 4. Benchmarks surface

```
benchmarks/
├── BENCHMARK.md       (results table)
├── BENCHMARK.json     (machine-readable equivalent)
└── run_benchmark.py   (50-iter x 10-workload reproducer vs naive `str.split(',')`)
```

`run_benchmark.py` reads a single Forwarded header value from `argv[1]`
and times `parse + format`. No network, no shell exec, no arbitrary code
loading.

## 5. Tests surface

13 test modules, 176 collected `def test_*` functions (331 collected
test cases when parametrization is counted — matches the build card
claim). No `fuzz_*` test modules exist; SPEC.md AC10 refers to a
`fuzz_parse.py` file that does not exist in the repo (the QA worker
substituted pytest-corpus coverage; see Finding I-5).

## 6. Out-of-scope surfaces (intentional)

The library does NOT expose, parse, or process:

- HTTP request/response lines
- `X-Forwarded-For` (separate grammar; explicitly out of scope per
  SPEC.md §5.2)
- Cookies, Set-Cookie, or any other header
- DNS, IP geolocation, or rate-limit logic
- Network I/O of any kind
- Persistence / filesystem writes
- `os.environ` reads

All inputs arrive as Python `str` (or whatever the caller passes);
all outputs are Python objects (`Forwarded`, `ForwardedElement`, `str`)
or JSON strings written to stdout.