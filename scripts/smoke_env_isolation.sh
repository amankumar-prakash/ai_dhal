#!/usr/bin/env bash
# Smoke: compose documents DB→API and LLM→workers isolation
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="$ROOT/docker-compose.yml"

python3 - <<PY
from pathlib import Path
text = Path("$COMPOSE").read_text()
assert "api_service:" in text and "red_team_backend:" in text and "blue_team_backend:" in text
# Workers receive LLM vars
assert "OPENAI_API_KEY: \${OPENAI_API_KEY" in text
assert "LLM_MODEL: \${LLM_MODEL" in text
# Explicit comment that API does not get LLM
assert "do NOT pass OPENAI_API_KEY" in text
# Workers documented without DB
assert "No DATABASE_URL" in text
print("env isolation OK")
PY

echo "smoke_env_isolation passed"
