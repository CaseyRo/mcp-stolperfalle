"""Relevance gate for /hook/query: ask Jev (TypeSafe) whether each candidate KU applies to the error.

Everything a human should review lives here: question, thresholds, model pin. Tuned in the jev lab
(`~/dev/jev/evals/stolperfalle_recall.py`, RESULTS.md 2026-09-28: 25/30 top-1 injections did not
apply; the gate kept 3/30).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from stolperfalle.config import settings

logger = logging.getLogger(__name__)

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
SHORTLIST = 5
TIMEOUT_S = 0.9  # hook client gives /hook/query 1.5 s in total; search takes ≤0.4 s (measured 2026-09-28)
# ponytail: untuned (the eval had no labelled truth); re-run the lab eval after a week of live traffic.
ACT = 0.80
CONFIRM = 0.50
LOG_FILE = "relevance-gate.jsonl"  # next to the DB, on the data volume


def _question(ku: dict) -> dict:
    ins = ku.get("insight") or {}
    return {
        "type": "noul",
        "instructions": {
            "knowledge_unit": {"summary": ins.get("summary", ""), "action": ins.get("action", "")},
            "question": "Would the advice in `knowledge_unit` help someone understand or fix the error in the state?",
        },
        "criteria": {
            "true": "The knowledge unit is about this error's actual cause or the tool that failed",
            "false": "The knowledge unit is about a different tool, error, or situation, even if some words overlap",
        },
    }


async def gate(text: str, candidates: list[dict]) -> dict | None:
    """Split candidates into ACT `results` and CONFIRM `hints`, best first.

    Returns None when the gate cannot run (no key, or any failure), so the caller falls back to
    today's ranked results.
    """
    key = settings.typesafe_api_key.get_secret_value()
    if not key or not candidates:
        return None
    body = {
        "model": MODEL,
        "state": {"error": text[-4096:]},
        "questions": {f"c{i}": _question(ku) for i, ku in enumerate(candidates)},
    }
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            r = await client.post(URL, json=body, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
        probs = [float(data["answers"][f"c{i}"]["noul"]) for i in range(len(candidates))]
    except Exception as e:  # any failure degrades; never leak the key or the body into logs
        logger.warning("relevance gate degraded: %s", type(e).__name__)
        return None

    model = data.get("model", MODEL)
    _record(candidates, probs, model, round((time.perf_counter() - start) * 1000))
    scored = sorted(zip(probs, candidates, strict=True), key=lambda pc: pc[0], reverse=True)
    return {
        "results": [ku for p, ku in scored if p >= ACT],
        "hints": [ku for p, ku in scored if CONFIRM <= p < ACT],
        "model": model,
    }


def _band(p: float) -> str:
    return "act" if p >= ACT else "confirm" if p >= CONFIRM else "drop"


def _record(candidates: list[dict], probs: list[float], model: str, latency_ms: int) -> None:
    """One JSON line per gate call, for tuning ACT/CONFIRM from live traffic (CDI-2085).

    KU ids, probabilities and bands only: never the error text or the key. Appended next to the
    DB on the data volume, so it survives container recreation (docker logs do not).
    """
    line = json.dumps({
        "relevance_gate": 1,
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "latency_ms": latency_ms,
        "act": ACT,
        "confirm": CONFIRM,
        "kus": [
            {"id": ku.get("id"), "p": round(p, 4), "band": _band(p)}
            for ku, p in zip(candidates, probs, strict=True)
        ],
    })
    logger.info("%s", line)
    try:
        with (Path(settings.cq_local_db_path).parent / LOG_FILE).open("a") as f:
            f.write(line + "\n")
    except OSError as e:  # logging must never break the hook path
        logger.warning("relevance log not written: %s", type(e).__name__)
