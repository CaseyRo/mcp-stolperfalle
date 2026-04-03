---
name: git-caddy stack operational details
description: Operational gotchas for working with the git-caddy stack on nebula-1
type: project
---

Files in `/home/caseyromkes/stacks/git-caddy/` are owned by `root` — all writes require `sudo`.

Git commits on nebula-1 require explicit identity: `git -c user.email='ops@cdit-works.de' -c user.name='Casey Romkes' commit`.

The `caddy validate` dry-run fails when env vars are empty (e.g. `GATUS_API_KEY` expands to empty string, breaking the header matcher). This is expected behavior for dry-runs without a loaded `.env` — it does not indicate a config bug. Use `docker compose config` to validate interpolation instead.

**Why:** root ownership is from how Komodo originally deployed the stack. Git identity is not set globally for the root user on nebula-1.

**How to apply:** Always use `sudo bash -s` heredoc pattern for multi-step edits. Always pass `-c user.email -c user.name` when committing as root.
