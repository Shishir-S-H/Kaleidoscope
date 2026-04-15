#!/usr/bin/env bash
# Full Elasticsearch reset for a single-node / dev cluster:
#   1. Delete every index that does NOT start with '.' (system indices kept)
#   2. Upsert ILM policy from es_mappings/ilm_policy.json (unless SKIP_ILM=1)
#   3. Recreate the 7 mapped indices from es_mappings/*.json
#
# After this, restart the Spring Boot app so Java-owned indices (posts, users,
# blogs, …) are recreated from PostgreSQL.

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

EXTRA=()
if [[ "${SKIP_ILM:-}" == "1" ]]; then
  EXTRA+=(--no-ilm)
fi

echo "Wiping cluster (DESTRUCTIVE)..."
python3 scripts/setup/setup_es_indices.py --wipe-cluster "${EXTRA[@]}"
