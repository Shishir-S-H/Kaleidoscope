# Developer Setup & Operations Guide — kaleidoscope-ai

> **Edition:** Phase C (April 2026)
> **Scope:** Local development setup, environment configuration, and operational troubleshooting for the `kaleidoscope-ai` Python AI microservices layer.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Local Setup — 5 Minutes](#2-local-setup--5-minutes)
3. [Environment Configuration](#3-environment-configuration)
4. [Common Commands](#4-common-commands)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker Desktop | Latest | Must be running before any `docker compose` command |
| Python | 3.11+ | Only needed if running tests outside Docker |
| RAM | 4 GB minimum | 8 GB recommended for comfortable local dev |
| Disk | 5 GB free | For Docker images and Elasticsearch data volume |
| Internet | Required | Services call HuggingFace Inference API at runtime |

---

## 2. Local Setup — 5 Minutes

### Step 1 — Clone and navigate

```bash
# If you haven't cloned yet
git clone https://github.com/Shishir-S-H/Kaleidoscope.git
cd Kaleidoscope/kaleidoscope-ai
```

### Step 2 — Create your `.env` file

```bash
cp .env.example .env
# Edit with your values (see Section 3 below)
```

### Step 3 — Start all services

```bash
docker compose up -d
```

Wait ~30 seconds for Redis and Elasticsearch to initialise before sending any traffic.

### Step 4 — Verify the system

```bash
# All containers should show status "Up"
docker compose ps

# Elasticsearch cluster health
curl http://localhost:9200/_cluster/health

# List all Elasticsearch indices (7 expected)
curl http://localhost:9200/_cat/indices?v
```

**Expected indices:**  
`media_search`, `post_search`, `user_search`, `face_search`, `recommendations_knn`, `feed_personalized`, `known_faces_index`

---

## 3. Environment Configuration

### 3.1 Required variables

Create `kaleidoscope-ai/.env` with the following. All values marked **Required** must be set before starting.

```bash
# ── Docker Registry ─────────────────────────────────────────────────────────
# Backend image is pulled from Docker Hub under DOCKER_REGISTRY
DOCKER_REGISTRY=ajayprabhu2004

# AI services are built locally; DOCKER_USERNAME kept for future CI/CD use
DOCKER_USERNAME=shishir01

# ── HuggingFace API ──────────────────────────────────────────────────────────
# Required — create a token at https://huggingface.co/settings/tokens
HF_API_TOKEN=hf_...your_token_here...

# HuggingFace Space endpoints — one per AI service (Required)
HF_API_URL_CONTENT_MODERATION=https://phantomfury-kaleidoscope-content-moderation.hf.space/classify
HF_API_URL_IMAGE_TAGGER=https://phantomfury-kaleidoscope-image-tagger.hf.space/tag
HF_API_URL_SCENE_RECOGNITION=https://phantomfury-kaleidoscope-scene-recognition.hf.space/recognize
HF_API_URL_IMAGE_CAPTIONING=https://phantomfury-kaleidoscope-image-captioning.hf.space/caption
HF_API_URL_FACE_RECOGNITION=https://phantomfury-kaleidoscope-face-recognition.hf.space/detect

# ── Security ─────────────────────────────────────────────────────────────────
# Required — use a strong random password in production
REDIS_PASSWORD=your-strong-redis-password
ELASTICSEARCH_PASSWORD=your-strong-elasticsearch-password

# ── Scene Recognition ────────────────────────────────────────────────────────
# Optional — default label set shown below
SCENE_LABELS=beach,mountains,urban,office,restaurant,forest,desert,lake,park,indoor,outdoor,rural,coastal,mountainous,tropical,arctic

# ── Backend Application ──────────────────────────────────────────────────────
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-backend
APP_PORT=8080
ENVIRONMENT=production
```

### 3.2 Generate strong passwords

```bash
# Redis password
openssl rand -base64 32

# Elasticsearch password
openssl rand -base64 32
```

### 3.3 Security reminders

- Never commit `.env` to git — it is already in `.gitignore`
- Rotate passwords every 90 days in production
- Keep `HF_API_TOKEN` out of logs and CI environment outputs

---

## 4. Common Commands

### Start / Stop

```bash
# Start all services (detached)
docker compose up -d

# Stop all services (preserves volumes)
docker compose down

# Stop and remove all volumes (full reset)
docker compose down -v
```

### Logs

```bash
# Follow logs for all services
docker compose logs -f

# Follow logs for a specific service
docker compose logs -f face_matcher

# Last 100 lines from a service
docker compose logs --tail=100 content_moderation
```

### Service management

```bash
# Check service health at a glance
docker compose ps

# Restart a single service without restarting the stack
docker compose restart face_matcher

# Rebuild a service image after code changes
docker compose up -d --build face_matcher
```

### Infrastructure health checks

```bash
# Redis ping (should return PONG)
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Elasticsearch cluster health
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health

# List all Redis streams
docker exec redis redis-cli -a ${REDIS_PASSWORD} KEYS "*"

# Inspect stream lengths
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN post-image-processing
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN ml-insights-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN face-detection-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN face-recognition-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN es-sync-queue
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN ai-processing-dlq
```

### Consumer groups — manual creation (if missing after a fresh start)

The `docker compose up` entrypoints create these automatically, but if you need to create them manually:

```bash
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing media-preprocessor-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE face-detection-results face-matcher-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE profile-picture-processing profile-enrollment-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-aggregation-trigger post-aggregator-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE es-sync-queue es-sync-group 0 MKSTREAM
docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE ai-processing-dlq dlq-processor-group 0 MKSTREAM
```

### Elasticsearch index setup

```bash
# (Re-)create all 7 index mappings from es_mappings/
python scripts/setup/setup_es_indices.py
```

### Running tests

```bash
# Full test suite
pytest

# Single test file
pytest tests/test_face_matcher.py -v

# Tests with live infrastructure (requires docker compose up -d)
pytest tests/test_e2e_pipeline.py -v
```

---

## 5. Troubleshooting

### Services won't start

**Symptoms:** Containers exit immediately or fail health checks.

```bash
# Check container exit reason
docker compose logs [service_name]

# Verify ports are free
# Redis: 6379, Elasticsearch: 9200 / 9300
netstat -an | findstr "6379 9200"   # Windows
lsof -i :6379 -i :9200              # macOS / Linux
```

Common causes:
- Docker Desktop not running
- Port 6379 or 9200 already in use by another process
- Insufficient disk space: `df -h`
- Insufficient memory: `free -h` (Linux) or Docker Desktop → Resources

---

### Redis connection errors

**Symptoms:** Services log `NOAUTH Authentication required` or `Connection refused` to Redis.

```bash
# Confirm Redis is up
docker compose ps redis

# Test password
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Check password in your .env
grep REDIS_PASSWORD .env
```

---

### Elasticsearch connection errors

**Symptoms:** `es_sync` or `face_matcher` logs `Connection refused` or `401 Unauthorized` against port 9200.

```bash
# Confirm ES is up and the health colour
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health

# Elasticsearch OOM (exit code 137) — cap heap for low-RAM machines
# Add to .env:
# ES_JAVA_OPTS=-Xms1g -Xmx1g
docker compose restart elasticsearch
```

---

### AI services not processing images

**Symptoms:** Images published to `post-image-processing` but nothing appears in `ml-insights-results`.

1. Verify consumer groups exist:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-image-processing
   ```

2. Check service logs for errors:

   ```bash
   docker compose logs content_moderation | grep -i error
   docker compose logs image_tagger | grep -i error
   ```

3. Verify HuggingFace API config is set:

   ```bash
   docker compose exec content_moderation env | grep HF_API
   ```

4. Restart AI services:

   ```bash
   docker compose restart content_moderation image_tagger scene_recognition image_captioning face_recognition
   ```

---

### face_matcher not producing tag suggestions

**Symptoms:** Face embeddings appear in `face-detection-results` but no events appear in `face-recognition-results`.

- Confirm `known_faces_index` is populated (requires at least one user to have uploaded a profile picture and gone through `profile_enrollment`).
- Check the KNN confidence threshold — default is `0.85`. A score below this suppresses output. Tune `KNN_CONFIDENCE_THRESHOLD` in the service env if needed.
- Check face_matcher logs:
  ```bash
  docker compose logs face_matcher | grep -i error
  ```

---

### Messages in Dead Letter Queue

**Symptoms:** `ai-processing-dlq` stream is growing.

```bash
# Count messages in DLQ
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN ai-processing-dlq

# Inspect the most recent failures
docker exec redis redis-cli -a ${REDIS_PASSWORD} XREVRANGE ai-processing-dlq + - COUNT 5
```

Common causes:
- HuggingFace API timeout or rate limit hit
- Invalid or unreachable image URL
- Network connectivity issue to external hosts

When `DLQ_AUTO_RETRY=true`, the `dlq_processor` service re-publishes failed messages to `post-image-processing` automatically (up to `DLQ_MAX_RETRIES`).

---

### Post Aggregator not firing

**Symptoms:** ML insights exist for all images in a post but no event appears in `post-insights-enriched`.

```bash
# Verify post-aggregation-trigger stream has entries
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN post-aggregation-trigger

# Check aggregator consumer group
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-aggregation-trigger

# Check aggregator logs
docker compose logs post_aggregator | tail -50
```

---

### ES Sync not indexing

**Symptoms:** Data exists in PostgreSQL read-model tables but the Elasticsearch index is empty or stale.

```bash
# Confirm es_sync is consuming
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS es-sync-queue

# Check ES Sync logs
docker compose logs es_sync | tail -50

# Verify PostgreSQL connectivity from inside the container
docker compose exec es_sync python -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                        database=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                        password=os.getenv('DB_PASSWORD'))
print('Connected'); conn.close()
"
```

---

### Slow processing

Expected latencies under normal load:

| Component | Typical Latency |
|-----------|----------------|
| AI processing (HuggingFace round-trip) | 10–30 s per image |
| Post aggregation | < 100 ms |
| ES Sync (index write) | < 100 ms |
| Elasticsearch search query | ~44 ms |

If AI processing consistently exceeds 60 s:
- Check HuggingFace API status page
- Verify your API token is valid and has not hit rate limits
- Check container resource usage: `docker stats`

---

### Checking pending messages per consumer group

```bash
docker exec redis redis-cli -a ${REDIS_PASSWORD} XPENDING post-image-processing content-moderation-group
docker exec redis redis-cli -a ${REDIS_PASSWORD} XPENDING ml-insights-results <consumer-group>
```
