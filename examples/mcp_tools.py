#!/usr/bin/env python3
"""Example: call the pacs008-mcp server's tools in-process.

Usage:
    pip install pacs008-mcp     # requires Python 3.10+
    python examples/mcp_tools.py

The pacs008 MCP server (launched as ``pacs008-mcp`` over stdio) exposes the
pacs008 library to AI agents. This example invokes the same tools directly
through the FastMCP instance, without a transport, to show what an agent would
receive.
"""

import asyncio

from pacs008_mcp.server import server

# A single flat pacs.008 FI-to-FI Customer Credit Transfer record.
record = [
    {
        "msg_id": "MSG001",
        "creation_date_time": "2026-01-15T10:30:00",
        "nb_of_txs": 1,
        "settlement_method": "CLRG",
        "interbank_settlement_date": "2026-01-15",
        "end_to_end_id": "E2E001",
        "interbank_settlement_amount": 1000.00,
        "interbank_settlement_currency": "EUR",
        "charge_bearer": "SHAR",
        "debtor_name": "Debtor Corp",
        "debtor_agent_bic": "DEUTDEFF",
        "creditor_agent_bic": "COBADEFF",
        "creditor_name": "Creditor Ltd",
    }
]


async def main() -> None:
    tools = await server.list_tools()
    print("Registered MCP tools:", [t.name for t in tools])

    async def call(name, args):
        result = await server.call_tool(name, args)
        # FastMCP returns a (content, structured) tuple or content blocks;
        # pull the first text payload for display.
        content = result[0] if isinstance(result, tuple) else result
        text = content[0].text if content else ""
        return text

    print(
        "list_message_types ->",
        (await call("list_message_types", {}))[:60],
        "…",
    )
    print("list_schemes       ->", await call("list_schemes", {}))
    xml = await call(
        "generate_message",
        {"message_type": "pacs.008.001.08", "records": record},
    )
    print("generate_message   ->", xml[:46], "…")


if __name__ == "__main__":
    asyncio.run(main())
