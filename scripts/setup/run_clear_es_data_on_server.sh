#!/usr/bin/env bash
#
# Run this script ON THE SERVER (e.g. after SSH) to pull latest code and clear
# Elasticsearch data (keeps indices/mappings).
#
# Usage on server:
#   cd ~/Kaleidoscope/kaleidoscope-ai   # or your repo path
#   ./scripts/setup/run_clear_es_data_on_server.sh
#
# Requires: ELASTICSEARCH_PASSWORD set in environment or in .env in repo root.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

echo "=============================================="
echo "Pull latest and clear Elasticsearch data"
echo "=============================================="
echo "Repo root: $REPO_ROOT"
echo ""

echo "[1/2] Pulling latest from origin/main..."
git pull origin main
echo ""

echo "[2/2] Clearing Elasticsearch data (data only, indices kept)..."
if [ -f .env ]; then
  set -a
  source .env
  set +a
  echo "Loaded .env for ELASTICSEARCH_PASSWORD and ES_BASE_URL (if set)."
fi

if [ -z "${ELASTICSEARCH_PASSWORD}" ]; then
  echo "Error: ELASTICSEARCH_PASSWORD is not set. Set it in .env or:"
  echo "  export ELASTICSEARCH_PASSWORD='your_password'"
  exit 1
fi

export ES_BASE_URL="${ES_BASE_URL:-http://localhost:9200}"
chmod +x "$SCRIPT_DIR/clear_es_data.sh"
"$SCRIPT_DIR/clear_es_data.sh"

echo ""
echo "All done."
