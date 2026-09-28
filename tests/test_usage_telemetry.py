"""Usage telemetry over the wire: one `mcp_usage` stderr line per tool call.

Kept out of test_mcp_protocol.py so it doesn't collide with that file's
arrival in the fastmcp 4 PR (#58).
"""
from __future__ import annotations

import pytest
from fastmcp import Client

from stolperfalle.server import mcp


@pytest.mark.asyncio
async def test_call_tool_writes_one_usage_line(store, monkeypatch, capsys):
    import stolperfalle.store as store_mod

    monkeypatch.setattr(store_mod, "store", store)

    async with Client(mcp) as client:
        await client.call_tool("status", {})
    lines = [line for line in capsys.readouterr().err.splitlines() if '"mcp_usage"' in line]
    assert len(lines) == 1
    assert all(s in lines[0] for s in ('"stolperfalle"', '"status"', '"outcome": "ok"'))
