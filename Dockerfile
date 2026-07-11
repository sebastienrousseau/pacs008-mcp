# syntax=docker/dockerfile:1.6
# Multi-stage build for a minimal pacs008-mcp image.
#
# The container runs the FastMCP server over stdio so an MCP client can
# launch it directly with ``docker run -i --rm pacs008-mcp``.

FROM python:3.12-slim AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pin can be overridden at build-time so the GHCR pipeline can install
# pacs008 from a matching feat/* branch before the parent release hits
# PyPI; the default resolves the published version once available. The
# git client is needed only when the override spec is a git+ URL; it
# stays in this build stage and never ships in the final image.
ARG PACS008_PIP_SPEC="pacs008>=0.0.1"
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# pyproject.toml carries ``readme = "README.md"``, so README.md must be
# present at build-time for ``pip install .`` to resolve the package
# metadata.
COPY pyproject.toml README.md ./
COPY pacs008_mcp ./pacs008_mcp

# Install pacs008 from PyPI (or the override spec), then layer this
# package on top inside a self-contained virtualenv.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install "$PACS008_PIP_SPEC" \
    && /opt/venv/bin/pip install .


FROM python:3.12-slim

LABEL org.opencontainers.image.title="pacs008-mcp" \
      org.opencontainers.image.description="Model Context Protocol server for the pacs008 ISO 20022 FI-to-FI Customer Credit Transfer library." \
      org.opencontainers.image.source="https://github.com/sebastienrousseau/pacs008-mcp" \
      org.opencontainers.image.licenses="Apache-2.0"

# Non-root user (MCP clients launch the container with stdio; no extra
# privileges needed).
RUN groupadd --system mcp && useradd --system --gid mcp --home /home/mcp mcp \
    && mkdir -p /home/mcp \
    && chown -R mcp:mcp /home/mcp

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER mcp
WORKDIR /home/mcp

# A non-zero exit here means an import / dependency mismatch; the MCP
# client will see it before the first tool call.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import pacs008_mcp.server" || exit 1

ENTRYPOINT ["pacs008-mcp"]
