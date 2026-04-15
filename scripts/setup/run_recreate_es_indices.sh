#!/usr/bin/env bash
# Recreate all Kaleidoscope Elasticsearch indices from es_mappings/*.json
# Run on the same host as Elasticsearch (e.g. after ssh to the droplet).
#
# Requires: python3, pip (installs elasticsearch client if missing)
# Reads ELASTICSEARCH_PASSWORD from repo .env next to docker-compose.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $ROOT"
  exit 1
fi

ES_PASS="$(grep "^ELASTICSEARCH_PASSWORD=" .env | cut -d= -f2- | tr -d '\r')"
if [[ -z "${ES_PASS}" ]]; then
  echo "ERROR: ELASTICSEARCH_PASSWORD not set in .env"
  exit 1
fi

export ES_HOST="http://elastic:${ES_PASS}@127.0.0.1:9200"

echo "Installing elasticsearch Python client (if needed)..."
pip3 install -q 'elasticsearch>=8,<9'

echo "Recreating indices (DESTRUCTIVE)..."
python3 scripts/setup/setup_es_indices.py --recreate
