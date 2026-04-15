#!/usr/bin/env bash
# Run on server: bash audit_post_remote.sh [title_substring]
# Defaults title substring to Test-1
set -eu
cd /root/Kaleidoscope
set -a
# shellcheck disable=SC1091
source .env
set +a
TITLE_SUB="${1:-Test-1}"
JDBC="${SPRING_DATASOURCE_URL}"
HOSTPORT="${JDBC#jdbc:postgresql://}"
PGHOST="${HOSTPORT%%/*}"
REST="${HOSTPORT#*/}"
PGDATABASE="${REST%%\?*}"
PGUSER="${SPRING_DATASOURCE_USERNAME:-${DB_USERNAME:-}}"
export PGPASSWORD="${SPRING_DATASOURCE_PASSWORD:-${DB_PASSWORD:-}}"
export PGPORT="${PGPORT:-5432}"
export PGSSLMODE=require

run_sql() {
  docker run --rm \
    -e PGPASSWORD \
    -e PGSSLMODE \
    postgres:16-alpine \
    psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -At -c "$1"
}

echo "=== posts matching title (ILIKE %${TITLE_SUB}%) ==="
run_sql "SELECT post_id, title, user_id, status, visibility, created_at FROM posts WHERE title ILIKE '%${TITLE_SUB}%' ORDER BY created_at DESC LIMIT 5;"

PID=$(run_sql "SELECT post_id FROM posts WHERE title ILIKE '%${TITLE_SUB}%' ORDER BY created_at DESC LIMIT 1;")
echo "POST_ID=$PID"
if [[ -z "$PID" ]]; then echo "No post found"; exit 0; fi

MID=$(run_sql "SELECT media_id FROM post_media WHERE post_id = ${PID} ORDER BY position LIMIT 1;")
echo "MEDIA_ID=$MID"

echo "=== post_media ==="
run_sql "SELECT media_id, post_id, media_type, position, width, height, file_size_kb FROM post_media WHERE post_id = ${PID};"

echo "=== post_categories ==="
run_sql "SELECT * FROM post_categories WHERE post_id = ${PID};" || true

echo "=== post_saves count ==="
run_sql "SELECT COUNT(*) FROM post_saves WHERE post_id = ${PID};"

if [[ -n "${MID:-}" ]]; then
  echo "=== media_ai_insights ==="
  run_sql "SELECT media_id, status, is_safe, (caption IS NOT NULL) AS has_caption, (tags IS NOT NULL) AS has_tags, (scenes IS NOT NULL) AS has_scenes, (image_embedding IS NOT NULL) AS has_embedding, services_completed::text, version FROM media_ai_insights WHERE media_id = ${MID};" || true
  echo "=== media_detected_faces count ==="
  run_sql "SELECT COUNT(*) FROM media_detected_faces WHERE media_id = ${MID};" || true
fi

echo "=== read_model_post_search exists ==="
run_sql "SELECT EXISTS(SELECT 1 FROM read_model_post_search WHERE post_id = ${PID});" || true

if [[ -n "${MID:-}" ]]; then
  echo "=== read_model_media_search ==="
  run_sql "SELECT media_id, (caption IS NOT NULL), (image_embedding IS NOT NULL), (tags IS NOT NULL) FROM read_model_media_search WHERE media_id = ${MID};" || true
  echo "=== read_model_recommendations_knn ==="
  run_sql "SELECT media_id, (image_embedding IS NOT NULL) FROM read_model_recommendations_knn WHERE media_id = ${MID};" || true
  echo "=== read_model_feed_personalized ==="
  run_sql "SELECT media_id, post_id, (caption IS NOT NULL) FROM read_model_feed_personalized WHERE media_id = ${MID};" || true
  echo "=== read_model_face_search count (media_id) ==="
  run_sql "SELECT COUNT(*) FROM read_model_face_search WHERE media_id = ${MID};" || true
fi
