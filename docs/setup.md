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
(mode 600). It can read only the 1Password vault `agent-server`; copy an item
into that vault to make it available to agents.

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
