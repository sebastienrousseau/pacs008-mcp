#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What an agent waits for when it calls these tools.

This server is a thin shell over `pacs008`: it validates arguments, calls
the library, and marshals a result. The library is benchmarked in its own
repository, so re-measuring schema validation here would just measure
that again. What belongs here is the shape an *agent* experiences --
which tool costs what, and how that changes with the size of the batch it
was handed.

Three groups are measured.

* **The dispatch floor.** `list_message_types` touches no records at all,
  so whatever it costs is pure shell: argument handling and return
  marshalling. An agent pays this on every call, however small.

* **The payment pipeline across batch sizes.** `validate_records` and
  `generate_message` on the same growing input. Both scale linearly here
  and both do real work on every record -- unlike the `acmt` server,
  where most message types describe a single account and silently ignore
  the rest of the batch. The `output bytes` column is printed so that
  stays visible rather than assumed: growing bytes means the records are
  actually being rendered.

  The ratio between them is the useful number. Validation costs several
  times what generation does, so an agent that validates, fixes, and
  re-validates pays for the expensive half repeatedly.

* **The address tools.** `classify_address`, `validate_address`,
  `repair_address` and the bulk `validate_addresses` exist for the
  November 2026 structured-address cutover, which is a screening problem
  rather than a per-payment one: the question is "how many of our
  half-million stored addresses will fail", asked once over everything.

  They are pure string work with no schema behind them, and it shows.
  Address validation runs about two hundred times cheaper per item than
  record validation, which is the difference between screening a million
  addresses over a coffee and a job somebody has to schedule.

`verify_bic_online` is deliberately not measured. It makes a network
call, and timing somebody else's DNS and TLS handshake tells you nothing
about this code.

Run::

    python benches/bench_tool_dispatch.py
    python benches/bench_tool_dispatch.py --json
    python benches/bench_tool_dispatch.py --quick     # what CI runs

Nothing here asserts a threshold: wall-clock is not comparable between
machines, and a flaky performance gate teaches people to ignore red. CI
runs ``--quick`` so a benchmark that has stopped compiling against the
current API fails the build instead of rotting into a file that reads as
verified and is not.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pacs008_mcp.server as server  # noqa: E402

MESSAGE_TYPE = "pacs.008.001.08"

#: One complete, valid FI-to-FI customer credit transfer. Kept complete
#: on purpose: a record missing fields fails validation early and would
#: measure the rejection path rather than the working one.
_RECORD = {
    "msg_id": "MSG-0001",
    "creation_date_time": "2026-06-21T10:00:00",
    "nb_of_txs": "1",
    "settlement_method": "CLRG",
    "end_to_end_id": "E2E-0001",
    "interbank_settlement_amount": "1000.00",
    "interbank_settlement_currency": "EUR",
    "charge_bearer": "SLEV",
    "debtor_name": "Acme Ltd",
    "debtor_agent_bic": "DEUTDEFFXXX",
    "creditor_agent_bic": "NWBKGB2LXXX",
    "creditor_name": "Beta GmbH",
    "remittance_information": "Invoice 1",
}

#: A structured postal address in the CBPR+ sense.
_ADDRESS = {
    "street_name": "Rue de la Loi",
    "building_number": "170",
    "post_code": "1040",
    "town_name": "Brussels",
    "country": "BE",
}

#: The unstructured form `repair_address` is handed.
_LINES = ["Rue de la Loi 170", "1040 Brussels", "Belgium"]


def build(count: int) -> list[dict]:
    """``count`` distinct valid payment records."""
    return [
        dict(_RECORD, msg_id=f"MSG-{i:07d}", end_to_end_id=f"E2E-{i:07d}")
        for i in range(count)
    ]


def build_addresses(count: int) -> list[dict]:
    """``count`` distinct structured addresses."""
    return [dict(_ADDRESS, building_number=str(i)) for i in range(count)]


def _best(call, repeats: int) -> float:
    """Best-of timing after one untimed warm-up.

    The warm-up matters more than usual: the first `generate_message` in a
    process compiles the XSD, which costs two orders of magnitude more
    than every call after it. Timing that once and calling it the tool's
    cost would be wrong in both directions -- far too slow for a
    long-lived server, far too fast for a one-shot process.
    """
    call()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    return min(samples)


def _exponent(points: list[tuple[int, float]]) -> float | None:
    """Log-log slope: 1.0 linear, 2.0 quadratic."""
    if len(points) < 2:
        return None
    (n0, t0), (n1, t1) = points[0], points[-1]
    if n0 == n1 or t0 <= 0 or t1 <= 0:
        return None
    return math.log(t1 / t0) / math.log(n1 / n0)


