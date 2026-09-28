## Why

The error-recall hook injects the top-ranked KU from `/hook/query` with only a trust gate, and that gate filters nothing: 496 of 526 KUs sit at exactly 0.5 and it skips `< 0.5`. The jev lab replayed 30 real tool errors (`~/dev/jev/evals/RESULTS.md`, 2026-09-28): the hook would inject on all 30, and on 25 the injected KU does not apply. A relevance judgment per candidate cuts that to 3 injections, all on-point. Casey decided (3.2b) to land this gate before hook recall is re-enabled on any host.

## What Changes

- `/hook/query` asks Jev, per candidate in a small shortlist, whether the KU applies to the error text, and returns only candidates judged to apply (ACT band) in `results`.
- Candidates in the CONFIRM band come back under a new `hints` key, which today's hook ignores.
- Without `TYPESAFE_API_KEY`, or when Jev fails, the endpoint answers exactly as today and marks the response `degraded`.
- New optional setting `TYPESAFE_API_KEY` (Komodo variable on the stack).

## Non-goals

- The `query` MCP tool is unchanged; agents calling it deliberately get the full ranked list.
- No change to ranking (FTS + vector), KU kind, generalizability, or dedup — those are separate lab tasks.
- No plugin change: the hook keeps injecting `results[0]`; injecting `hints` is a later decision.

## Capabilities

### New Capabilities
- `recall-relevance`: relevance gating of `/hook/query` results with Jev, bands, and degraded behaviour.

### Modified Capabilities
None.

## Impact

- `src/stolperfalle/server.py` (`hook_query`), new `src/stolperfalle/relevance.py`, `src/stolperfalle/config.py`.
- One HTTP call to `api.typesafe.ai` per hook query (~1.7k input tokens, ~$0.00007); adds ~0.3 s (measured median) to a call the hook gives 1.5 s.
- Data sent: error text (≤ 4096 chars) and KU summary/action — internal data under the jev data-boundary spec.
