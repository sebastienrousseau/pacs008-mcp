<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau <sebastian.rousseau@gmail.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Toolchain policy

Python 3.10 is the floor (`python = ">=3.10,<4.0"` in `pyproject.toml`),
with Linux CI on 3.10, 3.11, 3.12, 3.13 and 3.14. The container image runs
3.14. Raising the floor is a maintainer decision, recorded in the changelog,
and moves with the `pacs008` core library. No distro-system Python is
supported.
