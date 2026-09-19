# Contributing to pacs008-mcp

Thank you for your interest in contributing to pacs008-mcp. This guide covers
the development workflow and standards.

`pacs008-mcp` is the Model Context Protocol (MCP) server of the **pacs008
suite** — alongside the core [`pacs008`](https://github.com/sebastienrousseau/pacs008)
library and the [`pacs008-loader-mt103`](https://github.com/sebastienrousseau/pacs008-loader-mt103)
MT103 loader. It depends on both and exposes them as agent tools, so most
behaviour lives in the core library.

## Development Setup

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation)
- Git with SSH commit signing configured
- A Developer Certificate of Origin sign-off on every commit (`git commit -s`;
  see [`DCO.txt`](DCO.txt))

### Setup

```bash
# Clone and install
git clone git@github.com:sebastienrousseau/pacs008-mcp.git
cd pacs008-mcp
poetry install

# Verify
poetry run pytest tests/ -q
```

> **Note:** `pacs008-mcp` depends on the core `pacs008` library. Until it is
> published to PyPI, install it from source first:
>
> ```bash
> pip install "git+https://github.com/sebastienrousseau/pacs008.git"
> ```

### On macOS

```bash
brew install python@3.12 poetry
```

### On Linux (Debian/Ubuntu)

```bash
sudo apt install python3 python3-pip
pip install poetry
```

### On WSL

```bash
sudo apt install python3 python3-pip
pip install poetry
# Ensure ~/.local/bin is in PATH
```

## Workflow

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Make changes** — follow the coding standards below
4. **Run tests**:
   ```bash
   poetry run pytest tests/ -v
   ```
5. **Run linters**:
   ```bash
   poetry run ruff check pacs008_mcp/
   poetry run mypy pacs008_mcp/
   poetry run black --check pacs008_mcp/ tests/
   ```
6. **Sign off, sign and commit**:
   ```bash
   git commit -s -S -m "feat: add my feature"
   ```
7. **Push** and open a pull request

## Sign-off (Required)

Every commit **must** carry a `Signed-off-by:` trailer, which is you
certifying the [Developer Certificate of Origin](DCO.txt). `git commit -s`
adds it; the `DCO` workflow fails a pull request that lacks one. To fix an
existing branch: `git rebase --signoff main && git push --force-with-lease`.

## Commit Signing (Required)

All commits **must** be signed with SSH or GPG.

### SSH Signing

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519
git config --global commit.gpgsign true
```

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add a new MCP tool wrapping a services helper
fix: return an error payload instead of raising on bad input
docs: update README with the MCP client config
test: cover the validate_scheme tool
refactor: simplify the tool registration
```

## Coding Standards

- **Line length:** 79 characters (enforced by Black + Ruff)
- **Type hints:** Required on all public functions (mypy strict)
- **Docstrings:** Required on all public classes and functions
- **Tests:** Every new tool or change must include tests
- **Decisions:** A change that shapes the server (a new transport, a new
  registration pattern) gets a record in [`docs/adr/`](docs/adr/index.md)

## Testing

```bash
# Full suite
poetry run pytest tests/ -v

# Single file
poetry run pytest tests/test_mcp_server.py -v
```

## Pull Request Checklist

- [ ] All tests pass (`poetry run pytest`)
- [ ] Linters pass (`ruff check`, `mypy`, `black --check`)
- [ ] Commits are signed and carry a `Signed-off-by:` trailer
- [ ] PR title follows conventional commit format
- [ ] New features include tests and documentation

## Governance

Roles, decision making and how to become a maintainer are in
[`GOVERNANCE.md`](GOVERNANCE.md); the release process is in
[`RELEASING.md`](RELEASING.md).

## License

By contributing, you agree that your contributions will be licensed under
the [Apache License 2.0](LICENSE).
