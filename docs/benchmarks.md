# Benchmarks

This server is a thin shell over `pacs008`. The library is benchmarked in
its own repository, so re-measuring schema validation here would only
measure that again. What belongs here is the shape an **agent**
experiences: which tool costs what, and how that changes with batch size.

## Running it

```sh
python benches/bench_tool_dispatch.py           # full run
python benches/bench_tool_dispatch.py --quick   # what CI runs
python benches/bench_tool_dispatch.py --json    # machine-readable
```

CI runs `--quick` — not as a timing gate, but so a benchmark that has
stopped compiling against the current API fails the build rather than
rotting into a file that reads as verified and is not.

## Single-call tools

| tool | cost |
| :--- | ---: |
| `list_message_types` | ~4.5 µs |
| `get_required_fields` | ~171 µs |
| `classify_address` | ~0.5 µs |
| `validate_address` | ~0.6 µs |
| `repair_address` | ~5.8 µs |

`list_message_types` touches no records, so its cost is the **dispatch
floor** — what every call pays before doing any work. The address tools
sit near it because they are string work with no schema behind them.

## The payment pipeline

| records | validate ms | µs/record | generate ms | v/g | output bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2.09 | 2,090 | 0.87 | 2.4× | 1,067 |
| 10 | 19.10 | 1,911 | 2.71 | 7.0× | 6,899 |
| 100 | 187.13 | 1,871 | 24.94 | 7.5× | 65,219 |

Two things to read here.

**Output grows with the batch.** Every record is rendered, not just the
first. That is worth stating because the sibling `acmt` server behaves
differently — most `acmt` message types describe a single account and
silently ignore the rest of the batch. Here they do not.

**Validation costs roughly seven times generation**, and the growth
exponent is 0.98 — linear. An agent that validates, fixes, and
re-validates pays for the expensive half twice; batching the fixes before
re-validating is worth doing.

## Address screening: the November 2026 path

| addresses | ms | µs/address |
| ---: | ---: | ---: |
| 1 | 0.01 | 12.21 |
| 100 | 1.08 | 10.83 |
| 1,000 | 11.97 | 11.97 |
| 10,000 | 120.76 | 12.08 |

Flat, and about **155× cheaper per item than record validation**.

That matters because the structured-address cutover is a *screening*
problem, not a per-payment one: the question is "how many of our stored
addresses will fail", asked once across everything. At ~12 µs each, a
million addresses is about twelve seconds — something you run while
waiting, not a job somebody has to schedule.

## Not measured

`verify_bic_online` makes a network call. Timing somebody else's DNS and
TLS handshake would say nothing about this code.
