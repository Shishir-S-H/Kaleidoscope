#!/usr/bin/env bash
#
# Clear all documents from Kaleidoscope Elasticsearch indices.
# Keeps indices and mappings intact — only data (documents) are removed.
#
# Usage (on SSH or host where ES is reachable):
#   export ELASTICSEARCH_PASSWORD='your_password'
#   export ES_BASE_URL='http://localhost:9200'   # optional; default below
#   ./clear_es_data.sh
#
# Or with inline env:
#   ELASTICSEARCH_PASSWORD='secret' ./clear_es_data.sh
#

set -e

ES_BASE_URL="${ES_BASE_URL:-http://localhost:9200}"
ES_USER="${ES_USER:-elastic}"

if [ -z "${ELASTICSEARCH_PASSWORD}" ]; then
  echo "Error: ELASTICSEARCH_PASSWORD is not set."
  echo "Usage: ELASTICSEARCH_PASSWORD='your_password' $0"
  exit 1
fi

INDICES=(
  "media_search"
  "post_search"
  "user_search"
  "face_search"
  "recommendations_knn"
  "feed_personalized"
  "known_faces_index"
)

echo "=============================================="
echo "Kaleidoscope - Clear Elasticsearch data only"
echo "=============================================="
echo "ES URL: $ES_BASE_URL"
echo "Indices: ${INDICES[*]}"
echo ""

for index in "${INDICES[@]}"; do
  echo -n "Clearing $index ... "
  resp=$(curl -s -w "\n%{http_code}" -X POST \
    -u "${ES_USER}:${ELASTICSEARCH_PASSWORD}" \
    -H "Content-Type: application/json" \
    "${ES_BASE_URL}/${index}/_delete_by_query?refresh=true" \
    -d '{"query":{"match_all":{}}}' 2>/dev/null) || true

  http_code=$(echo "$resp" | tail -n1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" = "200" ]; then
    deleted=$(echo "$body" | grep -o '"deleted":[0-9]*' | cut -d: -f2)
    echo "OK (deleted: ${deleted:-0})"
  elif [ "$http_code" = "404" ]; then
    echo "SKIP (index does not exist)"
  else
    echo "FAILED (HTTP $http_code)"
    echo "$body" | head -c 200
    echo ""
  fi
done

echo ""
echo "Done. Indices and mappings are unchanged; only documents were removed."
echo "Verify: curl -s -u elastic:\$ELASTICSEARCH_PASSWORD '$ES_BASE_URL/_cat/indices?v'"
