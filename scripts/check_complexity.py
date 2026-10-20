#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Fail when a function or file exceeds the complexity limits.

Per function: cyclomatic complexity at most 10, Halstead difficulty at most
30, at most 60 lines. Per file: at most 500 lines. Cognitive complexity (at
most 15) is checked by ``complexipy`` against ``complexipy-snapshot.json``
in the same CI job.

``BASELINE`` lists the offenders that predate this gate, with the value
each had when it was recorded. An offender may shrink but never grow; a
new offender fails the build; and an entry that is back under its limit
fails too, so the baseline is deleted as it is paid down and only ever
gets shorter.

Run::

    python scripts/check_complexity.py              # the default paths
    python scripts/check_complexity.py some/dir     # anything else
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import h_visit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = ("pacs008_mcp", "scripts", "benches", "examples", "fuzz")
MAX_CYCLOMATIC = 10
MAX_HALSTEAD_DIFFICULTY = 30.0
MAX_FUNCTION_LINES = 60
MAX_FILE_LINES = 500

#: (path relative to the repository, item, metric) -> recorded value.
BASELINE: dict[tuple[str, str, str], float] = {
    ("pacs008_mcp/server.py", "<file>", "lines"): 1142,
    ("pacs008_mcp/server.py", "verify_bic_online", "lines"): 129,
}


def python_files(paths: list[str]) -> Iterator[Path]:
    """Every ``.py`` file under ``paths``, in a stable order."""
    for raw in paths:
        path = Path(raw)
        yield from sorted(path.rglob("*.py")) if path.is_dir() else [path]


def measure(path: Path) -> dict[tuple[str, str, str], float]:
    """Every value in ``path`` that exceeds its limit, keyed like BASELINE."""
    source = path.read_text(encoding="utf-8")
    name = _relative(path)
    found: dict[tuple[str, str, str], float] = {}
    lines = len(source.splitlines())
    if lines > MAX_FILE_LINES:
        found[(name, "<file>", "lines")] = lines
    for block in cc_visit(source):
        if block.complexity > MAX_CYCLOMATIC:
            found[(name, block.name, "cyclomatic")] = block.complexity
    for func, report in h_visit(source).functions:
        if report.difficulty > MAX_HALSTEAD_DIFFICULTY:
            found[(name, func, "halstead")] = round(report.difficulty, 1)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                found[(name, node.name, "lines")] = length
    return found


def _relative(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        return resolved.relative_to(ROOT).as_posix()
    return path.as_posix()


def compare(
    found: dict[tuple[str, str, str], float],
    baseline: dict[tuple[str, str, str], float],
    checked: set[str],
) -> list[str]:
    """Every regression, new offender and stale baseline entry."""
    problems = []
    for key, value in sorted(found.items()):
        path, item, metric = key
        allowed = baseline.get(key)
        if allowed is None:
            problems.append(
                f"{path} {item}: {metric} {value} is over the limit"
            )
        elif value > allowed:
            problems.append(
                f"{path} {item}: {metric} grew from {allowed} to {value}"
            )
    for key in sorted(set(baseline) - set(found)):
        if key[0] in checked:
            problems.append(
                f"{key[0]} {key[1]}: {key[2]} is within the limit now; "
                f"delete its BASELINE entry"
            )
    return problems


def main(argv: list[str]) -> int:
    """Measure the paths and compare them with the baseline."""
    paths = argv or [
        str(ROOT / p) for p in DEFAULT_PATHS if (ROOT / p).exists()
    ]
    files = list(python_files(paths))
    found: dict[tuple[str, str, str], float] = {}
    for path in files:
        found.update(measure(path))
    problems = compare(found, BASELINE, {_relative(f) for f in files})
    for problem in problems:
        print(f"ERROR: {problem}")
    if problems:
        return 1
    print(
        f"OK: within the complexity limits ({len(BASELINE)} baselined "
        f"offenders, none grown)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
