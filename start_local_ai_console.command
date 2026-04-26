#!/bin/zsh
set -euo pipefail

# Finder-friendly launcher for the local review-gated research AI console.
# It starts only a local status/operations page and does not auto-finalize outputs.

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

HOST="${RESEARCH_AI_CONSOLE_HOST:-127.0.0.1}"
PORT="${RESEARCH_AI_CONSOLE_PORT:-8765}"
NO_BROWSER="${RESEARCH_AI_NO_BROWSER:-0}"
URL="http://${HOST}:${PORT}"
CONFIG_PATH="local_ai.config.json"

if [[ ! -f "$CONFIG_PATH" ]]; then
  CONFIG_PATH="configs/local_ai.example.json"
fi

export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/research_ai_pycache}"

if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi

echo "Local Research AI Console"
echo "Repository: $REPO_ROOT"
echo "Config: $CONFIG_PATH"
echo "URL: $URL"
echo ""
echo "Safety: local-only, review-gated, no auto-finalization."
echo "Press Ctrl+C in this terminal window to stop the console."
echo ""

if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $PORT is already in use. Opening the existing local page."
    if [[ "$NO_BROWSER" != "1" ]] && command -v open >/dev/null 2>&1; then
      open "$URL" >/dev/null 2>&1 || true
    fi
    exit 0
  fi
fi

if [[ "$NO_BROWSER" != "1" ]] && command -v open >/dev/null 2>&1; then
  (sleep 2; open "$URL" >/dev/null 2>&1 || true) &
fi

python3 -m src.research_systems_showcase.local_ai.cli \
  --config "$CONFIG_PATH" \
  console \
  --host "$HOST" \
  --port "$PORT"
