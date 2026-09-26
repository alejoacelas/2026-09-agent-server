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

- 2026-09-26: Prioritize 32 GB RAM and at least 256 GB SSD over dedicated CPU
  capacity. Alejandro selected this size after reviewing the cost tradeoffs.
