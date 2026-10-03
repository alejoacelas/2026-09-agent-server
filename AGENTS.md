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

The server’s `OP_SERVICE_ACCOUNT_TOKEN` is in personal 1Password account
`my.1password.com`, vault `Personal`, item `1Password service account agent-server`,
field `credential`. It grants read-only access to `server-agents`. Use
`~/.local/bin/op-agent` for unattended retrieval and injection; see `docs/setup.md`.
