# Brief for the setup walkthrough

Walk Alejandro through setting up a Hetzner Cloud server, one step at a time.
He does the steps that need him (account, payment, phone scans, browser sign-ins);
you run everything you can yourself, then verify each step before moving on.

Goal: an always-on box that hosts many parallel AI workers (Claude Code and Codex
in Orca worktrees), a webhook receiver, and a read-only WhatsApp bridge. Price is
not a concern; size for lots of concurrent agents and builds.

Cover, in order:

1. Choose the server: dedicated vCPU plan with plenty of RAM and disk, location near
   Alejandro, Ubuntu LTS. Explain the choice (x86 vs ARM, cloud vs dedicated/auction).
2. Create it with `hcloud` if possible (token from 1Password, personal account), SSH key only.
3. Harden: non-root user, firewall allowing only SSH and HTTPS, unattended upgrades, backups on.
4. Tailscale: join the tailnet, then restrict SSH to Tailscale.
5. Tooling: git, gh, Node, Go, Python/uv, 1Password CLI with a service account scoped to a
   dedicated `server` vault, Claude Code, Codex.
6. Orca: install, run `orca serve` under systemd, pair the Mac's Orca with `orca environment add`,
   sign in agents with `orca account add` (claude, then `--agent codex`).
7. Caddy in front of a placeholder webhook endpoint on a subdomain.
8. whatsapp-mcp bridge under systemd as its own user, sending disabled.

Record every step, command and 1Password reference in `docs/setup.md` as you go,
commit and push after each step. Never write secrets into the repo. Read `AGENTS.md` first.
Ask Alejandro before anything that costs money or is hard to undo.
