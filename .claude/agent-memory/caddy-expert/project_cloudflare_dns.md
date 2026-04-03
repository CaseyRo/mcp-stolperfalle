---
name: Cloudflare DNS credentials not available
description: No Cloudflare API credentials are stored locally or on nebula-1; DNS changes must be done via dashboard
type: project
---

`flarectl` is installed at `/opt/homebrew/bin/flarectl` locally but has no `CF_API_TOKEN` or `CF_API_EMAIL`/`CF_API_KEY` configured in any shell profile or config file. No credentials on nebula-1 either.

DNS records for `*.cdit-dev.de` and `*.cdit-works.de` must be managed manually via the Cloudflare dashboard.

**Why:** Credentials were never stored in the environment; likely managed through a separate secrets system or 1Password.

**How to apply:** When a task requires a new DNS A record, complete all Caddy-side steps automatically, then clearly instruct the user to add the record manually. Include the exact values: hostname, type=A, value=89.167.22.69, proxy=OFF (DNS-only/grey cloud).
