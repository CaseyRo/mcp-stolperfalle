"""Locks the security-audit hardening: input caps, paging clamp, and the
flag(duplicate) guard. See the CI/CD + pen-test audit (2026-07-07)."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError


async def _propose_one(store) -> str:
    result = await store.propose(
        summary="test ku",
        detail="a small detail",
        action="do the thing",
        domains=["testing"],
        kind="pitfall",
    )
    return result["ku"]["id"]


@pytest.mark.asyncio
async def test_flag_duplicate_requires_superseded_by(store):
    """duplicate ARCHIVES the KU, so it must name a replacement (like superseded)."""
    ku_id = await _propose_one(store)
    with pytest.raises(ToolError, match="requires superseded_by"):
        await store.flag(ku_id=ku_id, reason="duplicate")


@pytest.mark.asyncio
async def test_propose_rejects_oversized_detail(store):
    """Unbounded detail was a persistent storage DoS; the write cap rejects it."""
    with pytest.raises(ToolError):
        await store.propose(
            summary="x",
            detail="a" * 100_001,
            action="do",
            domains=["testing"],
            kind="pitfall",
        )


@pytest.mark.asyncio
async def test_propose_rejects_oversized_domain_element(store):
    """Per-element domain cap stops a single 20MB tag from being stored."""
    with pytest.raises(ToolError):
        await store.propose(
            summary="x",
            detail="d",
            action="do",
            domains=["a" * 200],
            kind="pitfall",
        )


@pytest.mark.asyncio
async def test_query_rejects_oversized_text(store):
    """Query text is guarded before it reaches the embedder."""
    with pytest.raises(ToolError, match="too long"):
        await store.query(text="a" * 16_001)


@pytest.mark.asyncio
async def test_query_negative_limit_is_clamped(store):
    """A negative limit used to make SQLite LIMIT unbounded; now clamped to >=1."""
    await _propose_one(store)
    result = await store.query(text="test", limit=-1)
    assert isinstance(result["count"], int)
    assert result["count"] <= 100
