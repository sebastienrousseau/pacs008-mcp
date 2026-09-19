"""The runnable example must keep running against the current server.

``examples/mcp_tools.py`` is what a first-time user copies. Executing it
here means a tool rename or a result-shape change fails the build instead
of leaving the example to rot.
"""

from __future__ import annotations

import runpy
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "mcp_tools.py"


def test_mcp_tools_example_runs(capsys) -> None:
    """The example lists the tools and generates a document."""
    runpy.run_path(str(EXAMPLE), run_name="__main__")
    out = capsys.readouterr().out
    assert "Registered MCP tools:" in out
    assert "'list_message_types'" in out
    assert "list_schemes       -> " in out
    assert "generate_message   -> <?xml" in out
