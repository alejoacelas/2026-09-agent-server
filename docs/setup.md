# Server setup

## 1. Server choice — 2026-09-26

Alejandro chose 32 GB RAM and 256 GB SSD after comparing costs. Target Hetzner
CX53: shared x86 vCPUs, 32 GB RAM, and 320 GB SSD (the plan exceeds the requested
disk capacity). Prefer Nuremberg, Germany, with Ubuntu 24.04 LTS. Availability
and the final quote still need verification through the account.

The published Europe price is €29.49/month before VAT, IPv4, and backups.
With backups at 20%, this is approximately €35.39/month before VAT and IPv4.
Sources: [Hetzner pricing](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/),
[plan specifications](https://www.hetzner.com/cloud/cost-optimized/), and
[backup billing](https://docs.hetzner.com/cloud/billing/faq/).
The public plan page reports unavailability; do not treat the target as reserved.

Shared CPU is acceptable initially. Measure contention, memory pressure, disk
space, and task failures before increasing capacity. Model subscriptions and
API usage are separate costs.

## 2. Provisioning — awaiting personal account access

No server has been created. Access checks performed from this repository:

```sh
git status --short --branch
hcloud context list
op account list --format=json
op item list --account my.1password.com --format json
gh auth status
```

The repository was clean; GitHub authentication is available as `alejoacelas`.
Both `hcloud` and `op` are installed. Personal 1Password is accessible, but no
item matching Hetzner was found (only matching metadata was printed). There is
no configured hcloud context. The personal cloud browser redirected Hetzner
Console to its login page; that browser session was stopped.

Requested prerequisite: sign in or register at [Hetzner Console](https://console.hetzner.com/)
using `alejoacelas@gmail.com`, complete any account verification/payment setup,
and create an `agent-server` project with a Read & Write API token. Save it in
personal 1Password as `Hetzner agent-server`, field `credential`, and provide the
vault name. This is a requested location, not a verified existing secret reference.

Once accessible, verify plan availability, price including backups and tax, and
the Ubuntu image. Provision with an SSH key and enable backups. Keep the API
token in an ignored `.env`, loaded on demand with `op`; record the confirmed
1Password reference in README.md. Never commit credentials or private service IPs.
