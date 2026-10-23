# Stolperfalle in one page

**What it is.** A self-hosted memory for AI coding agents. When an agent hits a trap (a silent
misconfiguration, an API that behaves differently from its docs, a tool that fails without an error),
the lesson is stored as a *knowledge unit* (KU): what happened, why it matters, and what to do next time.
When another agent later hits a matching error, the KU is put into its context before it starts guessing.

**Who it is for.** Teams running AI coding agents (Claude Code in particular) across many repositories,
where the same mistakes get rediscovered session after session.

**How it works.**

- **Write:** an agent calls `propose`, or `reflect` drafts candidates from a session summary for the agent
  to review and propose.
- **Read:** Claude Code hooks query the store when a prompt or a failed shell command carries a real error
  signal (a traceback, a non-zero exit code, an HTTP status), and inject the best-matching KU.
- **Quality:** agents `confirm` advice that worked and `flag` advice that was wrong, stale or duplicated.
- **Standard:** KUs follow Mozilla AI's open [cq](https://github.com/mozilla-ai/cq) schema, with local
  extensions carried in its `extensions` slot ([registry](docs/cq-extensions.md)).

## What data goes where

| Operation | Leaves your server? |
|---|---|
| `query`, `propose`, `confirm`, `flag`, `status` | No. SQLite on your server; embeddings computed locally (`all-MiniLM-L6-v2`) unless you set `CQ_EMBEDDING_API_URL`. |
| Hooks | Error text goes from the developer's machine to **your** server, nowhere else. |
| `reflect` | The session summary goes to Anthropic (`claude-sonnet-5-5`) **if** `CQ_LLM_API_KEY` is set. Without a key a local heuristic runs and nothing leaves. |

## Access, isolation, provenance

- **Auth:** bearer tokens for agents and automations; Cloudflare Access OIDC for browser clients.
- **Isolation:** every KU has an `owner_org`, and `query` only returns KUs from `TRUSTED_ORGS`. Today this
  is a read filter (default: trust all); write-side permissions are planned. The clean boundary today is
  **one install per team or client**.
- **Provenance:** each install signs its KUs with its own Ed25519 key (`did:key`), stored outside the
  database, so a database leak does not let anyone forge KUs.

## Known gaps (October 2026)

- **No redaction on write.** Agents can and did write client names and internal hostnames into KUs; a
  store audit found and rewrote them by hand. Until redaction exists, keep installs per client.
- **No hard delete.** `flag` archives a KU but keeps the row. Erasure (e.g. a GDPR Art. 17 request) needs
  an operator to delete it from SQLite.
- **Confidence is mostly unrated.** 94% of KUs sit at the default confidence with zero confirmations,
  because agents rarely call `confirm`. Treat confidence as weak until it is derived from usage.
- **No edit path.** A correction is a new KU that supersedes the old one, and near-identical fixes can be
  rejected as duplicates.
- **No measured productivity effect yet.** See the pilot section.
- **One LLM provider.** `reflect` uses the Anthropic SDK; switching providers is a code change today.

## Cost and operations

- **Runtime:** one container (about 1 GB with the CPU build of PyTorch and the embedding model) and one
  SQLite volume. Migrations snapshot the database before any breaking change.
- **LLM:** about one US cent per `reflect` call; under ~30 € a month even at 100 calls a day; zero
  without a key. Model choice and method: [docs/reflect-model-eval.md](docs/reflect-model-eval.md).
- **Change control:** `main` is branch-protected; every change needs green tests (ruff, mypy, pytest) and a
  `pip-audit` dependency check. Production rebuilds from source on merge.

## Exit

- **License:** MIT.
- **Data:** a single SQLite file. KUs serialize to the upstream cq schema (`to_cq_json_strict`), so they can
  move to any other cq implementation.
- **LLM:** optional. Remove the key and everything except `reflect`'s draft quality keeps working.

## A pilot worth running

Four weeks, one team, one install. Measure before/after on the hook-detected errors:

1. How often the same error signature recurs across sessions.
2. How often an injected KU is followed by a successful next command.
3. How many KUs get confirmed or flagged, which shows whether the quality signal starts working.

Further reading: [README](README.md) (setup and configuration),
[docs/reflect-model-eval.md](docs/reflect-model-eval.md) (model comparison and store audit),
[docs/cq-extensions.md](docs/cq-extensions.md) (schema extensions).
