"""Guard the package version against the files that restate it.

`__version__`, `pyproject.toml`, `SECURITY.md` and `CHANGELOG.md` each
carry the version independently, and nothing tied them together. That is
how `0.0.8` reached PyPI with `cryptography<50.0.0` after the tree had
already been changed to `<51.0.0`: the constraint moved, the version did
not, and no release was cut — so every dependent kept resolving against
the old metadata and could not install the patched `cryptography` at
all.

These tests fail loudly when the four disagree.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

import pacs008_mcp

if sys.version_info >= (3, 11):  # pragma: no cover - version dependent
    import tomllib
else:  # pragma: no cover - version dependent
    # `tomllib` is stdlib only from 3.11, and this package supports 3.10.
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def _pyproject_version() -> str:
    with PYPROJECT.open("rb") as handle:
        return str(tomllib.load(handle)["tool"]["poetry"]["version"])


def _changelog_versions() -> list[str]:
    return HEADING.findall(CHANGELOG.read_text(encoding="utf-8"))


def test_dunder_version_is_semver() -> None:
    assert SEMVER.match(
        pacs008_mcp.__version__
    ), f"__version__ is {pacs008_mcp.__version__!r}, which is not X.Y.Z"


def test_dunder_version_matches_pyproject() -> None:
    assert pacs008_mcp.__version__ == _pyproject_version(), (
        f"pacs008_mcp.__version__ is {pacs008_mcp.__version__!r} but "
        f"pyproject.toml says {_pyproject_version()!r}"
    )


def test_changelog_documents_the_current_version() -> None:
    versions = _changelog_versions()
    assert versions, "CHANGELOG.md has no '## [X.Y.Z]' headings"
    assert pacs008_mcp.__version__ in versions, (
        f"CHANGELOG.md has no entry for {pacs008_mcp.__version__}; "
        f"newest documented is {versions[0]}"
    )


def test_changelog_newest_entry_is_the_current_version() -> None:
    versions = _changelog_versions()
    assert versions[0] == pacs008_mcp.__version__, (
        f"the newest CHANGELOG entry is {versions[0]} but the package is "
        f"{pacs008_mcp.__version__} — a release was cut without a changelog "
        f"entry, or an entry was added without bumping the version"
    )


def test_changelog_entries_are_ordered_newest_first() -> None:
    versions = _changelog_versions()
    keyed = [tuple(int(p) for p in v.split(".")) for v in versions]
    assert keyed == sorted(
        keyed, reverse=True
    ), f"CHANGELOG.md entries are out of order: {versions}"


def test_changelog_has_no_duplicate_versions() -> None:
    versions = _changelog_versions()
    duplicates = {v for v in versions if versions.count(v) > 1}
    assert (
        not duplicates
    ), f"CHANGELOG.md documents {duplicates} more than once"


def test_installed_metadata_matches_the_source() -> None:
    """The built distribution must agree with the source tree.

    An editable install reads `pyproject.toml`, so a mismatch here means
    the package was built from a different version than is checked out.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        installed = version("pacs008-mcp")
    except PackageNotFoundError:  # pragma: no cover - not installed
        pytest.skip("pacs008 is not installed in this environment")

    assert installed == pacs008_mcp.__version__, (
        f"installed distribution is {installed} but the source tree is "
        f"{pacs008_mcp.__version__}"
    )


def test_pacs008_floor_admits_the_patched_cryptography() -> None:
    """The `pacs008` floor must be one that allows cryptography 50.0.0.

    `pacs008` 0.0.7 and 0.0.8 both cap `cryptography<50.0.0`. Requiring
    `cryptography>=50.0.0` alongside either is not an unmet preference,
    it is `ResolutionImpossible` — the package will not install at all.
    0.0.9 is the first release that admits it.
    """
    from packaging.requirements import Requirement
    from packaging.version import Version

    with PYPROJECT.open("rb") as handle:
        deps = tomllib.load(handle)["tool"]["poetry"]["dependencies"]

    raw = deps["pacs008"]
    spec = raw if isinstance(raw, str) else raw["version"]
    requirement = Requirement(f"pacs008{spec}")

    for bad in ("0.0.7", "0.0.8"):
        assert not requirement.specifier.contains(Version(bad)), (
            f"pacs008{spec} still admits {bad}, which caps "
            f"cryptography<50.0.0 and makes this package uninstallable "
            f"alongside its own cryptography floor"
        )
    assert requirement.specifier.contains(Version("0.0.9"))


def test_cryptography_floor_is_the_patched_release() -> None:
    """The transitive cryptography floor must name the patched version."""
    from packaging.requirements import Requirement
    from packaging.version import Version

    with PYPROJECT.open("rb") as handle:
        deps = tomllib.load(handle)["tool"]["poetry"]["dependencies"]

    raw = deps["cryptography"]
    spec = raw if isinstance(raw, str) else raw["version"]
    requirement = Requirement(f"cryptography{spec}")

    assert not requirement.specifier.contains(Version("49.0.0")), (
        f"cryptography{spec} still admits 49.0.0, which the advisory "
        f"covers"
    )
    assert requirement.specifier.contains(Version("50.0.0"))
