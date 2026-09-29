# mcp-stolperfalle

Experiential knowledge capture and recall MCP server for AI coding agents. A conforming-plus-extending implementation of Mozilla AI's [cq](https://github.com/mozilla-ai/cq) — Phase 1 of the machine-readable org layer we're building at [CDiT](https://cdit-works.de).

> **Renamed 2026-07-11 (was `mcp-stolperstein`).** *Stolpersteine* are [Gunter Demnig's brass Holocaust memorial stones](https://en.wikipedia.org/wiki/Stolperstein) set into German pavements; using that name for a casual dev tool risked trivializing the memorial, so the project was renamed to **Stolperfalle** (an ordinary German word for a trip hazard — same *stolpern* "stumble" root, none of the weight). Rationale and rollout: [`openspec/changes/archive/2026-07-11-rename-product-name`](openspec/changes/archive/2026-07-11-rename-product-name/proposal.md). The old GitHub URL auto-redirects. The rename also extends to the wire-protocol extension namespace: fields now ride the upstream `extensions` slot under `stolperfalle:*` keys (the previous `stolperstein:*` namespace was our own emitted value, not part of cq — see [`docs/cq-extensions.md`](docs/cq-extensions.md)).

It is for developers who run AI coding agents (Claude Code in particular) across many repositories and want the lessons from one session, such as a pitfall, a workaround or a tool that fits, to surface automatically in the next one. It ships an MCP server plus a Claude Code plugin whose hooks query the server when a real error shows up.

## Requirements

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/), or Docker
- About 1 GB of disk for the CPU build of PyTorch and the local embedding model (`all-MiniLM-L6-v2`), or an embeddings API via `CQ_EMBEDDING_API_URL`
- Optional: an OpenAI-compatible chat endpoint for `reflect` (without one it falls back to a heuristic extractor)

## Quick start

```bash
git clone https://github.com/CaseyRo/mcp-stolperfalle.git
cd mcp-stolperfalle
uv sync
CQ_LOCAL_DB_PATH=./stolperfalle.db uv run mcp-stolperfalle        # stdio mode
CQ_LOCAL_DB_PATH=./stolperfalle.db uv run mcp-stolperfalle migrate  # apply DB migrations and exit
```

The default database path is `/data/stolperstein.db`, which suits the container; set `CQ_LOCAL_DB_PATH` for a local run.

Docker (streamable HTTP on port 8716, path `/mcp`, persistent volumes):

```bash
cp .env.example .env   # set MCP_STOLPERFALLE_API_KEY and MCP_STOLPERFALLE_PUBLIC_URL
docker compose up -d --build
```

`compose.yaml` builds from source, runs as a non-root user with all capabilities dropped, and stores data in the `stolperstein-data` and `fastmcp-data` volumes. `GET /health` is an unauthenticated liveness probe.

## What this is

Stolperfalle is the local node — one per install — where Knowledge Units (KUs) live: problem→action pairs, with confidence, severity, provenance, and org ownership. Agents `query()`, `propose()`, `confirm()`, `flag()`, and `reflect()` against it.

On the wire, it conforms to the upstream cq schema strictly. Locally it carries a richer superset (severity, status state machine, kind enum, rich provenance, multi-tenant `owner_org`). See [`docs/cq-extensions.md`](docs/cq-extensions.md) for the extension registry. Upstream discussion of proposed additions: [mozilla-ai/cq#286](https://github.com/mozilla-ai/cq/discussions/286).

## Tools, prompts and resources

| Tool | Kind | What it does |
|------|------|--------------|
| `query` | read | Search KUs by natural language, error signature or technology tags (hybrid FTS5 and vector search, filtered by `TRUSTED_ORGS`) |
| `propose` | write | Propose a new KU from a discovered insight |
| `confirm` | write | Record that a KU's advice held; raises its confidence |
| `flag` | write | Flag a KU as stale, incorrect, superseded, dangerous or duplicate |
| `reflect` | read | Extract candidate KUs from a session summary for review before `propose` |
| `status` | read | Store health: counts, confidence, staleness (`debug=True` adds schema detail) |

Prompts: `recall-before-task`, `capture-learning`. Resources: `stolperfalle://vocabulary`, `stolperfalle://status`, `cq://extensions`, `cq://schema/knowledge-unit`.

The server also exposes `POST /hook/query` and `POST /hook/reflect` for the Claude Code hooks (bearer auth, same key as MCP).

## Configuration

All server settings are environment variables read by `src/stolperfalle/config.py`; `.env.example` lists them with comments.

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT` | `stdio` | `stdio` or `http` |
| `HOST` | `127.0.0.1` | HTTP bind address (`0.0.0.0` in the container) |
| `PORT` | `8716` | HTTP port |
| `MCP_STOLPERFALLE_API_KEY` | (generated) | Bearer key for HTTP clients and hooks. If empty, an ephemeral `stmcp_` key is generated at startup and not logged, so set a stable one |
| `MCP_STOLPERFALLE_PUBLIC_URL` | `http://HOST:PORT` | Public base URL, used for OAuth metadata |
| `CF_ACCESS_TEAM` | (empty) | Cloudflare Access team name, for the optional OIDC login |
| `CF_ACCESS_CLIENT_ID` | (empty) | Cloudflare Access for SaaS client id |
| `CF_ACCESS_CLIENT_SECRET` | (empty) | Client secret; when empty, OIDC is off and only bearer auth is used |
| `CQ_LOCAL_DB_PATH` | `/data/stolperstein.db` | SQLite database path |
| `MCP_STOLPERFALLE_SIGNING_KEY` | (empty) | Base64 of the 32-byte Ed25519 key; overrides the key file (see below) |
| `CQ_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local sentence-transformers model |
| `CQ_EMBEDDING_API_URL` | (empty) | Use an embeddings API instead of the local model |
| `CQ_LLM_API_URL` | (empty) | OpenAI-compatible endpoint for `reflect`; empty means heuristic fallback |
| `CQ_LLM_API_KEY` | (empty) | API key for that endpoint |
| `CQ_LLM_MODEL` | `gpt-4o-mini` | Model name for `reflect` |
| `TRUSTED_ORGS` | `*` | Comma-separated org DIDs visible to `query`; `*` trusts all |
| `STOLPERFALLE_EMERGENT_DISABLED` | `false` | Turn off emergent-signal detection |
| `EMERGENT_DETECT_EVERY_N` | `10` | Run detection every Nth query miss (`0` disables) |
| `EMERGENT_MIN_MISSES` | `5` | Minimum misses per cluster |
| `EMERGENT_MIN_SESSIONS` | `2` | Minimum distinct hour buckets per cluster |
| `TYPESAFE_API_KEY` | (empty) | Optional relevance gate for `/hook/query`; unset returns ungated results |

The plugin's hook handlers read their own variables on the client side (`MCP_STOLPERFALLE_PUBLIC_URL`, `MCP_STOLPERFALLE_API_KEY`, `STOLPERFALLE_HOOKS_DISABLED`, `STOLPERFALLE_HOOK_COOLDOWN_S`, `STOLPERFALLE_REFLECT_THRESHOLD`, `STOLPERFALLE_ERROR_PATTERNS`, `STOLPERFALLE_REFLECT_VIA_HOOK`, `STOLPERFALLE_HOOKS_DEBUG`). See `plugin/stolperfalle/SKILL.md` and [USING.md](USING.md).

## Authentication

stdio has no auth layer. With `TRANSPORT=http` the server accepts two methods at once:

- **Bearer token**: `Authorization: Bearer <MCP_STOLPERFALLE_API_KEY>`, compared in constant time. Used by direct clients, automation and the hooks.
- **OIDC login (optional)**: when the `CF_ACCESS_*` variables are set, the server proxies an OAuth flow through a Cloudflare Access for SaaS application, for browser-based MCP clients.

Put TLS in front of the server (reverse proxy or tunnel) before exposing it beyond localhost, and keep keys out of version control.

## Relationship with upstream (mozilla-ai/cq)

Stolperfalle is not a fork — it's an independent, cq-compatible local node that stays strictly valid on the wire and proposes anything it needs beyond that back upstream rather than diverging quietly.

**History so far:** filed [discussion #286](https://github.com/mozilla-ai/cq/discussions/286) proposing a set of local extensions (severity, kind, status, org ownership, etc.) → scoped as [issue #406](https://github.com/mozilla-ai/cq/issues/406), proposing a generic `extensions` slot instead of relaxing `additionalProperties` → **merged upstream as [PR #453](https://github.com/mozilla-ai/cq/pull/453) on 2026-06-23**. That slot is generic (it accepts any `namespace:key`), so it's how Stolperfalle carries its own fields under `stolperfalle:*` keys (see [`docs/cq-extensions.md`](docs/cq-extensions.md)) without ever breaking strict conformance.

**Current standing on individual fields:** `severity`, `contributing_orgs`, and `kind` were declined for core promotion (upstream's call: importance should emerge from usage, not self-declaration) — they stay local-only, riding the slot. `context.environment` and `proposer_did` attribution are deferred, open threads. `status`, `staleness_policy`, `related[]`, `owner_org`, and `emergent` were never proposed for core — they're Stolperfalle-specific by design.

**Open loop:** an adopter comment for #286, announcing production slot emission, is drafted (`openspec/changes/archive/2026-07-07-adopt-cq-extensions-slot/upstream-comment-draft.md`) but not yet posted — held for review.

## Migration workflow

The server runs pending migrations automatically on boot. For operators:

```bash
uv run mcp-stolperfalle migrate           # apply pending migrations + exit
uv run mcp-stolperfalle prune-backups     # list pre-migration .bak files (dry run)
uv run mcp-stolperfalle prune-backups --confirm
uv run mcp-stolperfalle detect-emergent   # run emergent-signal aggregation manually
```

### Deploying a breaking schema change

1. **Pre-deploy**: note the current production commit. Snapshot the `stolperstein-data` Docker volume to `stolperstein-data-pre-vN`.
2. **Deploy**: merge to `main`; the deployment rebuilds the container from source. On first boot, the migration runner copies `stolperstein.db` to `stolperstein.db.bak-pre-v<N>` before each breaking migration, applies the chain inside per-migration transactions, and stamps `schema_version`.
3. **Verify**: `mcp-stolperfalle status --debug` must show the expected `schema_version`, no `proposer_did IS NULL`, no `owner_org IS NULL`, and KU totals matching pre-migration.
4. **48h later**: run `mcp-stolperfalle prune-backups --confirm` to remove the `.bak-pre-v*` files once you're confident no rollback is needed.

### Rollback

There are no published images: the stack builds from source (`build: .`, no registry), so rollback is git- and volume-based:

- **Code rollback**: `git revert <bad-sha>` and open a PR (`main` is branch-protected; CI must pass), or point the deployment at the last-good commit SHA for an immediate targeted redeploy. Budget ~5 min for the rebuild (it re-installs the CPU torch wheel and re-downloads the embedding model).
- **DB rollback** (a breaking migration went wrong): stop the container, copy `stolperstein.db.bak-pre-v<N>` over `stolperstein.db`, then deploy the code SHA that matches that schema. Migrations run on boot, so *old code on a newer-migrated DB* is exactly what the `.bak` guards against — and `.bak-pre-v<N>` only exists for breaking migrations.
- If `/data/stolperstein.key` was lost, the install generates a new keypair on next boot (KUs remain intact, but subsequent proposals get a new DID — the provenance chain breaks at the rollback point, recoverable but visible). Escrow the key (see below) to avoid this.

## Private signing key (`/data/stolperstein.key`)

The install's Ed25519 private key is stored **outside** the SQLite DB for good reason — a DB leak does not compromise signing capability. Treat `/data/stolperstein.key` as sensitive:

- **A whole-volume snapshot of `stolperstein-data` includes the key** — you can't exclude one file from a block/volume snapshot, so snapshot access = signing access; scope who can read those snapshots accordingly. For DB-only backups, copy `stolperstein.db` + `*.bak-pre-v*` at the file level instead.
- **Escrow it.** There is otherwise exactly one copy — a volume loss permanently rotates the install DID. Base64 the key into your password manager or secret store so it's recoverable: `docker exec <container> base64 -w0 /data/stolperstein.key`, then recover by setting `MCP_STOLPERFALLE_SIGNING_KEY` in the deployment environment.
- Don't include it in `docker cp` / dump operations.
- To inject the key via env (recovery, CI, or ephemeral deployments), set `MCP_STOLPERFALLE_SIGNING_KEY` to the base64-encoded 32-byte key. The env var takes priority over the file.

## Claude Code plugin

`plugin/stolperfalle/` ships a real hook manifest (`hooks.json`) with three hooks: `UserPromptSubmit`, `PostToolUse(Bash)`, `Stop`. They fire on **structured** error signals only (exception class names, tracebacks, non-zero exit codes, HTTP status strings, explicit `fatal:`/`panic:`/`Error:` prefixes) — not bare conversational English. 30s cooldown + 5min per-KU dedupe via `fcntl.flock`-guarded state file at `$FASTMCP_HOME/hooks-state.json`. See `plugin/stolperfalle/SKILL.md` for tool usage and the `STOLPERFALLE_HOOKS_DISABLED` escape hatch.

Hooks require the MCP server reachable over HTTP; set `MCP_STOLPERFALLE_PUBLIC_URL` + `MCP_STOLPERFALLE_API_KEY`. Without those, hook handlers exit 0 silently (no-op). Setup and day-to-day use are in [USING.md](USING.md).

## Telemetry

A vendored `usage.py` middleware writes one JSON line per tool call to stderr with the server, tool, duration, outcome and protocol. Tool arguments are never logged. Tool failures raise `ToolError`, so clients receive a proper MCP error.

## Development

```bash
uv sync
uv run ruff check src tests plugin
uv run mypy src
uv run pytest
```

Tests force `TRANSPORT=stdio`, use a fixed test signing key and no-op embeddings, so they need no model download. `main` is branch-protected: changes land through a pull request that must pass two checks, `test` (`.github/workflows/ci.yml`: ruff, mypy, pytest) and `security` (`.github/workflows/security.yml`: `pip-audit` against the locked dependencies).

## Releases

Releases are tag-only: a release is a pushed `v*` tag and there are no version-bump commits. This repo has no release workflow and no tags yet; production tracks `main` and rebuilds from source on each merge.

## Support

If this server saves you time, you can [buy me a coffee](https://buymeacoffee.com/caseyberlin).

## License

MIT, see [LICENSE](LICENSE).

