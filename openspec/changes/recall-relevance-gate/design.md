## Context

See proposal.md. The lab eval's question, criteria, and shortlist size are the tuned starting point (`~/dev/jev/evals/stolperfalle_recall.py`); the hook calls `/hook/query` with `limit=1` under a 1.5 s client budget.

## Decisions

**Gate on the server, not in the plugin.** Alternative: the plugin calls Jev. Rejected: every host would need a TypeSafe key, and the plugin is stdlib-only by design. On the server there is one key (a Komodo variable) and one place to tune.

**Plain `httpx` against the one endpoint, not `typesafe-sdk`.** `httpx` is already a dependency and the API is a single POST; the SDK would add a dependency for about fifteen lines. The lab's "call the SDK directly" non-goal was about not wrapping it, which this also honours.

**One request per hook query, one Noul per candidate.** Independent questions over the same state run in parallel inside one request. Shortlist 5 (the eval found one right answer in 5th place). Question text and criteria are copied from the eval, with thresholds and model pin alongside in `relevance.py`, the one reviewed location.

**Timeout 0.9 s, then degrade.** The hook client (`_client.py`) gives `/hook/query` 1.5 s in total, not the hook's 5 s process timeout; a slower answer would be dropped client-side and marked unreachable instead of degrading. Measured 2026-09-28 on 8 real errors: search median 0.23 s (max 0.39), Jev median 0.31 s (max 0.35), sum max 0.72 s.

## Risks / Trade-offs

- [Gate hides the one useful KU on a borderline case] → CONFIRM candidates stay visible under `hints`; the one-month review (2026-10-27) looks at what was hidden.
- [Thresholds are untuned (eval had no labelled truth)] → 0.80/0.50 marked `ponytail:` in code; re-run the lab eval after a week of live traffic.

## Migration Plan

Deploy with `TYPESAFE_API_KEY` unset (no behaviour change, `degraded: true`), then set the Komodo variable. Rollback: unset it. Only after that do hosts get the hook env vars back (zsh-setup `claude.sh`).
