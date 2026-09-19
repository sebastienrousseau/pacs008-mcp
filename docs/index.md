# pacs008-mcp

Model Context Protocol server exposing the
[pacs008](https://github.com/sebastienrousseau/pacs008) ISO 20022
FI-to-FI Customer Credit Transfer library as agent tools.

```{toctree}
:maxdepth: 2
:caption: Contents

readme
api
benchmarks
adr/index
roadmap
changelog
```

## What it is

Sixteen tools, three resources and one prompt over the `pacs008` library,
served to any MCP client (Claude Desktop, IDEs, agents) over stdio,
streamable HTTP or SSE. Every tool is a thin, typed wrapper over the same
library the CLI and REST API use, so all interfaces behave identically.
A tool never raises: on bad input it returns an `{"error": ...}` payload
the agent can read.

## Why

An agent building an interbank payment needs to discover the exact
message type, learn the fields, validate the records against the JSON
Schema and against the rail's usage guidelines, and only then generate
XML. This server exposes each of those steps as a separate, closed-world
tool with JSON Schema enums for the closed sets, so the client can
constrain inputs before the call and the model cannot guess a message
type or skip a validation gate.

## Install

```sh
pip install pacs008-mcp            # Python 3.10+
pip install 'pacs008-mcp[online]'  # adds httpx for verify_bic_online
```

## Transports

One command line, three transports:

| Command | Transport | Endpoint |
| :--- | :--- | :--- |
| `pacs008-mcp` | stdio | the client spawns the process |
| `pacs008-mcp --transport streamable-http` | Streamable HTTP (2026-07-28 and 2025-11-25) | `http://127.0.0.1:8000/mcp` |
| `pacs008-mcp --transport sse` | HTTP+SSE (2024-11-05) | `http://127.0.0.1:8000/sse` and `/messages/` |

`--host` and `--port` change the bind address. The HTTP transports carry
no authentication of their own: bind loopback, or put the server behind a
gateway you trust. See [ADR 0001](adr/0001-three-transports-one-command-line.md).

## Tools

| Tool | Does |
| :--- | :--- |
| `list_message_types` | List every supported pacs message type and its human name |
| `list_schemes` | List every registered scheme / usage-guideline profile |
| `get_scheme` | Return the rule attributes of one scheme profile |
| `get_required_fields` | List the required input fields for a message type |
| `get_input_schema` | Return the full input JSON Schema for a message type |
| `validate_records` | Validate flat records against the message type's JSON Schema |
| `validate_scheme` | Validate records against a scheme's usage-guideline rules |
| `generate_message` | Generate XSD-validated pacs XML from in-memory records |
| `validate_xml` | Validate a raw XML string against the bundled XSD |
| `parse_message` | Parse and classify an inbound ISO 20022 message |
| `convert_mt103` | Convert a legacy SWIFT MT103 into pacs.008 records |
| `classify_address` | Classify a postal address as structured, hybrid or unstructured |
| `validate_address` | Validate one postal address against an address policy |
| `repair_address` | Upgrade legacy unstructured address lines toward structured form |
| `validate_addresses` | Batch-validate every party address across payment rows |
| `verify_bic_online` | Check a BIC structurally, with an optional directory lookup |

Resources: `pacs008://message-types`, `pacs008://schemes` and the
templated `pacs008://scheme/{scheme_id}`. Prompt: `build_pacs008_message`,
which teaches the recommended tool order.

## Quick links

- [Source on GitHub](https://github.com/sebastienrousseau/pacs008-mcp)
- [PyPI release](https://pypi.org/project/pacs008-mcp/)
- [Core library: pacs008](https://github.com/sebastienrousseau/pacs008)
- [MT103 loader: pacs008-loader-mt103](https://github.com/sebastienrousseau/pacs008-loader-mt103)
- [MCP specification](https://modelcontextprotocol.io)

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
