<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# pacs008-mcp Architecture

A map of the codebase for new contributors and maintainers. The goal is
that anyone can navigate, extend, and reason about pacs008-mcp without
prior context.

## The pipeline

```
MCP client (Claude Desktop, IDE, agent)
        |  stdio, streamable HTTP or SSE (JSON-RPC)
        v
pacs008_mcp/server.py        (MCP server: tools, resources, prompt)
        |  thin typed wrappers
        v
pacs008                      (constants, profiles, validation,
        |                     standards.address, xml.generate_xml,
        |                     xml.parser, xml.validate_via_xsd)
pacs008_loader_mt103         (parse_mt103, for convert_mt103)
        v
ISO 20022 pacs XML / structured data
```

Tools are deliberately thin: every one is a small adapter that
delegates to the
[`pacs008`](https://github.com/sebastienrousseau/pacs008) library (or,
for `convert_mt103`, to
[`pacs008-loader-mt103`](https://github.com/sebastienrousseau/pacs008-loader-mt103))
and returns a JSON-serialisable result. The same library backs its CLI
and REST API, so every interface behaves identically.

## Module map

| Area | Module | Responsibility |
| :--- | :--- | :--- |
| **Server** | `pacs008_mcp/server.py` | The MCP server, all tool / resource / prompt registrations |
| **Entry point** | `pacs008_mcp.server:main` (console script: `pacs008-mcp`) | Launches the server over stdio, or over streamable HTTP / SSE with `--transport` (`_cli.py` + `_transports.py`, ADR 0001) |
| **SDK shim** | `pacs008_mcp/_mcp_compat.py` | Builds the server on either supported major of the `mcp` SDK (2.x `MCPServer`, 1.x `FastMCP`) |
| **Version** | `pacs008_mcp/__init__.py` | Single source of truth (`__version__`) |
| **Tests** | `tests/test_mcp_server.py`, `tests/test_transports.py`, `tests/test_mcp_sdk_compat.py`, `tests/test_package_version.py`, `tests/test_py_typed_marker.py`, `tests/test_suite_conformance.py` | In-process regressions, the command line, the SDK shim, the version and packaging guards, and the shared suite conformance gate |
| **Examples** | `examples/mcp_tools.py` | Runnable in-process walkthrough of the tools |
| **Benchmarks** | `benches/bench_tool_dispatch.py` | What an agent waits for per tool; `docs/benchmarks.md` explains the result |
| **Release helpers** | `scripts/verify_versions.py`, `scripts/check_suite_consistency.py` | Assert every restatement of the version agrees; compare the published suite against PyPI |

## Tools, resources, prompts

The current MCP surface:

- **Tools** - sixteen. Discovery: `list_message_types`, `list_schemes`,
  `get_scheme`, `get_required_fields`, `get_input_schema`. Validation
  and generation: `validate_records`, `validate_scheme`,
  `generate_message`, `validate_xml`, `parse_message`. Migration:
  `convert_mt103`. Addresses: `classify_address`, `validate_address`,
  `repair_address`, `validate_addresses`. Online: `verify_bic_online`
  (the one tool that makes an outbound call; needs the `online` extra).
- **Resources** - `pacs008://message-types` (the catalogue as JSON),
  `pacs008://schemes` (the scheme profile catalogue) and
  `pacs008://scheme/{scheme_id}` (one profile's rules).
- **Prompts** - `build_pacs008_message(...)` (guided instruction template
  for building and validating one pacs.008 message).

## Key design decisions

- **Delegation, not duplication.** Every tool is a thin wrapper over
  `pacs008`. If you want a new tool, port the matching helper from
  `pacs008` rather than re-implementing it here.
- **Errors as data.** Tools never raise. A `ValueError` is turned into
  an `{"error": ...}` payload so the agent can reason about failure
  without parsing tracebacks.
- **Closed sets are enums.** `message_type`, `scheme` and
  `address_policy` are surfaced as JSON Schema `enum` metadata derived
  from the library's own constants, so accepted values never drift.
- **Loopback by default.** stdio needs no socket. The HTTP transports
  bind `127.0.0.1` unless told otherwise and add no authentication of
  their own; a routable deployment sits behind a gateway (ADR 0001).
- **One outbound call, and it is named.** `verify_bic_online` is the
  only tool that reaches the network, and only when a directory URL is
  given (argument or `PACS008_BIC_DIRECTORY_URL`); the structural BIC
  check runs offline.
- **Coverage enforced at 100%** line+branch; only defensive guards are
  `# pragma: no cover`.

## Extension points

- **Add a tool:** add a function under `@server.tool(...)` in
  `pacs008_mcp/server.py`; pair it with tests in
  `tests/test_mcp_server.py`.
- **Add a resource:** `@server.resource("pacs008://...")` decorator.
- **Add a prompt:** `@server.prompt()` decorator.
- **Match a new `pacs008` feature:** when a new helper lands upstream,
  port it as a tool here in the same release window.

## Where to look first

- Runnable example: [`examples/`](examples/)
- Decisions: [`docs/adr/`](docs/adr/index.md)
- Roadmap: [`ROADMAP.md`](ROADMAP.md)
- Release process: [`RELEASING.md`](RELEASING.md)
- Parent library: [`pacs008`](https://github.com/sebastienrousseau/pacs008)
