# Agent server

Explores running a Hetzner server where AI workers (Claude Code, Codex) take
delegated tasks and finish them without checking back with Alejandro.

The server hosts:

- Orca's headless runtime (`orca serve`), paired to the Mac over Tailscale, for worktrees and agents.
- A worker that pulls triggers from a Val Town endpoint, for jobs like "call ended → process transcript".
- The WhatsApp bridge from [whatsapp-mcp](https://github.com/lharries/whatsapp-mcp), read-only.

Use the personal identity (`alejoacelas@gmail.com`) for cloud writes. Keep no
80k material on this server. Record secrets only as 1Password references
(account, vault, item, field). Never commit tokens, IPs of private services, or
WhatsApp data.

- `docs/setup.md` — current server state, secrets locations, and rebuild steps.
- `docs/delegation.md` — plan for letting delegated tasks run unattended.
