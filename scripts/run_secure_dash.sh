#!/usr/bin/env bash
set -euo pipefail
export NVM_DIR="${NVM_DIR:-$HOME/.config/nvm}"
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
cd /home/ai_lab/workspace/ai_dhal/secure_dash
exec npm run dev -- --host 127.0.0.1 --port 5173
