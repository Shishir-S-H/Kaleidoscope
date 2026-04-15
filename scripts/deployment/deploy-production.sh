#!/usr/bin/env bash
# deploy-production.sh
#
# Fully automated deployment to DigitalOcean droplet at 165.232.179.167.
#
# Usage:
#   ./scripts/deployment/deploy-production.sh [--drain-dlq] [--skip-migration]
#
# Flags:
#   --drain-dlq         After deploy, temporarily enable DLQ auto-retry to replay
#                       stranded messages, then disable it.
#   --skip-migration    Skip running V3 SQL migration (use if already applied).
#
# Prerequisites:
#   - SSH key-based access to root@165.232.179.167
#   - psql available on the remote server (for the migration step)
#   - The remote ~/Kaleidoscope directory must already exist (see setup-production.sh)

set -euo pipefail

# ── Colours ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BLUE}══ $* ${NC}"; }

# ── Config ───────────────────────────────────────────────────────────────────
SSH_HOST="root@165.232.179.167"
REMOTE_DIR="~/Kaleidoscope/kaleidoscope-ai"
DOCKER_REGISTRY_BACKEND="ajayprabhu2004"
DOCKER_REGISTRY_AI="shishir01"

DRAIN_DLQ=false
SKIP_MIGRATION=false

for arg in "$@"; do
  case "$arg" in
    --drain-dlq)        DRAIN_DLQ=true ;;
    --skip-migration)   SKIP_MIGRATION=true ;;
    *) error "Unknown flag: $arg"; exit 1 ;;
  esac
done

AI_SERVICES=(
  media_preprocessor profile_enrollment face_matcher
  content_moderation image_tagger scene_recognition
  image_captioning image_embedding face_recognition
  post_aggregator dlq_processor es_sync
)

# ── SSH connectivity ─────────────────────────────────────────────────────────
step "SSH connectivity check"
if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "${SSH_HOST}" true 2>/dev/null; then
  warn "Key-based SSH not available. You may be prompted for a password."
fi
info "Connected to ${SSH_HOST}"

# ── Sync repo ────────────────────────────────────────────────────────────────
step "Sync repo on server"
if ssh "${SSH_HOST}" "cd ~/Kaleidoscope && git fetch origin main && git reset --hard origin/main"; then
  info "Repo synced to $(git rev-parse --short HEAD 2>/dev/null || echo 'latest')"
else
  warn "git sync failed — continuing with files already on server"
fi

