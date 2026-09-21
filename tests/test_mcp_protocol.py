"""The MCP surface itself — nothing else in the suite touches it.

Every other test exercises the store, embeddings or hooks directly, so nothing
verified that the server stands up, registers its tools, or dispatches a call.
The fastmcp 3 -> 4 upgrade made that gap visible: the whole suite stayed green
while the only signal was mypy.

These would NOT have caught that particular change — `ToolAnnotations` accepts
both `readOnlyHint=` and `read_only_hint=`, since the camelCase spellings are
the MCP wire aliases and pydantic populates by either, so it was a type-checking
fix rather than a behavioural one. What they do catch is the framework upgrade
that stops the server importing, drops a tool from the manifest, or breaks
dispatch — none of which anything else here would notice.
"""
from __future__ import annotations

import pytest
from fastmcp import Client

from stolperfalle.server import mcp

EXPECTED_TOOLS = {"confirm", "flag", "propose", "query", "reflect", "status"}


@pytest.mark.asyncio
async def test_server_registers_its_tools():
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert EXPECTED_TOOLS <= names, f"missing: {EXPECTED_TOOLS - names}"


@pytest.mark.asyncio
async def test_read_only_tools_are_annotated_as_such():
    # Asserted through the client rather than on the source, so it holds
    # whichever spelling the server uses — the point is that the hints survive
    # the round trip to the wire.
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    query = tools["query"]
    assert query.annotations is not None
    assert query.annotations.read_only_hint is True
    assert query.annotations.open_world_hint is False


@pytest.mark.asyncio
async def test_a_tool_call_round_trips(tmp_db, monkeypatch):
    # The tools resolve `stolperfalle.store.store` at call time, so swap the
    # singleton rather than the env — config is read at import.
    import stolperfalle.store as store_mod
    from stolperfalle.embeddings import NoOpEmbeddings

    isolated = store_mod.KnowledgeStore(tmp_db)
    isolated._embeddings = NoOpEmbeddings()
    monkeypatch.setattr(store_mod, "store", isolated)

    async with Client(mcp) as client:
        result = await client.call_tool("status", {})
    assert result.content, "status returned no content"
    assert '"total"' in result.content[0].text
