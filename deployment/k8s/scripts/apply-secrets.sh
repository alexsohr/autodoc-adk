#!/usr/bin/env bash
# =============================================================================
# apply-secrets.sh — Load API key secrets from .env into K8s
# =============================================================================
# Reads API keys from the project .env file and creates/updates the
# autodoc-api-keys K8s Secret. The .env file is gitignored so secret
# values never enter version control.
#
# Usage:
#   ./deployment/k8s/scripts/apply-secrets.sh
#   ENV_FILE=/path/to/.env ./deployment/k8s/scripts/apply-secrets.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../../.."
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
NAMESPACE="autodoc"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: .env file not found at $ENV_FILE"
  echo "Copy .env.example to .env and fill in your API keys."
  exit 1
fi

echo "=== AutoDoc ADK — Apply Secrets ==="
echo "Reading from: $ENV_FILE"
echo "Namespace: $NAMESPACE"
echo

# Helper: read a value from .env (handles quotes)
get_env() {
  local key="$1"
  local val
  val=$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2-)
  # Strip surrounding quotes
  val="${val%\"}"
  val="${val#\"}"
  val="${val%\'}"
  val="${val#\'}"
  echo "$val"
}

# Build --from-literal args for API keys
LITERALS=()

GOOGLE_API_KEY=$(get_env GOOGLE_API_KEY)
if [ -n "$GOOGLE_API_KEY" ]; then
  LITERALS+=(--from-literal=GOOGLE_API_KEY="$GOOGLE_API_KEY")
  echo "  GOOGLE_API_KEY: set"
else
  echo "  GOOGLE_API_KEY: not found in .env (skipped)"
fi

OPENAI_API_KEY=$(get_env OPENAI_API_KEY)
if [ -n "$OPENAI_API_KEY" ]; then
  LITERALS+=(--from-literal=OPENAI_API_KEY="$OPENAI_API_KEY")
  echo "  OPENAI_API_KEY: set"
else
  echo "  OPENAI_API_KEY: not found in .env (skipped)"
fi

GITHUB_DEFAULT_TOKEN=$(get_env GITHUB_DEFAULT_TOKEN)
if [ -n "$GITHUB_DEFAULT_TOKEN" ]; then
  LITERALS+=(--from-literal=GITHUB_DEFAULT_TOKEN="$GITHUB_DEFAULT_TOKEN")
  echo "  GITHUB_DEFAULT_TOKEN: set"
else
  LITERALS+=(--from-literal=GITHUB_DEFAULT_TOKEN="")
  echo "  GITHUB_DEFAULT_TOKEN: not found in .env (empty)"
fi

echo

if [ ${#LITERALS[@]} -eq 0 ]; then
  echo "ERROR: No API keys found in .env"
  exit 1
fi

# Create or replace the secret (dry-run + apply pattern avoids "already exists" errors)
kubectl create secret generic autodoc-api-keys \
  -n "$NAMESPACE" \
  "${LITERALS[@]}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo
echo "Secret autodoc-api-keys updated in namespace $NAMESPACE."
echo "Restart pods to pick up changes:"
echo "  kubectl -n $NAMESPACE rollout restart deployment/autodoc-api"
