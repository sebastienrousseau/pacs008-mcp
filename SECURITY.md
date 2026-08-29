# Security Policy

## Supported versions

Security fixes are applied to the latest released version on PyPI and the
`main` branch. The table below tracks which series receive fixes.

| Version | Supported |
|---------|-----------|
| `0.0.12` | Latest released `0.0.x` only |
| < `0.0.12` | No |

A longer-term support window will be announced here once `1.0.0` ships.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues privately by either:

1. **Preferred:** GitHub's private vulnerability reporting — open a draft
   advisory at <https://github.com/sebastienrousseau/pacs008-mcp/security/advisories/new>.
2. **Email:** `contact@sebastienrousseau.com` with the subject line
   `[pacs008-mcp security]`.

Include, where possible:

- A description of the issue and its impact (confidentiality, integrity,
  availability).
- Steps to reproduce, ideally with a minimal proof of concept.
- The affected version(s) and platform(s).
- Any suggested mitigation or fix.

## What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement | Within 3 business days |
| Initial assessment | Within 10 business days |
| Fix or mitigation plan | Within 30 days for high/critical severity |
| Public disclosure | Coordinated with reporter after a fix is available |

For low-severity issues, the timeline may be longer. We will keep you updated
on progress.

## Scope

In scope:

- Code under `pacs008_mcp/` shipped to PyPI.
- The example scripts under `examples/`.
- The behaviour of the MCP server over its stdio transport, and the
  tools and resources it exposes.

Out of scope:

- Third-party dependencies (please report upstream — we will track the
  advisory and update our pinned ranges). This includes the `mcp` SDK
  and the `pacs008` library, which has its own policy.
- Vulnerabilities that require local code execution on the host already
  running the server.
- Denial-of-service via deliberately crafted input that exceeds documented
  size limits (open a feature request to add a guard instead).

## Hardening guidance for operators

An MCP server is driven by a model, which means its inputs are not
necessarily written by a person who read the docs:

- The server speaks MCP over stdio to its client. Do not expose that
  transport over a network socket without adding authentication and TLS in
  front of it; the protocol has neither.
- Records handed to the tools are validated, not executed. Treat payment
  data passed through them as PII subject to GDPR/PCI-DSS — debtor and
  creditor names and addresses reach the model's context and any
  transcript kept of it. The address tools exist precisely to handle that
  data, so they see the most of it.
- `verify_bic_online` makes an outbound network call. In an environment
  where egress matters, that is the one tool to gate.
- Keep `pacs008-mcp`, `pacs008`, the `mcp` SDK, and the Python interpreter
  patched.

## Credits

We will credit reporters who follow this policy in release notes and the
GitHub advisory, unless they request anonymity.
