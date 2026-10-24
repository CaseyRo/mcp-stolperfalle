"""Canonical MCP usage-telemetry middleware. Vendor this file into each fleet server.

One JSON line per tool call on stderr (stdout would corrupt stdio transports):
    {"mcp_usage": 1, "ts": "...", "server": "siyuan", "tool": "get_block",
     "duration_ms": 42, "outcome": "ok", "protocol": "2026-07-28"}

No arguments, no results. A failure inside telemetry never touches the call.
Works on fastmcp 4.x (`on_call_tool` hook).

Register:  mcp.add_middleware(UsageMiddleware("siyuan"))
Non-tool routes (e.g. `@mcp.custom_route` REST hooks) bypass the middleware;
record those with  emit("siyuan", "hook/query", duration_ms, "ok")
Spec:      openspec/changes/upgrade-fleet-fastmcp-4/specs/mcp-usage-telemetry/spec.md
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

from fastmcp.server.middleware import Middleware


def emit(server, tool, duration_ms, outcome, protocol=None):
    """Write one usage line to stderr. Never raises."""
    try:
        sys.stderr.write(json.dumps({
            "mcp_usage": 1,
            # timezone.utc keeps 3.10 support
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),  # noqa: UP017
            "server": server,
            "tool": tool,
            "duration_ms": duration_ms,
            "outcome": outcome,
            # Negotiated MCP era (e.g. 2026-07-28 vs 2025-06-18).
            "protocol": protocol,
        }) + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001, S110 - telemetry never affects the call
        pass


class UsageMiddleware(Middleware):
    def __init__(self, server: str):
        self.server = server

    async def on_call_tool(self, context, call_next):
        start = time.perf_counter()
        outcome = "error"
        try:
            result = await call_next(context)
            outcome = "error" if getattr(result, "is_error", False) else "ok"
            return result
        finally:
            try:  # the context lookups can raise too
                emit(
                    self.server,
                    getattr(context.message, "name", "?"),
                    round((time.perf_counter() - start) * 1000),
                    outcome,
                    getattr(
                        getattr(context.fastmcp_context, "request_context", None),
                        "protocol_version",
                        None,
                    ),
                )
            except Exception:  # noqa: BLE001, S110 - telemetry never affects the call
                pass
