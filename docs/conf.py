"""Sphinx configuration for pacs008-mcp documentation."""

from __future__ import annotations

import importlib.metadata

project = "pacs008-mcp"
author = "Sebastien Rousseau"
copyright = "2023-2026, Sebastien Rousseau"

try:
    release = importlib.metadata.version("pacs008-mcp")
except importlib.metadata.PackageNotFoundError:
    release = "0.0.0+dev"
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "myst_parser",
]

# MyST options: enable Markdown directives without breaking standard
# CommonMark renders.
myst_enable_extensions = ["colon_fence", "deflist", "linkify"]

# The README's table of contents links to its own headings by slug, so
# every heading down to level 3 gets an anchor. Its architecture diagram
# is a ```mermaid fence, which GitHub renders and Pygments does not know;
# it is shown as plain text here rather than failing the strict build.
myst_heading_anchors = 3
# ``pacs008_mcp.server`` re-exports pydantic's ``Field`` by importing it;
# the typehints extension cannot resolve pydantic's own forward reference
# in that signature. It is not part of this package's API.
suppress_warnings = [
    "misc.highlighting_failure",
    "sphinx_autodoc_typehints.forward_reference",
]

# Allow myst_parser to ingest the top-level README.md.
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Furo theme: lightweight, modern, mobile-friendly.
html_theme = "furo"
html_title = f"pacs008-mcp {release}"

# Cross-link to the Python stdlib. The pacs008 library publishes no
# Sphinx inventory, so there is nothing to map for it.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Autodoc defaults.
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
