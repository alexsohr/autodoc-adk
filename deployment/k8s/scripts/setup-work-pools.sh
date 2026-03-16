#!/usr/bin/env bash
# =============================================================================
# setup-work-pools.sh — Create and configure Prefect work pools for AutoDoc ADK
# =============================================================================
# Creates orchestrator-pool and k8s-pool with concurrency limits and applies
# the base job templates.
#
# Usage:
#   # With port-forward (dev-k8s):
#   kubectl port-forward -n autodoc svc/prefect-api 4200:4200 &
#   ./deployment/k8s/scripts/setup-work-pools.sh
#
#   # Or specify the URL directly:
#   PREFECT_API_URL=http://localhost:4200/api ./deployment/k8s/scripts/setup-work-pools.sh
#
# Environment:
#   PREFECT_API_URL — Prefect API URL (default: http://localhost:4200/api)
#   PREFECT_CMD     — Prefect CLI command (default: auto-detects uv run prefect
#                     or bare prefect)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/../job-templates"
API_URL="${PREFECT_API_URL:-http://localhost:4200/api}"

# Auto-detect prefect command: prefer bare `prefect`, fall back to `uv run prefect`
if [ -z "${PREFECT_CMD:-}" ]; then
  if command -v prefect &>/dev/null; then
    PREFECT_CMD="prefect"
  elif command -v uv &>/dev/null; then
    PREFECT_CMD="uv run prefect"
  else
    echo "ERROR: Neither 'prefect' nor 'uv' found on PATH."
    exit 1
  fi
fi

# Export so all prefect subcommands use the remote API
export PREFECT_API_URL="$API_URL"

echo "=== AutoDoc ADK — Work Pool Setup ==="
echo "Prefect API: $API_URL"
echo "Prefect CLI: $PREFECT_CMD"
echo

# Wait for Prefect API to be reachable
echo "Waiting for Prefect API..."
for i in $(seq 1 30); do
  if curl -sf "${API_URL%/api}/api/health" >/dev/null 2>&1; then
    echo "  Prefect API is ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  ERROR: Prefect API not reachable at $API_URL after 30s."
    echo "  For dev-k8s, start a port-forward first:"
    echo "    kubectl port-forward -n autodoc svc/prefect-api 4200:4200"
    exit 1
  fi
  sleep 1
done
echo

# Create or update orchestrator-pool
echo "Creating orchestrator-pool (kubernetes, concurrency limit: 10)..."
if $PREFECT_CMD work-pool create orchestrator-pool --type kubernetes 2>/dev/null; then
  echo "  Created orchestrator-pool."
else
  echo "  orchestrator-pool already exists."
fi
$PREFECT_CMD work-pool set-concurrency-limit orchestrator-pool 10
echo "  Concurrency limit set to 10."

# Apply base job template
$PREFECT_CMD work-pool update orchestrator-pool \
  --base-job-template "$TEMPLATES_DIR/orchestrator-job-template.json" 2>/dev/null \
  && echo "  Base job template applied." \
  || echo "  Warning: could not apply base job template (may require manual setup)."
echo

# Create or update k8s-pool
echo "Creating k8s-pool (kubernetes, concurrency limit: 50)..."
if $PREFECT_CMD work-pool create k8s-pool --type kubernetes 2>/dev/null; then
  echo "  Created k8s-pool."
else
  echo "  k8s-pool already exists."
fi
$PREFECT_CMD work-pool set-concurrency-limit k8s-pool 50
echo "  Concurrency limit set to 50."

# Apply base job template
$PREFECT_CMD work-pool update k8s-pool \
  --base-job-template "$TEMPLATES_DIR/scope-job-template.json" 2>/dev/null \
  && echo "  Base job template applied." \
  || echo "  Warning: could not apply base job template (may require manual setup)."
echo

echo "=== Work pool setup complete ==="
echo
echo "Verify with:"
echo "  $PREFECT_CMD work-pool ls"
