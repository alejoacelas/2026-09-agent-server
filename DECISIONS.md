# Decisions

## Core decisions

### Agent isolation

- [Agent work runs as the `agent` user; credentials stay with a broker running as `alejo`.](#agent-user)

### Access

- [SSH uses OpenSSH keys over Tailscale, the same as between the Macs; Tailscale SSH is off.](#ssh-access)

### Initial capacity and cost

- [Start with 32 GB RAM and at least 256 GB SSD; shared CPU is acceptable.](#initial-server)

## Details

### Initial server

Target CX53 (32 GB RAM, 320 GB SSD) in Germany, subject to availability, within
the roughly €50/month budget discussed. The prior dedicated-vCPU recommendation
cost too much for an unmeasured workload. Increase capacity when observed memory,
storage, or CPU contention delays useful work; ask before a costlier substitution.
The selected starting point is recorded in [setup.md](docs/setup.md) and
commit [8c850a3](https://github.com/alejoacelas/2026-09-agent-server/commit/8c850a3).

### Agent user

Comment-driven mail runs and errands were given full access (shell, all
connectors, the web, Alejo's Chrome) on 2026-10-24. As `alejo` that would also
have exposed passwordless sudo, the 1Password service-account token, the GitHub
token, gog's refresh tokens for all three Google identities, a deploy key and
other services' environments. Agent sessions therefore run as `agent`, without
sudo or access to `/home/alejo`, and use Alejo's GitHub and Google accounts
through [the broker](server/agent-broker/broker.py), which performs actions
and adds secrets to requests but never returns them. Keep new credentials
behind the broker rather than in `agent`'s files. The Chrome relay and the
claude.ai connectors remain account-wide powers the broker doesn't cover.

### SSH access

The Macs reach each other with OpenSSH keys because the Tailscale Mac app cannot
serve Tailscale SSH. The server now matches, so one mechanism governs all three
machines. Tailscale SSH's check mode needs a browser re-login at least weekly,
which blocks unattended agents; `accept` mode would instead admit every tailnet
device. Revisit Tailscale SSH everywhere if the machine count grows enough that
per-machine key lists become a chore.

## Decision log

- 2026-10-03: Use Codex's shared daemon for new Orca sessions on the server and
  Mac, at Alejandro's request. Configuration: [a1f2590](https://github.com/alejoacelas/2026-09-agent-server/commit/a1f2590).

- 2026-09-26: Prioritize 32 GB RAM and at least 256 GB SSD over dedicated CPU
  capacity. Alejandro selected this size after reviewing the cost tradeoffs.

- 2026-10-03: Prototype search with a public Wikipedia snapshot stored and indexed
  on Hetzner, exposed only through Tailscale. This measures real remote-search
  latency without copying personal or employer material. Use title-first keyword
  search for the launcher interaction; measure corpus-specific needs before
  adding semantic search. Implementation: [27f7335](https://github.com/alejoacelas/2026-09-agent-server/commit/27f7335).

- 2026-10-04: Copy approved credentials into separate Mac and server agent vaults
  in personal 1Password, preserving originals and existing secret references. Keep
  work/advising items Mac-only and exclude 1Password account credentials, bootstrap
  tokens, identity/payment records, and the migration note from both agent vaults.
  Copies need explicit updates during rotation; see [setup](docs/setup.md) and
  [c4ea335](https://github.com/alejoacelas/2026-09-agent-server/commit/c4ea335).

- 2026-10-24: Agent work moved to the `agent` user, with a credential broker for
  `gh`, `gog` and git pushes, at Alejandro's request.

- 2026-10-26: Turn off Tailscale SSH and use OpenSSH keys over Tailscale, matching the
  Macs, so unattended agents on either Mac can reach the server.

- 2026-10-27: Every web page open on a tailnet device can send requests to tailnet
  services, so each service here refuses writes a browser marks as cross-site
  (`Sec-Fetch-Site`), and tailnet membership is never treated as authentication.
  The same review turned on `ufw` (tailnet only), automatic reboots for updates,
  broker copies of share files, and retired Orca.