# ── Verify .env ──────────────────────────────────────────────────────────────
step "Environment verification"
ssh "${SSH_HOST}" "bash -s" << 'ENVCHECK'
  ENV_FILE=~/Kaleidoscope/kaleidoscope-ai/.env
  if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found. Copy .env.example and fill in values."
    exit 1
  fi
  source "$ENV_FILE"

  REQUIRED=(
    REDIS_PASSWORD ELASTICSEARCH_PASSWORD
    GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_REGION GOOGLE_CREDENTIALS_BASE64
    GOOGLE_GEMINI_MODEL GOOGLE_EMBEDDING_MODEL
    SPRING_DATASOURCE_URL DB_USERNAME DB_PASSWORD
  )
  MISSING=()
  for VAR in "${REQUIRED[@]}"; do
    [ -z "${!VAR:-}" ] && MISSING+=("$VAR")
  done

  if [ ${#MISSING[@]} -gt 0 ]; then
    echo "ERROR: Missing required variables in .env:"
    printf '  %s\n' "${MISSING[@]}"
    exit 1
  fi

  # Warn if old model is still set
  if [ "${GOOGLE_GEMINI_MODEL:-}" = "gemini-1.5-flash" ]; then
    echo "WARNING: GOOGLE_GEMINI_MODEL=gemini-1.5-flash is an unversioned alias that"
    echo "         returns 404 on Vertex AI. Update to gemini-2.0-flash-001."
  else
    echo "  GOOGLE_GEMINI_MODEL=${GOOGLE_GEMINI_MODEL}"
  fi

  echo "All required environment variables are present."
ENVCHECK
info "Environment OK"

# ── V3 migration ─────────────────────────────────────────────────────────────
if [ "${SKIP_MIGRATION}" = false ]; then
  step "Apply V3 vector-dimension migration (512 → 1408)"
  ssh "${SSH_HOST}" "bash -s" << 'MIGRATION'
    set -e
    ENV_FILE=~/Kaleidoscope/kaleidoscope-ai/.env
    MIGRATION_SQL=~/Kaleidoscope/kaleidoscope-ai/migrations/V3__upgrade_vector_dimensions.sql

    [ ! -f "$MIGRATION_SQL" ] && { echo "V3 migration not found — skipping"; exit 0; }

    source "$ENV_FILE" 2>/dev/null || true
    [ -z "${SPRING_DATASOURCE_URL:-}" ] && { echo "SPRING_DATASOURCE_URL not set — skipping"; exit 0; }

    # Parse JDBC URL
    REST="${SPRING_DATASOURCE_URL#jdbc:postgresql://}"
    HOST_PORT="${REST%%/*}"
    PATH_QUERY="${REST#*/}"
    DB_HOST="${HOST_PORT%%:*}"
    DB_PORT_PART="${HOST_PORT##*:}"
    DB_NAME="${PATH_QUERY%%\?*}"
    DB_PORT="${DB_PORT_PART:-5432}"
    [ "$DB_PORT" = "$DB_HOST" ] && DB_PORT=5432

    echo "Applying V3 migration → ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    PGPASSWORD="${DB_PASSWORD}" psql \
      -h "${DB_HOST}" -p "${DB_PORT}" \
      -U "${DB_USERNAME}" -d "${DB_NAME}" \
      --set=sslmode=require \
      -f "${MIGRATION_SQL}" \
      && echo "V3 migration applied successfully." \
      || echo "WARNING: Migration returned non-zero (may already be applied)."
MIGRATION
else
  info "Skipping V3 migration (--skip-migration)"
fi

# ── Refresh recommendations_knn ES mapping ───────────────────────────────────
step "Refresh Elasticsearch recommendations_knn index (1408-dim)"
ssh "${SSH_HOST}" "bash -s" << 'ESREFRESH'
  source ~/Kaleidoscope/kaleidoscope-ai/.env 2>/dev/null || true
  ES_PASS="${ELASTICSEARCH_PASSWORD:-}"
  [ -z "$ES_PASS" ] && { echo "ELASTICSEARCH_PASSWORD not set — skipping"; exit 0; }

  BASE="http://localhost:9200"
  AUTH="elastic:${ES_PASS}"
  MAPPING=~/Kaleidoscope/kaleidoscope-ai/es_mappings/recommendations_knn.json

  # ES may still be starting — retry up to 5 times
  for i in 1 2 3 4 5; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u "$AUTH" "$BASE/_cluster/health" 2>/dev/null || echo "000")
    [ "$STATUS" -ge 200 ] && [ "$STATUS" -lt 300 ] && break
    echo "ES not ready (attempt $i/5, status $STATUS) — waiting 10s..."
    sleep 10
  done

  echo "Deleting old recommendations_knn index (404 is OK)..."
  curl -s -o /dev/null -w "HTTP %{http_code}\n" -u "$AUTH" -X DELETE "$BASE/recommendations_knn" || true
  echo "Creating recommendations_knn with 1408-dim mapping..."
  RESULT=$(curl -sf -u "$AUTH" -X PUT "$BASE/recommendations_knn" \
    -H "Content-Type: application/json" \
    -d "@$MAPPING" 2>&1)
  echo "$RESULT"
ESREFRESH

# ── Pull latest images ───────────────────────────────────────────────────────
step "Pull latest Docker images"
info "Pulling backend image..."
ssh "${SSH_HOST}" "docker pull ${DOCKER_REGISTRY_BACKEND}/kaleidoscope:backend-latest" || warn "Backend pull failed"

for svc in "${AI_SERVICES[@]}"; do
  info "Pulling ${svc}..."
  ssh "${SSH_HOST}" "docker pull ${DOCKER_REGISTRY_AI}/kaleidoscope-${svc}:latest" \
    || warn "${svc} pull failed (continuing)"
done

# ── Stop → start ─────────────────────────────────────────────────────────────
step "Restart all services"
ssh "${SSH_HOST}" "
  cd ${REMOTE_DIR}
  docker compose -f docker-compose.prod.yml down --remove-orphans
  docker compose -f docker-compose.prod.yml up -d
"
info "Services started"

# ── Wait + health checks ─────────────────────────────────────────────────────
step "Waiting 30s for services to stabilise..."
sleep 30

step "Health checks"
ssh "${SSH_HOST}" "bash -s" << 'HEALTH'
  source ~/Kaleidoscope/kaleidoscope-ai/.env 2>/dev/null || true

  echo "── Container status ──────────────────────"
  docker compose -f ~/Kaleidoscope/kaleidoscope-ai/docker-compose.prod.yml ps

  echo ""
  echo "── Redis ─────────────────────────────────"
  docker exec redis redis-cli -a "${REDIS_PASSWORD:-}" ping 2>/dev/null \
    && echo "Redis: OK" || echo "Redis: NOT READY"

  echo ""
  echo "── Elasticsearch ─────────────────────────"
  HEALTH=$(curl -sf -u "elastic:${ELASTICSEARCH_PASSWORD:-}" \
    http://localhost:9200/_cluster/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "NOT READY")
  echo "Elasticsearch cluster: $HEALTH"

  echo ""
  echo "── Backend ───────────────────────────────"
  BACKEND_ID=$(docker ps -q -f name=kaleidoscope-app 2>/dev/null | head -1)
  if [ -n "$BACKEND_ID" ]; then
    docker exec "$BACKEND_ID" curl -sf http://localhost:8080/actuator/health 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print('Backend:', d.get('status','?'))" 2>/dev/null \
      || echo "Backend: starting up..."
  else
    echo "Backend: container not found"
  fi

  echo ""
  echo "── AI workers ────────────────────────────"
  for svc in image_tagger image_captioning scene_recognition image_embedding \
             content_moderation face_recognition post_aggregator es_sync dlq_processor; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null || echo "missing")
    RESTARTED=$(docker inspect --format='{{.RestartCount}}' "$svc" 2>/dev/null || echo "?")
    printf "  %-25s status=%-12s restarts=%s\n" "$svc" "$STATUS" "$RESTARTED"
  done
HEALTH

# ── DLQ drain ────────────────────────────────────────────────────────────────
if [ "${DRAIN_DLQ}" = true ]; then
  step "DLQ backlog drain"
  info "Restarting dlq_processor with DLQ_AUTO_RETRY=true..."
  ssh "${SSH_HOST}" "
    cd ${REMOTE_DIR}
    docker compose -f docker-compose.prod.yml stop dlq_processor
    DLQ_AUTO_RETRY=true docker compose -f docker-compose.prod.yml up -d dlq_processor
    echo 'Waiting 60s for DLQ drain...'
    sleep 60
    echo 'Disabling auto-retry...'
    docker compose -f docker-compose.prod.yml stop dlq_processor
    docker compose -f docker-compose.prod.yml up -d dlq_processor
    echo 'DLQ processor restarted with DLQ_AUTO_RETRY=false'
  "
  info "DLQ drain complete"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
info "══════════════════════════════════════════════"
info "  Deployment complete"
info "  Host   : 165.232.179.167"
info "  Commit : $(git rev-parse --short HEAD 2>/dev/null || echo 'n/a')"
if [ "${DRAIN_DLQ}" = true ]; then
  info "  DLQ    : drained"
fi
info "══════════════════════════════════════════════"
echo ""
info "Useful commands:"
echo "  Live logs   : ssh ${SSH_HOST} 'docker compose -f ${REMOTE_DIR}/docker-compose.prod.yml logs -f --tail=100'"
echo "  Worker logs : ssh ${SSH_HOST} 'docker logs -f image_tagger'"
echo "  Verify post : ssh ${SSH_HOST} 'python3 ${REMOTE_DIR}/scripts/deployment/verify_post_pipeline.py test-2'"
echo "  DLQ drain   : $0 --skip-migration --drain-dlq"