def measure_pipeline(sizes: list[int], repeats: int) -> dict:
    """validate_records and generate_message on the same input."""
    rows, points = [], []
    for count in sizes:
        records = build(count)
        validate = _best(
            partial(server.validate_records, MESSAGE_TYPE, records), repeats
        )
        generate = _best(
            partial(server.generate_message, MESSAGE_TYPE, records), repeats
        )
        rendered = server.generate_message(MESSAGE_TYPE, records)
        points.append((count, validate))
        rows.append(
            {
                "records": count,
                "validate_ms": validate * 1e3,
                "validate_us_per_record": validate * 1e6 / count,
                "generate_ms": generate * 1e3,
                "validate_over_generate": (
                    validate / generate if generate else 0.0
                ),
                "output_bytes": len(str(rendered)),
            }
        )
    return {"rows": rows, "exponent": _exponent(points)}


def measure_addresses(sizes: list[int], repeats: int) -> dict:
    """The bulk screening path, which is what the cutover actually needs."""
    rows, points = [], []
    for count in sizes:
        addresses = build_addresses(count)
        seconds = _best(partial(server.validate_addresses, addresses), repeats)
        points.append((count, seconds))
        rows.append(
            {
                "addresses": count,
                "ms": seconds * 1e3,
                "us_per_address": seconds * 1e6 / count,
            }
        )
    return {"rows": rows, "exponent": _exponent(points)}


def run(quick: bool) -> dict:
    sizes = [1, 10] if quick else [1, 10, 100]
    address_sizes = [1, 100] if quick else [1, 100, 1_000, 10_000]
    repeats = 2 if quick else 5
    reps = 200 if quick else 2_000
    single = {
        "list_message_types": _best(server.list_message_types, reps) * 1e6,
        "get_required_fields": _best(
            partial(server.get_required_fields, MESSAGE_TYPE), reps // 4
        )
        * 1e6,
        "classify_address": _best(
            partial(server.classify_address, _ADDRESS), reps
        )
        * 1e6,
        "validate_address": _best(
            partial(server.validate_address, _ADDRESS), reps
        )
        * 1e6,
        "repair_address": _best(
            partial(server.repair_address, _LINES, "BE"), reps
        )
        * 1e6,
    }
    return {
        "message_type": MESSAGE_TYPE,
        "single_call_us": single,
        "pipeline": measure_pipeline(sizes, repeats),
        "addresses": measure_addresses(address_sizes, repeats),
    }


def render(results: dict) -> None:
    print("  Single-call tools -- what an agent pays per call:\n")
    for name, micros in results["single_call_us"].items():
        print(f"    {name:<22}{micros:>10.1f} us")
    print(
        "\n  list_message_types touches no records, so its cost is the "
        "dispatch floor: what\n  every call pays before doing any work. The "
        "address tools sit near it because they\n  are string work with no "
        "schema behind them."
    )

    pipeline = results["pipeline"]
    print(f"\n  Payment pipeline, {results['message_type']}:\n")
    print(
        f"    {'records':>8}{'validate ms':>14}{'us/record':>12}"
        f"{'generate ms':>14}{'v/g':>8}{'output bytes':>15}"
    )
    for row in pipeline["rows"]:
        print(
            f"    {row['records']:>8}{row['validate_ms']:>14.2f}"
            f"{row['validate_us_per_record']:>12.1f}"
            f"{row['generate_ms']:>14.2f}"
            f"{row['validate_over_generate']:>7.1f}x"
            f"{row['output_bytes']:>15,}"
        )
    rows = pipeline["rows"]
    if rows[-1]["output_bytes"] > rows[0]["output_bytes"]:
        print(
            "\n    Output grows with the batch: every record is rendered, "
            "not just the first."
        )
    exponent = pipeline["exponent"]
    if exponent is not None:
        print(
            f"    Validation growth exponent {exponent:.2f} "
            f"({'linear' if exponent <= 1.25 else 'superlinear'}). It costs "
            f"several times what generation\n    does, so an agent that "
            f"validates, fixes and re-validates pays the expensive half "
            f"twice."
        )

    addresses = results["addresses"]
    print("\n  Address screening -- the November 2026 cutover path:\n")
    print(f"    {'addresses':>10}{'ms':>12}{'us/address':>14}")
    for row in addresses["rows"]:
        print(
            f"    {row['addresses']:>10}{row['ms']:>12.2f}"
            f"{row['us_per_address']:>14.2f}"
        )
    per_address = addresses["rows"][-1]["us_per_address"]
    per_record = pipeline["rows"][-1]["validate_us_per_record"]
    if per_address:
        print(
            f"\n    About {per_record / per_address:.0f}x cheaper per item "
            f"than record validation. The cutover is a\n    screening "
            f"problem -- 'how many of our stored addresses will fail', "
            f"asked once over\n    everything -- and at this cost a million "
            f"addresses is seconds, not a scheduled job."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--quick", action="store_true", help="small sizes, as CI runs"
    )
    args = parser.parse_args()

    results = run(quick=args.quick)
    if args.json:
        json.dump(results, sys.stdout, indent=1)
        print()
    else:
        render(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
