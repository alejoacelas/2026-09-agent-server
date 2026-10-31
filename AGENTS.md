# Agent server

Explores running a Hetzner server where AI workers (Claude Code, Codex) take
delegated tasks and finish them without checking back with Alejandro.

The server hosts:

- A worker that pulls triggers from a Val Town endpoint, for jobs like "call ended → process transcript".
- The WhatsApp bridge from [whatsapp-mcp](https://github.com/lharries/whatsapp-mcp), read-only.

Use the personal identity (`alejoacelas@gmail.com`) for cloud writes. Record secrets only as 1Password references
(account, vault, item, field). Never commit tokens, IPs of private services, or
WhatsApp data.

Run agent work as the `agent` user (`sudo -iu agent`), never as `alejo`. It
reaches Alejo's GitHub and Google accounts through the credential broker and
never holds the tokens; see [Agent user](docs/setup.md#agent-user).

- `docs/setup.md` — current server state, secrets locations, and rebuild steps.
- `docs/delegation.md` — plan for letting delegated tasks run unattended.
- `docs/desk-pipeline.md` — spec for recording Alejo's conversations into desk and preparing work for his review.

The server’s `OP_SERVICE_ACCOUNT_TOKEN` is in personal 1Password account
`my.1password.com`, vault `Personal`, item `1Password service account agent-server`,
field `credential`. It grants read-only access to `server-agents`. Use
`~/.local/bin/op-agent` for unattended retrieval and injection; see `docs/setup.md`.
