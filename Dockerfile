# syntax=docker/dockerfile:1.6
# Multi-stage build for a minimal pacs008-mcp image.
#
# The container runs the FastMCP server over stdio so an MCP client can
# launch it directly with ``docker run -i --rm pacs008-mcp``.

# The base image is pinned by digest (OpenSSF Scorecard Pinned-Dependencies);
# Dependabot's docker ecosystem keeps the tag and digest current.
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pyproject.toml carries ``readme = "README.md"``, so README.md must be
# present at build-time for ``pip install .`` to resolve the package
# metadata.
COPY pyproject.toml README.md ./
COPY requirements/docker.txt ./requirements/docker.txt
COPY pacs008_mcp ./pacs008_mcp

# Install the hash-pinned runtime dependencies, then layer this package on
# top with --no-deps, inside a self-contained virtualenv.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes -r requirements/docker.txt \
    && /opt/venv/bin/pip install --no-deps .


FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

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
