#!/usr/bin/env bash
# Installs the agent server's tooling on Ubuntu 24.04. Safe to re-run.
# Run as the sudo user created by cloud-init: ssh alejo@<host> 'bash -s' < server/bootstrap.sh
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
arch=$(dpkg --print-architecture)

# Swap gives headroom when several agents run builds at once.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 8G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# Apt repositories: Node, GitHub CLI, 1Password CLI, Tailscale.
sudo install -d -m 0755 /etc/apt/keyrings
[ -f /etc/apt/sources.list.d/nodesource.list ] || curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash - >/dev/null
if [ ! -f /etc/apt/sources.list.d/github-cli.list ]; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli.gpg >/dev/null
  echo "deb [arch=$arch signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
fi
if [ ! -f /etc/apt/sources.list.d/1password.list ]; then
  curl -fsSL https://downloads.1password.com/linux/keys/1password.asc | sudo gpg --dearmor --yes -o /etc/apt/keyrings/1password.gpg
  echo "deb [arch=$arch signed-by=/etc/apt/keyrings/1password.gpg] https://downloads.1password.com/linux/debian/$arch stable main" | sudo tee /etc/apt/sources.list.d/1password.list >/dev/null
  sudo mkdir -p /etc/debsig/policies/AC2D62742012EA22 /usr/share/debsig/keyrings/AC2D62742012EA22
  curl -fsSL https://downloads.1password.com/linux/debian/debsig/1password.pol | sudo tee /etc/debsig/policies/AC2D62742012EA22/1password.pol >/dev/null
  curl -fsSL https://downloads.1password.com/linux/keys/1password.asc | sudo gpg --dearmor --yes -o /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg
fi
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo apt-get update -qq
sudo apt-get install -y -qq nodejs gh 1password-cli golang-go python3-venv ripgrep unzip >/dev/null
# Orca is an Electron app; its package doesn't declare these runtime libraries.
sudo apt-get install -y -qq libasound2t64 libgtk-3-0t64 libnss3 libgbm1 libxss1 libxshmfence1 libdrm2 libnotify4 libsecret-1-0 xvfb >/dev/null

# uv for Python projects.
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null

# Agents.
command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash >/dev/null
command -v codex >/dev/null || sudo npm install -g @openai/codex >/dev/null

# Orca: the Linux package ships the CLI as orca-ide.
if ! command -v orca-ide >/dev/null; then
  url=$(curl -fsSL https://api.github.com/repos/stablyai/orca/releases/latest | grep -o "https://[^\"]*orca-ide_[^\"]*_$arch.deb" | head -1)
  curl -fsSL -o /tmp/orca.deb "$url" && sudo apt-get install -y -qq /tmp/orca.deb >/dev/null && rm /tmp/orca.deb
fi

sudo dpkg-reconfigure -f noninteractive unattended-upgrades
grep -q '.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"
go version
for c in node gh op uv tailscale claude codex orca-ide; do printf '%-10s %s\n' "$c" "$($c --version 2>/dev/null | head -1 || echo MISSING)"; done
