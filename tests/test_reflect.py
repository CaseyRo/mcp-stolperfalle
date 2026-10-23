"""Tests for the reflect module — heuristic and LLM-based extraction."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from stolperfalle.models import KUKind, ReflectCandidate
from stolperfalle.reflect import (
    _classify_kind,
    _extract_action,
    _extract_domains,
    _extract_summary,
    _heuristic_extract,
    _score_generalizability,
    _split_into_segments,
    reflect_with_dedup,
)

# ── Segment splitting ──────────────────────────────────────────────────


class TestSplitSegments:
    def test_numbered_items(self):
        text = (
            "Intro text about the session.\n\n"
            "1. First issue with something important that caused real problems in production.\n"
            "2. Second issue with another thing that was poorly documented and easy to miss."
        )
        segments = _split_into_segments(text)
        assert len(segments) >= 2

    def test_bold_numbered_items(self):
        text = (
            "1. **Bold first**: detail about the first issue and why it matters for production systems.\n"
            "2. **Bold second**: detail about the second issue that affected multiple services."
        )
        segments = _split_into_segments(text)
        assert len(segments) >= 2

    def test_paragraph_splitting(self):
        text = (
            "First paragraph with enough content to be meaningful and describe a real technical issue.\n\n"
            "Second paragraph also with enough content to matter and provide actionable guidance."
        )
        segments = _split_into_segments(text)
        assert len(segments) == 2

    def test_short_text_returns_empty(self):
        assert _split_into_segments("too short") == []

    def test_single_substantial_block(self):
        text = "A substantial block of text that describes something important enough to extract a learning from."
        segments = _split_into_segments(text)
        assert len(segments) == 1


# ── Domain extraction ──────────────────────────────────────────────────


class TestDomainExtraction:
    def test_docker_domains(self):
        domains = _extract_domains("Docker container DNS issue")
        assert "docker" in domains

    def test_multiple_domains(self):
        domains = _extract_domains("Slack webhook to Attio via REST API")
        assert "slack" in domains
        assert "attio" in domains
        assert "rest" in domains
        assert "webhooks" in domains

    def test_unknown_returns_general(self):
        domains = _extract_domains("Some obscure technology problem")
        assert domains == ["general"]


# ── Kind classification ────────────────────────────────────────────────


class TestKindClassification:
    def test_pitfall_silent_fail(self):
        assert _classify_kind("The function silently fails without logging") == KUKind.pitfall

    def test_pitfall_mismatch(self):
        assert _classify_kind("Token mismatch caused 401 errors") == KUKind.pitfall

    def test_workaround_had_to(self):
        assert _classify_kind("Had to rewrite the handler to fetch data separately") == KUKind.workaround

    def test_gap_like_falls_through_to_pitfall_or_workaround(self):
        # gap-signal is no longer a proposable kind in CQ v1 — gap-like
        # language falls through to pitfall (default) unless it's clearly
        # a workaround.
        result = _classify_kind("Missing support for batch operations")
        assert result in (KUKind.pitfall, KUKind.workaround)

    def test_default_pitfall(self):
        assert _classify_kind("Something happened") == KUKind.pitfall


# ── Generalizability scoring ───────────────────────────────────────────


class TestGeneralizability:
    def test_general_signals_boost(self):
        general = _score_generalizability(
            "This is a best practice that applies to any project using webhooks. "
            "Always verify the HMAC signature before processing."
        )
        specific = _score_generalizability(
            "Our project had a bug in PR #123 where we forgot to update the config."
        )
        assert general > specific

    def test_technology_mentions_boost(self):
        multi_tech = _score_generalizability(
            "Docker container with Redis and Postgres had networking issues with Caddy reverse proxy."
        )
        no_tech = _score_generalizability(
            "Something went wrong with the thing and we fixed it by changing something."
        )
        assert multi_tech > no_tech

    def test_short_text_penalized(self):
        short = _score_generalizability("Docker issue.")
        long = _score_generalizability(
            "Docker container DNS resolution fails on the default bridge network. "
            "User-defined bridge networks resolve container names automatically."
        )
        assert long > short

    def test_score_bounded(self):
        score = _score_generalizability("x" * 50)
        assert 0.0 <= score <= 1.0


# ── Summary extraction ─────────────────────────────────────────────────


class TestSummaryExtraction:
    def test_bold_header(self):
        text = "**Attio webhook HMAC mismatch**: caused 401 on every delivery"
        assert _extract_summary(text) == "Attio webhook HMAC mismatch"

    def test_first_sentence(self):
        text = "The default bridge network has no DNS. This means containers can't resolve each other."
        assert "default bridge" in _extract_summary(text)

    def test_max_length(self):
        text = "A" * 300 + ". End."
        assert len(_extract_summary(text)) <= 280


# ── Action extraction ──────────────────────────────────────────────────


class TestActionExtraction:
    def test_had_to_pattern(self):
        text = "Had to rewrite the handler to fetch data via the REST API after notification."
        action = _extract_action(text)
        assert "rewrite" in action.lower()

    def test_fallback(self):
        text = "Something happened that was unexpected."
        action = _extract_action(text)
        assert "Verify" in action


# ── Full heuristic extraction ──────────────────────────────────────────


class TestHeuristicExtraction:
    def test_attio_session(self):
        summary = (
            "1. **Attio webhook HMAC mismatch**: Secret didn't match, caused 401.\n"
            "2. **Attio payload is notification-only**: Sends IDs not data. Poorly documented.\n"
            "3. **Per-attribute webhook events**: Single creation triggers many deliveries."
        )
        candidates = _heuristic_extract(summary)
        assert len(candidates) >= 2
        assert all(isinstance(c, ReflectCandidate) for c in candidates)
        # Should be sorted by generalizability (descending)
        scores = [c.generalizability_score for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_empty_summary(self):
        assert _heuristic_extract("") == []

    def test_no_generalizable_content(self):
        assert _heuristic_extract("ok") == []


# ── LLM extraction ────────────────────────────────────────────────────


class TestLLMExtraction:
    @staticmethod
    def _configure(monkeypatch):
        from pydantic import SecretStr
        monkeypatch.setattr("stolperfalle.config.settings.cq_llm_api_key", SecretStr("test-key"))
        monkeypatch.setattr("stolperfalle.config.settings.cq_llm_model", "test-model")

    @staticmethod
    def _mock_client(response):
        client = AsyncMock()
        client.messages.create.return_value = response
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return patch("anthropic.AsyncAnthropic", return_value=client), client

    @pytest.mark.asyncio
    async def test_llm_not_configured_returns_none(self, monkeypatch):
        from pydantic import SecretStr
        monkeypatch.setattr("stolperfalle.config.settings.cq_llm_api_key", SecretStr(""))
        from stolperfalle.reflect import _llm_extract
        result = await _llm_extract("test session")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_returns_candidates(self, monkeypatch):
        self._configure(monkeypatch)
        text = json.dumps({"candidates": [{
            "summary": "Webhook HMAC secrets must match exactly",
            "detail": "Attio webhooks show as active even when HMAC fails",
            "action": "Verify HMAC secret matches between provider and server",
            "domains": ["webhooks", "auth"],
            "kind": "pitfall",
            "generalizability_score": 0.8,
        }]})
        response = SimpleNamespace(
            stop_reason="end_turn", stop_details=None,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        )
        patcher, client = self._mock_client(response)
        with patcher:
            from stolperfalle.reflect import _llm_extract
            result = await _llm_extract("test session about webhooks")

        assert result is not None
        assert len(result) == 1
        assert result[0].summary == "Webhook HMAC secrets must match exactly"
        assert result[0].kind == KUKind.pitfall
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["model"] == "test-model"
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        assert "temperature" not in kwargs  # rejected by current models

    @staticmethod
    def _api_error(cls, status: int):
        import httpx2

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        return cls("boom", response=httpx2.Response(status, request=request), body=None)

    @pytest.mark.asyncio
    async def test_llm_refusal_falls_back_with_reason(self, monkeypatch):
        self._configure(monkeypatch)
        response = SimpleNamespace(stop_reason="refusal", stop_details={"category": None}, content=[])
        patcher, _ = self._mock_client(response)
        with patcher:
            result = await reflect_with_dedup("1. **Docker bridge DNS fails**: no DNS between containers on the default bridge.", store=None)
        assert result["method"] == "heuristic"
        assert result["fallback_reason"] == "LLMRefused"

    @pytest.mark.asyncio
    async def test_llm_config_error_is_raised_not_hidden(self, monkeypatch):
        # A wrong key or model id must fail loudly; a heuristic answer would
        # hide the broken deployment (the gpt-6-luna `temperature` 400).
        import anthropic

        from stolperfalle.reflect import LLMConfigError

        self._configure(monkeypatch)
        patcher, client = self._mock_client(None)
        client.messages.create.side_effect = self._api_error(anthropic.AuthenticationError, 401)
        with patcher, pytest.raises(LLMConfigError, match="HTTP 401"):
            await reflect_with_dedup("some session", store=None)

    @pytest.mark.asyncio
    async def test_llm_server_error_falls_back_and_is_counted(self, monkeypatch):
        import anthropic

        from stolperfalle.reflect import fallback_counts

        self._configure(monkeypatch)
        monkeypatch.setattr("stolperfalle.reflect.fallback_counts", fallback_counts.__class__())
        from stolperfalle import reflect as reflect_mod

        patcher, client = self._mock_client(None)
        client.messages.create.side_effect = self._api_error(anthropic.InternalServerError, 500)
        with patcher:
            result = await reflect_with_dedup("1. **Webhook payload is notification-only**: provider sends IDs, not records. Poorly documented.", store=None)
        assert result["method"] == "heuristic"
        assert result["fallback_reason"] == "InternalServerError"
        assert reflect_mod.fallback_counts["InternalServerError"] == 1

    @pytest.mark.asyncio
    async def test_reflect_tool_surfaces_config_error(self, monkeypatch):
        import anthropic
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        from stolperfalle.server import mcp

        self._configure(monkeypatch)
        patcher, client = self._mock_client(None)
        client.messages.create.side_effect = self._api_error(anthropic.NotFoundError, 404)
        with patcher:
            async with Client(mcp) as mcp_client:
                with pytest.raises(ToolError, match="CQ_LLM_MODEL"):
                    await mcp_client.call_tool("reflect", {"session_summary": "anything"})


# ── Integration: reflect_with_dedup ────────────────────────────────────


@pytest.mark.asyncio
async def test_reflect_with_dedup_heuristic(monkeypatch):
    """reflect_with_dedup works with heuristic fallback (no LLM configured)."""
    monkeypatch.setenv("CQ_LLM_API_KEY", "")

    result = await reflect_with_dedup(
        "1. **Docker bridge DNS fails**: Default bridge has no DNS resolution between containers.\n"
        "2. **Webhook payload is notification-only**: Provider sends IDs not full records. Poorly documented.",
        store=None,
    )
    assert result["method"] == "heuristic"
    assert len(result["candidates"]) >= 2
    assert all("summary" in c for c in result["candidates"])


@pytest.mark.asyncio
async def test_reflect_empty_summary(monkeypatch):
    monkeypatch.setenv("CQ_LLM_API_KEY", "")
    result = await reflect_with_dedup("", store=None)
    assert result["candidates"] == []


@pytest.mark.asyncio
async def test_reflect_with_store_dedup(store, monkeypatch):
    """Candidates matching existing KUs are filtered out."""
    monkeypatch.setenv("CQ_LLM_API_KEY", "")

    # The store fixture uses NoOpEmbeddings, so dedup won't actually filter
    # (no embeddings to compare). But it should still work without errors.
    result = await reflect_with_dedup(
        "1. **Some issue**: Docker bridge DNS fails between default bridge containers.\n"
        "2. **Another issue**: Webhook signatures must be verified before processing payload.",
        store=store,
    )
    assert "candidates" in result
    assert isinstance(result["candidates"], list)
