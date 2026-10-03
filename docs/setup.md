# Server setup

Current state of the agent server and how to rebuild it.

## Server

- Hetzner Cloud project `agent-server`, personal account (`alejoacelas@gmail.com`).
- Server `agent-server`: CX33 (4 x86 vCPU, 8 GB RAM, 80 GB disk), Nuremberg,
  Ubuntu 24.04, backups on. €11.99/month plus 20% for backups.
- Hetzner firewall `agent-server` allows inbound SSH (22/tcp) and Tailscale (41641/udp) only.
- SSH as `alejo` with the Mac's `~/.ssh/id_ed25519` key (Hetzner key `alejo-mac`).
  Root login and password login are disabled.

Why this size: in September 2026 Hetzner's ARM (CAX) plans and the larger CX plans
were sold out in every location, and the June 2026 price rise made the CPX plans
2.4–2.75x more expensive. The CX33 was the only in-stock plan at the cost-optimised
price. Resize in place within the CX family (`hcloud server change-type`) when a
larger one is back in stock; keep the disk size to stay able to downgrade.
Check real availability with the `locations[].available` field of
`GET /v1/server_types`; the datacenter listing is deprecated and wrong.

## Secrets

| Variable | Where it lives | Used for |
|---|---|---|
| `HCLOUD_TOKEN` | 1Password `my.1password.com` › Personal › `Hetzner agent-server` › `credential` | `hcloud` on the Mac |
| `OP_SERVICE_ACCOUNT_TOKEN` | 1Password `my.1password.com` › Personal › `1Password service account agent-server` › `credential` | `op` on the server |

Rebuild the Mac's `.env` with `op inject --account my.1password.com -i .env.tpl -o .env`.
On the server the service-account token is in `~/.config/agent-server/op.env`
(mode 600). It can read only the 1Password vault `server-agents`; copy an item
into that vault to make it available to agents.

The existing server vault was renamed from `agent-server`; its token remains valid.
The Mac has a separate read-only service account for `mac-agents`, also in the
personal 1Password account.

Use `~/.local/bin/op-agent` on the server or `~/best/dotfiles/bin/op-agent` on the
Mac. It loads the machine’s service-account token and forwards arguments to `op`.
For example, `op-agent run --env-file .env.tpl -- your-command` injects references
to that machine’s agent vault without approval prompts. Ordinary `op` on the Mac
retains its interactive authentication for other vaults.

The Mac token is stored in `~/.config/mac-agents/.env` (mode 600, directory 700).
Rebuild it from `my.1password.com` › `Personal` ›
`1Password service account mac-agents` › `credential`, assigning the value to
`OP_SERVICE_ACCOUNT_TOKEN`. Keep both bootstrap tokens outside the agent vaults.
The helper source is `~/best/dotfiles/bin/op-agent`; copy it to the server’s
`~/.local/bin/op-agent` when rebuilding.

## Rebuild

1. `hcloud server create --name agent-server --type cx33 --image ubuntu-24.04 --location nbg1 --ssh-key alejo-mac --firewall agent-server --user-data-from-file <cloud-init with key filled in>`,
   using `server/cloud-init.yaml` with `SSH_KEY_PLACEHOLDER` replaced by the public key.
2. `hcloud server enable-backup agent-server`.
3. `ssh alejo@<ip> 'bash -s' < server/bootstrap.sh` installs Node, gh, Go, uv,
   1Password CLI, Tailscale, Claude Code, Codex, and Orca, and adds 8 GB swap.
4. Put the service-account token in `~/.config/agent-server/op.env`.
5. Sign-ins that need Alejandro: Tailscale, Claude, Codex, and pairing Orca (below).

## Remaining steps

- [x] Tailscale on the server and the Mac. Public SSH is closed; connect with `ssh agent-server` over Tailscale.
- [x] `orca-ide serve` under systemd (`server/orca.service`), paired to the Mac as Orca environment `agent-server`.
- [x] Claude and Codex signed in with their own logins (`~/.claude`, `~/.codex`), independent of Orca.
  Sign in again with `claude` → `/login` and `codex login --device-auth` (enable device-code login in ChatGPT security settings first).
- [ ] Val Town endpoint for webhooks; server pulls jobs from it.
- [ ] whatsapp-mcp bridge as its own user, sending disabled.

## Codex launches in Orca

The server's Orca Codex launch arguments are
`--dangerously-bypass-approvals-and-sandbox`, allowing Codex's shared daemon.
The Mac client's Settings → Agents → “Run each Codex terminal on its own server”
is off. Launch arguments supplied by a client can override the server defaults.

The server setting was applied through Orca's runtime `settings.update` method
(`agentDefaultArgs.codex`) and verified through `settings.get` and the saved
`~/.config/orca/profiles/local-default/orca-data.json`. Preserve the other agents'
arguments when updating the map. New defaults apply to new launches; an existing
session or a restored launch may retain its original arguments. For a manually
started session, run `codex --dangerously-bypass-approvals-and-sandbox`.

## Search prototype

[Find](http://agent-server/) searches 241,787 Simple English Wikipedia articles
stored on this server (269 MB text, 815 MB SQLite index). The 2023-11-01 snapshot
is public; no personal or employer corpus is imported.

`search.service` is an enabled user service for `alejo`, with lingering enabled
so it survives logout and starts at boot. It runs from
`~/.local/share/agent-server-search/` and listens on `127.0.0.1:8765`.
Tailscale Serve proxies tailnet HTTP port 80 to it; no public access or Funnel.
See [rebuild steps and controls](../search/README.md).

On 2026-10-03, 18 representative requests from the Mac had a 43 ms median total
request time and 4 ms median server search time. The slowest request was 477 ms;
server search stayed below 10 ms in that sample. A one-letter query took about
298 ms including 188 ms searching. These are small-sample observations, not a
latency guarantee; the UI displays timing for every query.
