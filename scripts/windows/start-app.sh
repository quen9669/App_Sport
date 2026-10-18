#!/usr/bin/env bash
# Starts App Sport in production mode (`make prod`), for the Windows Startup
# shortcut opened at log-on (`make autostart`). Runs inside WSL (Ubuntu). The output goes
# to backend/data/prod.log (outside git, like the database).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"
log="backend/data/prod.log"
mkdir -p backend/data

# A Windows task does not open an interactive shell: load the tools by hand.
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" # uv
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" # node, if installed with nvm

# Already running (or `make dev` is open)? Then there is nothing to do.
if (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null; then
  echo "$(date -Is) port 8000 already in use, not starting" >>"$log"
  exit 0
fi

echo "$(date -Is) starting App Sport (make prod)" >>"$log"
exec make prod >>"$log" 2>&1
