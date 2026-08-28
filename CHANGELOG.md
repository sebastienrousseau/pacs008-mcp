# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.9] - 2026-08-28

Swift deferred the CBPR+ structured-address start date; the descriptions a
model reads still named it as in force.

### Fixed

- The `address_policy` parameter description, the `classify_address`
  docstring and the workflow guidance all said the CBPR+ structured-address
  rule takes force on 14 November 2026. Swift deferred that on 27 August 2026
  and confirms replacement timing by December at the latest. These strings
  are what an assistant reads to decide what to tell a user, so a stale date
  here is repeated to whoever asked as though it were authoritative.
- The descriptions now say the deferral is Swift's and covers CBPR+; HVPS+,
  T2 RTGS, CHAPS, Lynx and Fedwire set their own timing and are unaffected.

### Unchanged

- No tool behaviour changes. Descriptions only.

## [0.0.8] - 2026-08-16

Release the work that accumulated on `main` after `v0.0.7` was tagged,
and take the `pacs008` release that makes the `cryptography` floor
resolvable.

### Fixed

- `pacs008` is now `>=0.0.9`. Both `0.0.7` and `0.0.8` of `pacs008` cap
  `cryptography<50.0.0`, so requiring the patched `cryptography 50.0.0`
  against them is not merely unsatisfied — it is unresolvable:

      ERROR: Cannot install cryptography>=50.0.0, pacs008==0.0.7 and
      pacs008==0.0.8 because these package versions have conflicting
      dependencies.

- `cryptography` is floored at `>=50.0.0`. It arrives transitively via
  `mcp` -> `pyjwt[crypto]` and nothing constrained it, so a resolver
  could pick a version in the range GHSA flags as high severity.

### Added

