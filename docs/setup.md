# Server setup

Current state of the agent server and how to rebuild it.

## Server

- Hetzner Cloud project `agent-server`, personal account (`alejoacelas@gmail.com`).
- Server `agent-server`: CX33 (4 x86 vCPU, 8 GB RAM, 80 GB disk), Nuremberg,
  Ubuntu 24.04, backups on. €11.99/month plus 20% for backups.
- Hetzner firewall `agent-server` allows inbound Tailscale (41641/udp) only, so SSH
  is reachable only over Tailscale. `ufw` on the server does the same (allow
  `tailscale0` and 41641/udp), in case the Hetzner firewall is ever detached.
- Unattended upgrades also cover tailscale, gh, nodejs and 1password-cli, and
  reboot at 04:30 UTC when an update needs it (`/etc/apt/apt.conf.d/52agent-server`).
- SSH as `alejo` with OpenSSH key login. `~/.ssh/authorized_keys` holds both Macs'
  `~/.ssh/id_ed25519` keys (Hetzner key `alejo-mac` is the main Mac's). Root login
  and password login are disabled. Tailscale SSH is off (`tailscale set --ssh=false`).

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

Agent-vault items are copies of approved items in `Personal`, preserving existing
`op://Personal/...` references. Copies do not synchronize: when rotating a
credential, update the original and each approved agent-vault copy. Copied items
carry an `agent-copy-source/<original-item-id>` tag for matching, including when
two originals have the same title. Use item IDs in secret references for those
ambiguous titles. Keep inventories containing private item names off this repository.

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

## Agent user

Agent work on the server runs as the Unix user `agent`, not `alejo`: the mail
jobs and review page, and any Claude Code or Codex session started for
delegated work (`ssh agent-server`, then `sudo -iu agent`). It has no sudo and
can't read `/home/alejo` (mode 750), so it can't read Alejo's tokens: the
1Password service-account token, the GitHub token, gog's keyring, Claude's
login, or other services' environments. `agent` has its own Claude Code login
to the same claude.ai account (connectors and the Chrome relay come with it),
lingering enabled for its user services, and git commits as Alejandro Acelas.
Codex isn't signed in for `agent`.

The credential broker, [server/agent-broker](../server/agent-broker/broker.py),
runs as `alejo` (`agent-broker.service`, installed in
`~/.local/lib/agent-broker/`) and acts for `agent` without handing over
secrets:

- `gh` and `gog` in `agent`'s `~/.local/bin` are
  [client.py](../server/agent-broker/client.py), which sends the command over
  `/srv/agent-broker/broker.sock`. The broker runs it as `alejo` from an empty
  folder and refuses `auth`, `config`, extensions, SSH and GPG keys,
  `--access-token`, `--home`, and any file path outside `/srv/agent-share`
  (`alejo:agent`, mode 2770), the folder for files passed between them.
  Share files the command names are copied into a folder only `alejo` can
  open, and new or changed ones copied back, so `agent` can't swap a checked
  path for a symlink to Alejo's files before `gh` or `gog` opens it.
- An HTTP proxy on `127.0.0.1:8790` (only under that name, so a web page
  can't reach it by rebinding a domain) forwards `/<route>/...` and adds that
  route's secret ([routes.json](../server/agent-broker/routes.json)). `agent`'s
  git rewrites `https://github.com/` to `http://127.0.0.1:8790/github/`, so
  clones and pushes use Alejo's GitHub token without seeing it. Add a route
  with an `op://server-agents/...` reference to give agents an API key the
  same way, then restart the broker.

Deliberate exceptions: the plans and mood Telegram bots still run Claude as
`alejo`, because they edit files `alejo` owns. The plans bot has Bash, web
access and credential reads denied in its own settings. The mood bot runs Bash
in Claude Code's sandbox (bubblewrap), with communications connectors, their
credentials and their domains blocked; see `checkin/claude-settings.json` in
the mood repository. The sandbox needs `bubblewrap`, `socat` and the AppArmor
profile `/etc/apparmor.d/bwrap`, which lets `/usr/bin/bwrap` create user
namespaces under Ubuntu 24.04's restriction; `bootstrap.sh` installs all three.

## Rebuild

1. `hcloud server create --name agent-server --type cx33 --image ubuntu-24.04 --location nbg1 --ssh-key alejo-mac --firewall agent-server --user-data-from-file <cloud-init with key filled in>`,
   using `server/cloud-init.yaml` with `SSH_KEY_PLACEHOLDER` replaced by the public key.
2. `hcloud server enable-backup agent-server`.
3. `ssh alejo@<ip> 'bash -s' < server/bootstrap.sh` installs Node, gh, Go, uv,
   1Password CLI, Tailscale, Claude Code, Codex, and Orca, and adds 8 GB swap.
4. Put the service-account token in `~/.config/agent-server/op.env`.
5. Sign-ins that need Alejandro: Tailscale, Claude, Codex, and pairing Orca (below).
6. Agent user: `sudo useradd -m -s /bin/bash agent`, `sudo chmod 750 /home/agent`,
   `sudo usermod -aG agent alejo`, `sudo loginctl enable-linger agent`; install
   Claude Code as `agent` and sign in (`sudo -iu agent claude`, then `/login`).
   Create `/srv/agent-broker` (`alejo:agent`, 2750), `/srv/agent-broker/empty`
   (`alejo`, 555) and `/srv/agent-share` (`alejo:agent`, 2770); copy
   `server/agent-broker/` to `~/.local/lib/agent-broker/`, enable its service,
   install `client.py` as `agent`'s `~/.local/bin/gh` and `gog`, and set
   `agent`'s git `url.http://127.0.0.1:8790/github/.insteadOf https://github.com/`.

## Remaining steps

- [x] Tailscale on the server and the Mac. Public SSH is closed; connect with `ssh agent-server` over Tailscale.
- [x] `orca-ide serve` under systemd (`server/orca.service`). Disabled on 2026-10-27; Alejandro no longer uses Orca.
- [x] Claude and Codex signed in with their own logins (`~/.claude`, `~/.codex`), independent of Orca.
- [x] GitHub CLI signed in as `alejoacelas` (`gh auth login --web`, HTTPS, set up as git's credential helper);
  git commits as Alejandro Acelas <alejoacelas@gmail.com>.
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

## Google CLI (gog)

`gog` v0.35.0, the same version as the Mac, is in `~/.local/lib/gog/`. Run it through
the wrapper `~/.local/bin/gog`, which loads `~/.config/gogcli/keyring.env` (mode 600:
`GOG_KEYRING_BACKEND=file` and a random `GOG_KEYRING_PASSWORD`) because the server has
no system keychain. Encrypted tokens are in `~/.local/share/gogcli/keyring/`.

It holds the Mac's three accounts: `alejoacelas@gmail.com` and `alejo@impact-ops.org`
on the `default` OAuth client, `alejo@habere.org` on `habere`. They were copied from
the Mac on 2026-10-24 rather than signed in again: client files from
`~/Library/Application Support/gogcli/`, client secrets from the Keychain items
`gogcli` › `client/<client>/client-secret` (loaded with `gog --client <client> auth
credentials set`), and refresh tokens with `gog auth tokens export` and `import`.
Check with `gog auth doctor --check`. The habere account has no Gmail and no Drive
access on either machine.

## Mail digest

The mail digest page from
[gmail-sorting](/Users/alejo/best/projects/2026-10-24-gmail-sorting/AGENTS.md)
runs as `agent`'s user service `gmail-review.service` on `127.0.0.1:8771`,
with the mail jobs on `agent`'s timers. Tailscale Serve proxies
`https://agent-server.tail622085.ts.net/mail` to it (tailnet only). The
project's AGENTS.md covers deploys and data.

## Moderation Bot

`modbot.service`, a user service for `alejo`, runs the AI Uplift Slack
Moderation Bot from `~/work/slack-moderation-bot`. Deploys, logs and secrets are in
[slack-moderation-bot](/Users/alejo/best/projects/2026-10-31-slack-moderation-bot/AGENTS.md).
