"""Relevance gate: band split and degrade paths, with Jev faked at the HTTP layer."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from stolperfalle import relevance


def _kus(n: int) -> list[dict]:
    return [{"id": f"ku{i}", "insight": {"summary": f"s{i}", "action": f"a{i}"}} for i in range(n)]


@pytest.fixture
def jev(monkeypatch, tmp_path):
    """Set a key and route relevance's httpx client to a fake Jev answering `probs` (or failing)."""
    monkeypatch.setattr(relevance.settings, "typesafe_api_key", SecretStr("ts_test"))
    monkeypatch.setattr(relevance.settings, "cq_local_db_path", str(tmp_path / "x.db"))
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


@pytest.mark.asyncio
async def test_each_call_logs_probabilities_without_error_text(jev, tmp_path):
    jev["probs"] = [0.10, 0.92, 0.60]
    await relevance.gate("SECRET-ERROR-TEXT", _kus(3))
    await relevance.gate("SECRET-ERROR-TEXT", _kus(3))
    raw = (tmp_path / relevance.LOG_FILE).read_text()
    lines = [json.loads(x) for x in raw.splitlines()]
    assert len(lines) == 2 and "SECRET-ERROR-TEXT" not in raw and "ts_test" not in raw
    assert lines[0]["kus"] == [
        {"id": "ku0", "p": 0.1, "band": "drop"},
        {"id": "ku1", "p": 0.92, "band": "act"},
        {"id": "ku2", "p": 0.6, "band": "confirm"},
    ]
    assert lines[0]["model"] == "jev-1.13.0" and isinstance(lines[0]["latency_ms"], int)


@pytest.mark.asyncio
async def test_unwritable_log_does_not_break_the_gate(jev, monkeypatch):
    monkeypatch.setattr(relevance.settings, "cq_local_db_path", "/nonexistent-dir/x.db")
    jev["probs"] = [0.92]
    out = await relevance.gate("err", _kus(1))
    assert [k["id"] for k in out["results"]] == ["ku0"]
