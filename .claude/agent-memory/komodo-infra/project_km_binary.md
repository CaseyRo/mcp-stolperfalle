---
name: km binary location
description: The km CLI binary is not in PATH; it must be invoked with its full Cellar path
type: project
---

The `km` binary is not symlinked into PATH on this machine. Use the full path:

`/opt/homebrew/Cellar/km/2.1.1/bin/km`

Config is at `~/.config/komodo/komodo.cli.toml` and points to `http://100.114.39.108:9120` (werkstatt-1 Tailscale IP, Komodo core port 9120).

The public hostname `komodo.cdit-dev.de` resolves to Hetzner public IP (89.167.22.69) which is now unreachable from the outside — Caddy on nebula-1 serves it internally via Tailscale only. Direct access to werkstatt-1 via Tailscale bypasses this.

**Why:** Homebrew did not create the `/opt/homebrew/bin/km` symlink, possibly due to a name conflict or manual install.

**How to apply:** Always use the full Cellar path in bash commands. If the version upgrades, the path will change — check with `ls /opt/homebrew/Cellar/km/`.
