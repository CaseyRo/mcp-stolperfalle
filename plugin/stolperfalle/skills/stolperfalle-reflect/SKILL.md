---
name: stolperfalle:reflect
description: Extract generalizable learnings from the current session and propose them as Knowledge Units
---

# /stolperfalle:reflect — Session Knowledge Extraction

Run this at the end of a substantive coding or debugging session to capture reusable learnings into the Stolperfalle knowledge base.

## Steps

1. **Summarize the session** — in plain prose, cover:
   - What problems did you hit? (Error signatures, tool failures, surprising behavior.)
   - What workarounds or fixes did you apply?
   - What was non-obvious — the thing a future agent wouldn't guess from the docs?

2. **Call reflect**:
   ```
   reflect(session_summary="<your summary>")
   ```

   Each candidate comes back pre-filled with `summary`, `detail`, `action`, `domains`, `kind`, `context_*`, `severity`, and `verified_fix` (the extractor's read of whether the failure was observed AND a fix was seen to work in this session). You get one candidate per distinct finding; reflect does not cap them.

3. **Pick at most 3 to propose.** A candidate qualifies only if it is backed by an observed failure *and* a verified fix in this session. Use `verified_fix` as a first filter, then check it against what you actually saw: you were there, the extractor only read your summary. Of the qualifying ones, keep the 3 most generalizable (would it help a DIFFERENT agent on a DIFFERENT project?). Everything else is **listed, not proposed**.

   Before proposing, check: is the `action` a concrete command, setting or check (not "be careful with X")? Are the exact names, flags and error strings still in it? Does `severity` feel right? (`critical` is for things that break production if ignored.)

4. **Propose the keepers** (at most 3):
   ```
   propose(
     summary=candidate["summary"],
     detail=candidate["detail"],
     action=candidate["action"],
     domains=candidate["domains"],
     kind=candidate["kind"],
     context_languages=candidate.get("context_languages", []),
     context_frameworks=candidate.get("context_frameworks", []),
     context_environment=candidate.get("context_environment"),
     context_pattern=candidate.get("context_pattern"),
     severity=candidate.get("severity", "medium"),
   )
   ```

   If a propose call comes back as an HTML "Sorry, you have been blocked" page, a WAF on the connector path matched shell commands or SQL in the text. Retry the same call with `summary`, `detail` and `action` each base64-encoded (UTF-8) and `encoding="base64"`. Do not reword the content to get past the filter.

5. **Report** — tell the user the IDs you proposed, and list the candidates you did not propose with one line each (why: no verified fix, over the cap, or not generalizable). The user can ask you to propose one of those.

## Good candidates

- Error patterns that took multiple attempts to diagnose.
- Version-specific pitfalls (`context_environment="xcode-16"`, `context_environment="node-22"`).
- Workarounds for known framework bugs.
- Tool configuration that isn't well-documented.
- Anything an agent would want to know BEFORE starting similar work.

## Bad candidates (skip these)

- Project-specific business logic.
- One-time setup steps unlikely to recur.
- Things well-documented in official docs.
- `gap-signal`-shaped observations — those emerge automatically from query-miss patterns; you don't propose them directly.

## Kind guidance

- `pitfall` — "here's a trap, here's how to avoid it."
- `workaround` — "the real fix is upstream; until then, do X."
- `tool-recommendation` — "for this problem, reach for this tool."
