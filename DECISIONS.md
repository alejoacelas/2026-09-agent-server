# Decisions

## Core decisions

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
