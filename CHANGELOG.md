# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.0.1]: https://github.com/sebastienrousseau/pacs008-mcp/releases/tag/v0.0.1
