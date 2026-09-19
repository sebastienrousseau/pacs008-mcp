<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# 0002. Register tools explicitly, not with decorators

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** maintainer

## Context

FastMCP tools are conventionally declared with `@server.tool(...)`, and
the sixteen tools, three resources and one prompt of this server were.
mutmut 3 never mutates a decorated function, so every handler sat
outside mutation testing: a mutation score over this module described
the private helpers and nothing an agent calls.

## Options considered

1. Keep the decorators and accept that the handlers are untested by
   mutation; the score describes the helpers only.
2. Register the same functions by explicit `server.tool(...)(fn)`,
   `server.resource(...)(fn)` and `server.prompt(...)(fn)` calls in one
   block after the definitions; the registered object, docstring,
   signature, title, annotations and listing order are identical.

## Decision

Option 2, as the sibling `pain001-mcp` did (its ADR 0003). The handlers
are what an agent calls; a mutation score that excludes them measures the
wrong thing. The catalogue an MCP client sees (`tools/list`,
`prompts/list`, `resources/list`, `resources/templates/list`) was dumped
before and after the change and is byte-identical.

## Consequences

A new tool is a plain function plus one registration line in the block
before `main()`; `EXPECTED_TOOLS` in the tests must follow. The mutation
workflow gates the handlers at the floor recorded in the Makefile, and
the property tests in `tests/test_properties.py` state the invariants
that block's handlers keep for any input their schemas admit.
