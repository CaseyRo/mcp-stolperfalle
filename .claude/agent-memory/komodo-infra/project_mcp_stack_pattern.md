---
name: MCP Stack Deployment Pattern
description: How MCP servers are deployed on ubuntu-smurf-mirror via Komodo git-backed stacks with Caddy ingress on nebula-1
type: project
---

Established pattern for MCP servers on the CDIT fleet (as of 2026-03-27):

**Deployment target**: ubuntu-smurf-mirror (192.168.1.46 / Tailscale 100.118.241.89)

**Stack type**: Komodo git-backed stack (`repo =` in komodo.toml), builds from Dockerfile in the repo.

**Port allocation** (known):
- 8001: mcp-lexoffice
- 8002: mcp-watermelon
- 8006: mcp-siyuan
- 8009: mcp-things (runs on cc1, not ubuntu-smurf-mirror)
- 3336: mcp-instaloader
- 8128: mcp-ytdlp
- 8716: mcp-stolperstein (planned — port is free as of 2026-03-27)

**Networking**: Most MCP stacks use their own isolated `<stack>_default` bridge network. mcp-siyuan is the exception — it joins `siyuan_default` (external) to reach the siyuan container directly. Standalone MCPs (instaloader, ytdlp) use no external network.

**komodo.toml pattern** (from git-mcp-siyuan):
```toml
[[stack]]
name = "git-mcp-<name>"
description = "..."
deploy = true
tags = ["mcp"]

[stack.config]
server_id = "ubuntu-smurf-mirror"
git_provider = "github.com"
repo = "CaseyRo/mcp-<name>"
branch = "main"
environment = """
MY_SECRET = [[KOMODO_VAR_NAME]]
MY_PUBLIC_VALUE = https://mcp-<name>.cdit-dev.de
KEYCLOAK_ISSUER = https://auth.cdit-works.de/realms/cdit-mcp
KEYCLOAK_AUDIENCE = mcp-<name>
"""
```

**compose.yaml pattern** (from git-mcp-siyuan):
```yaml
services:
  mcp-<name>:
    build: .
    restart: unless-stopped
    ports:
      - "<host_port>:8000"
    environment:
      - TRANSPORT=http
      - HOST=0.0.0.0
      - MY_API_KEY=${MY_API_KEY:-}
      - MCP_<NAME>_PUBLIC_URL=${MCP_<NAME>_PUBLIC_URL:-https://mcp-<name>.cdit-dev.de}
      - KEYCLOAK_ISSUER=${KEYCLOAK_ISSUER:-https://auth.cdit-works.de/realms/cdit-mcp}
      - KEYCLOAK_AUDIENCE=${KEYCLOAK_AUDIENCE:-mcp-<name>}
```

**API key secret naming convention** (from mcp-siyuan): `MCP_<NAME>_API_KEY`, e.g. `MCP_SIYUAN_API_KEY`. Value format seen: `smcp_-2CFO-4lzQfv4VSwYgZASQF90UehiXacUR2w3iuYLMY` (smcp_ prefix).

**Caddy ingress pattern** (nebula-1, /home/caseyromkes/stacks/git-caddy/Caddyfile):
- Virtual host: `mcp-<name>.cdit-dev.de`
- Env var in Caddy .env: `MCP_<NAME>_HOST=100.118.241.89` (Tailscale IP of host server)
- Two handles: `/.well-known/oauth-protected-resource` (rewritten to /mcp path) and catch-all `handle`
- Both proxy to `{$MCP_<NAME>_HOST}:<host_port>` with `flush_interval -1`
- No IP restrictions — auth enforced by MCP server itself (Keycloak JWT)

**Why:** All MCP servers use Keycloak at `https://auth.cdit-works.de/realms/cdit-mcp` for JWT auth. Caddy just TLS-terminates and proxies; no Caddy-level auth layer needed for MCPs.

**How to apply:** Use this pattern exactly when deploying mcp-stolperstein or any future MCP stack.
