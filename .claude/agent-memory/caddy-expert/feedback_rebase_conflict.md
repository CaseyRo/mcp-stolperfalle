---
name: git-caddy concurrent commits require rebase workflow
description: The CDiT-dev/caddy repo has active concurrent pushes; always pull --rebase before pushing
type: feedback
---

The git-caddy repo (`CDiT-dev/caddy` on GitHub) receives concurrent commits from multiple sources. A `git push` will regularly be rejected with "fetch first" errors.

**Why:** Multiple team members and automated processes push to this repo. Discovered during mcp-stolperstein setup (2026-03-27) when a push was rejected and a compose.yml conflict had to be resolved manually.

**How to apply:** After committing on nebula-1, always run `git pull --rebase` before `git push`. If a conflict occurs in compose.yml's `environment:` section, the resolution is to include ALL env vars from both sides (keep the remote's additions AND add our new one). Use `GIT_EDITOR=true` to accept the default commit message during `rebase --continue` since there's no interactive terminal.
