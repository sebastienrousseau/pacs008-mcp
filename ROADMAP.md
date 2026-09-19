# pacs008-mcp Roadmap

This roadmap tracks what is planned for the MCP companion of the
[pacs008](https://github.com/sebastienrousseau/pacs008) library. It
summarises the CHANGELOG and the open issues; it does not promise work
that is not tracked there. Releases ship when the gates pass, not on a
calendar.

## v0.0.12 (current)

- Sixteen tools over `pacs008`: message-type and scheme discovery,
  record and scheme validation, XML generation, XSD validation, inbound
  parsing, `convert_mt103` (MT103 to pacs.008 records), the four
  structured-address tools, and `verify_bic_online`.
- Three resources (`pacs008://message-types`, `pacs008://schemes`,
  `pacs008://scheme/{scheme_id}`) and one prompt
  (`build_pacs008_message`).
- 100% line+branch coverage gate, the shared suite conformance test, a
  dispatch benchmark, and a scheduled check that the published suite
  agrees with itself.
- One version number across `pacs008`, `pacs008-mcp` and
  `pacs008-loader-mt103`.

## Next release (on `main`, unreleased)

- stdio, streamable HTTP (2026-07-28 and 2025-11-25) and SSE from one
  command line (ADR 0001).
- Runs on both supported majors of the `mcp` SDK through a
  compatibility shim; a fresh install gets 2.x.

## Beyond

No further work is scheduled. There are no open issues at the time of
writing. New tools follow the library: when a helper lands in `pacs008`,
it is ported here in the same release window. The structured-address
tool descriptions track Swift's CBPR+ timing and will be updated when
Swift confirms the replacement date.

## Out of scope (handled elsewhere)

- **The CLI and REST API** - see the core
  [`pacs008`](https://github.com/sebastienrousseau/pacs008) library.
- **MT103 parsing itself** - see
  [`pacs008-loader-mt103`](https://github.com/sebastienrousseau/pacs008-loader-mt103);
  `convert_mt103` only wraps it.
