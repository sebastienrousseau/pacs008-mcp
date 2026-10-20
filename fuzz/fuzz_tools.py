# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Coverage-guided fuzzing of the text-taking tools with Atheris.

Each input becomes one string, handed to ``validate_xml``,
``parse_message`` and ``convert_mt103``. A tool must answer with a dict --
a result or an ``{"error": ...}`` payload -- and never raise; anything
else is a crash libFuzzer reports and minimises. The fixed and
property-based cases of the same contract are in
``tests/test_untrusted_text.py``.

Run (Linux x86_64, Python 3.12-3.14)::

    pip install --require-hashes -r requirements/fuzz.txt
    pip install --no-deps -e .
    python fuzz/fuzz_tools.py -max_total_time=60 -max_len=16384 \
        work-corpus/ fuzz/corpus/
"""

import contextlib
import io
import sys

import atheris

with atheris.instrument_imports():
    import pacs008_mcp.server as srv

MSG_TYPE = "pacs.008.001.08"


def test_one_input(data: bytes) -> None:
    """Feed one fuzzed string to every text-taking tool."""
    # Decoded directly, so libFuzzer's byte mutations of the seed corpus
    # (fuzz/corpus) stay XML- and MT103-shaped.
    text = data.decode("utf-8", errors="replace")
    # The library prints parse errors to stdout; keep the fuzzer log clean.
    with contextlib.redirect_stdout(io.StringIO()):
        results = (
            srv.validate_xml(MSG_TYPE, text),
            srv.parse_message(text),
            srv.convert_mt103(text),
        )
    for result in results:
        if not isinstance(result, dict):
            raise TypeError(f"tool returned {type(result).__name__}")


def main() -> None:
    """Hand the target to libFuzzer."""
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