- Online BIC directory verification tool (#10).
- MCP prompts and resources for Trinity parity (#9).
- `tests/test_package_version.py`, tying `__version__` to
  `pyproject.toml` and the newest `CHANGELOG.md` heading. Its absence is
  why `0.0.7` shipped without a changelog entry and why the
  `cryptography` bump in #12 — whose commit message says `(v0.0.7)` —
  landed *after* the `v0.0.7` tag and was never published.

## [0.0.7] - 2026-07-30

Backfilled: this version was released and tagged, but no changelog
entry was written at the time.

### Changed

- Required `pacs008>=0.0.7` (was `>=0.0.5`) for the 0.0.7 validation
  bug fix.

## [0.0.6] - 2026-07-26

### Added

- **PEP 561 `py.typed` marker** (`pacs008_mcp/py.typed`), wired into the
  Poetry `include` list and verified present in the built wheel. The server
  is `mypy --strict` clean but previously shipped no marker, so downstream
  consumers received none of its annotations.
- **Regression test** (`tests/test_py_typed_marker.py`) that fails before a
  release ships if the marker is dropped from source or packaging.

### Changed

- Version `0.0.5` → `0.0.6`.

## [0.0.5] - 2026-07-18

### Changed

- chore(deps): require `pacs008>=0.0.7` (was `>=0.0.5`) to pick up the
  0.0.7 validation bug fix. No tool signatures or behaviour change in
  this server.

## [0.0.4] - 2026-07-12

### Added

- `convert_mt103` tool — convert a legacy SWIFT **MT103** (single customer
  credit transfer) into **pacs.008-ready flat records** that can be fed
  straight into `validate_records` / `generate_message`. This is the SWIFT
  MT-to-MX migration path (correspondent-banking MT103 coexistence with ISO
  20022 ends November 2025). The tool is a thin wrapper over the
  [`pacs008-loader-mt103`](https://github.com/sebastienrousseau/pacs008-loader-mt103)
  library's `parse_mt103`; it does no file I/O and returns
  `{"message_type": "pacs.008.001.08", "records": [...]}`, or an
  `{"error": ...}` payload on a missing-mandatory-field / malformed MT103.

### Changed

- The MCP server now exposes **15 tools** (was 14).
- Added a runtime dependency on `pacs008-loader-mt103` (`>=0.0.1`).

## [0.0.3] - 2026-07-12

### Security

- Require **pacs008 >= 0.0.5**, which relaxes the cryptography constraint to
  `<49.0.0` (patched `>=48.0.1`), clearing the inherited Dependabot advisory.

## [0.0.2] - 2026-07-12

### Added

- Four **November 2026 structured-address cliff** tools, each a thin wrapper
  over the `pacs008` library's `standards.address` module. From 14 November
  2026, fully unstructured postal addresses are rejected across SWIFT CBPR+,
  HVPS+, T2 RTGS, CHAPS, Fedwire and Lynx; these tools let agents get ahead of
  the deadline:
  - `classify_address` — classify a postal address as structured / hybrid /
    unstructured (wraps `PostalAddress.classify` and its `is_*` predicates)
  - `validate_address` — validate one address against an address policy,
    defaulting to the 14 November 2026 cliff rule (wraps
    `PostalAddress.validate`)
  - `repair_address` — country-aware upgrade of legacy unstructured address
    lines toward hybrid/structured form (wraps `from_unstructured`)
  - `validate_addresses` — batch-validate every party address across payment
    rows (wraps `validate_addresses`)
- `policy` value-constraint enum on the address tools, surfaced as JSON Schema
  `enum` metadata derived from the library's `AddressPolicy` enum
  (`unstructured_ok`, `hybrid_or_structured`, `structured_only`), defaulting to
  `hybrid_or_structured` — the cliff policy.

### Changed

- The MCP server now exposes **14 tools** (was 10).
- Bumped the minimum `pacs008` dependency to `>=0.0.4` — the first published
  PyPI release whose `standards.address` module backs the new tools.

## [0.0.1] - 2026-07-11

### Added

- Initial release of `pacs008-mcp`, a Model Context Protocol (MCP) server that
  exposes the [`pacs008`](https://github.com/sebastienrousseau/pacs008) ISO
  20022 FI-to-FI Customer Credit Transfer library as tools for AI agents and
  assistants.
- `pacs008-mcp` console script that runs the FastMCP server over stdio.
- Ten MCP tools, each a thin wrapper over the `pacs008` library so they behave
  identically to the CLI and REST API:
  - `list_message_types` — list the 20 supported pacs message types with names
  - `list_schemes` — list the registered scheme / usage-guideline profiles
  - `get_scheme` — inspect a scheme profile's rules
  - `get_required_fields` — required input fields for a message type
  - `get_input_schema` — full input JSON Schema for a message type
  - `validate_records` — validate flat records against a message type's schema
  - `validate_scheme` — validate records against a scheme's usage guidelines
  - `generate_message` — generate a validated pacs XML message
  - `validate_xml` — validate a raw XML string against the bundled XSD
  - `parse_message` — parse & classify an inbound ISO 20022 message
- Value-constraint enums on closed-set tool parameters (`message_type`,
  `scheme`), surfaced as JSON Schema `enum` metadata derived from the `pacs008`
  library's own constants and profile registry so accepted values never drift.
- MCP tool annotations (`readOnlyHint`/`idempotentHint`/…) and tool titles for
  richer client/Glama introspection.
- Graceful error handling: tools return an `{"error": ...}` payload on failure
  rather than raising.
- 100% statement + branch test coverage, enforced inline via
  `--cov-fail-under=100`.
- Python 3.10+ support; depends on `pacs008` (>=0.0.1) and `mcp` (>=1.2).
- Runnable example (`examples/mcp_tools.py`) invoking the tools in-process.
- `glama.json`, `server.json` (MCP Registry metadata), and a `Dockerfile` for
  directory listing, registry publication, and container deployment.

[0.0.6]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.6
[0.0.5]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.5
[0.0.4]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.4
[0.0.3]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.3
[0.0.2]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.2
[0.0.1]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.1
