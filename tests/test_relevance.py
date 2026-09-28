"""Relevance gate: band split and degrade paths, with Jev faked at the HTTP layer."""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from stolperfalle import relevance


def _kus(n: int) -> list[dict]:
    return [{"id": f"ku{i}", "insight": {"summary": f"s{i}", "action": f"a{i}"}} for i in range(n)]


@pytest.fixture
def jev(monkeypatch):
    """Set a key and route relevance's httpx client to a fake Jev answering `probs` (or failing)."""
    monkeypatch.setattr(relevance.settings, "typesafe_api_key", SecretStr("ts_test"))
    state: dict = {"probs": [], "status": 200}
    real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer ts_test"
        answers = {f"c{i}": {"type": "noul", "noul": p} for i, p in enumerate(state["probs"])}
        return httpx.Response(state["status"], json={"model": "jev-1.13.0", "answers": answers})

    monkeypatch.setattr(
        relevance.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return state


@pytest.mark.asyncio
async def test_bands_split_results_hints_and_drop(jev):
    jev["probs"] = [0.10, 0.92, 0.60, 0.85, 0.30]
    out = await relevance.gate("err", _kus(5))
    assert [k["id"] for k in out["results"]] == ["ku1", "ku3"]  # ACT, best first
    assert [k["id"] for k in out["hints"]] == ["ku2"]           # CONFIRM
    assert out["model"] == "jev-1.13.0"                          # ASK ku0, ku4 dropped


@pytest.mark.asyncio
async def test_nothing_applies_returns_empty(jev):
    jev["probs"] = [0.02, 0.07]
    out = await relevance.gate("err", _kus(2))
    assert out["results"] == [] and out["hints"] == []


@pytest.mark.asyncio
async def test_api_failure_degrades(jev):
    jev["status"] = 529
    assert await relevance.gate("err", _kus(2)) is None


@pytest.mark.asyncio
async def test_no_key_degrades(monkeypatch):
    monkeypatch.setattr(relevance.settings, "typesafe_api_key", SecretStr(""))
    assert await relevance.gate("err", _kus(2)) is None
