# Deployment Scripts

Scripts for managing the production deployment of Kaleidoscope AI services
to the DigitalOcean droplet at `165.232.179.167`.

---

## CI/CD — GitHub Actions (build & push only)

Every push to `main` triggers `.github/workflows/build-and-push.yml`, which:

1. **Builds** all AI service Docker images in parallel  
2. **Pushes** each image as `{DOCKER_USERNAME}/kaleidoscope-{service}:latest` and `:{sha}`  

**The workflow does not SSH into production.** After it turns green, deploy on the droplet: pull git, run DB migrations if needed, recreate Elasticsearch indices (see `documentation/handoff_teammate_java_kaleidoscope_repo.md`), then `docker compose pull && up`.

### Required GitHub Secrets (build job only)

| Secret | Description |
|--------|-------------|
| `DOCKER_USERNAME` | Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token |

Optional: remove unused secrets (`DO_SSH_PRIVATE_KEY`, `SPRING_DATASOURCE_URL`, etc.) from Actions if you no longer run the old deploy job from CI.

### Manual workflow triggers

`workflow_dispatch` runs the same build-and-push (no extra inputs).

---

## Manual production deploy (SSH)

Use `deploy-production.sh` from a machine with SSH access, or run the equivalent steps on the server. That path still needs server `.env` (Google, DB, Redis, ES passwords) and optionally `DO_SSH_PRIVATE_KEY` only on **your** laptop/CI that invokes the script.

---

## Scripts

### `deploy-production.sh` — Full automated deployment

Runs the entire deploy sequence locally (SSH to the droplet).

```bash
# Standard deploy
./scripts/deployment/deploy-production.sh

# Deploy + replay any stranded DLQ messages
./scripts/deployment/deploy-production.sh --drain-dlq

# Deploy without re-running V3/V4 SQL migrations
./scripts/deployment/deploy-production.sh --skip-migration
```

What it does:
1. Syncs the repo on the server (`git pull`)
2. Validates `.env` variables (warns on wrong Gemini model ID)
3. Applies **V3** SQL migration (image `VECTOR` 512→1408 where applicable)
4. Applies **V4** SQL migration (face tables `VECTOR` 1024→1408; **deletes** existing face rows)
5. Recreates Elasticsearch indices **`recommendations_knn`**, **`face_search`**, **`known_faces_index`** from `es_mappings/*.json` (documents are dropped — rely on `es_sync` / backend to repopulate)
6. Pulls all latest Docker images
7. Stops → starts all services
8. Waits 30 s then runs health checks (Redis, ES, backend, AI workers)
9. Optionally drains the DLQ backlog (`--drain-dlq`)

### `verify_google_apis.py` — Post-deploy verification

Run on the server after deployment to confirm everything is operational:

```bash
# On the server
python3 ~/Kaleidoscope/kaleidoscope-ai/scripts/deployment/verify_google_apis.py

# From your machine (via SSH)
ssh root@165.232.179.167 \
  'python3 ~/Kaleidoscope/kaleidoscope-ai/scripts/deployment/verify_google_apis.py'
```

Checks:
- All required `.env` variables present and non-empty
- `GOOGLE_CREDENTIALS_BASE64` decodes to valid JSON
- Vertex AI Gemini model responds to a real probe call
- Vertex AI Embedding model returns a 1408-dim vector
- Elasticsearch is green/yellow and all expected indices exist
- Redis is reachable; reports DLQ depth
- PostgreSQL is reachable; V3 image-embedding columns + **V4 face-vector columns** (expected `vector(1408)`)

### `verify_post_pipeline.py` — End-to-end pipeline audit

Audits every PostgreSQL read model and Elasticsearch index for a specific post:

```bash
python3 ~/Kaleidoscope/kaleidoscope-ai/scripts/deployment/verify_post_pipeline.py test-2
```

### `backup-production-configs.sh` — Backup server configs

```bash
./scripts/deployment/backup-production-configs.sh
```

Backs up `.env`, `nginx.conf`, SSL certs, and `docker-compose.prod.yml` to
`production-configs/{timestamp}/`.

---

## DLQ Drain (one-time fix after Gemini model update)

After deploying the fix for `GOOGLE_GEMINI_MODEL`, replay the stranded
`image_tagger`, `image_captioning`, and `scene_recognition` messages:

```bash
# Option A: via the deploy script
./scripts/deployment/deploy-production.sh --skip-migration --drain-dlq

# Option B: via GitHub Actions → workflow_dispatch with drain_dlq=true

# Option C: manually on the server
ssh root@165.232.179.167
cd ~/Kaleidoscope/kaleidoscope-ai
docker compose -f docker-compose.prod.yml stop dlq_processor
DLQ_AUTO_RETRY=true docker compose -f docker-compose.prod.yml up -d dlq_processor
sleep 60   # wait for drain
docker compose -f docker-compose.prod.yml stop dlq_processor
docker compose -f docker-compose.prod.yml up -d dlq_processor  # restart with default (false)
```

---

## Environment Variables Reference

The `.env` file on the server must contain:

```ini
# Infrastructure
REDIS_PASSWORD=<strong password>
ELASTICSEARCH_PASSWORD=<strong password>

# Google Cloud (Vertex AI)
GOOGLE_CLOUD_PROJECT=kaleidoscope-backend
GOOGLE_CLOUD_REGION=us-central1
GOOGLE_GEMINI_MODEL=gemini-2.0-flash-001        # MUST be versioned — gemini-1.5-flash returns 404
GOOGLE_EMBEDDING_MODEL=multimodalembedding@001  # produces 1408-dim vectors
GOOGLE_CREDENTIALS_BASE64=<base64 encoded service account JSON>
GOOGLE_MODERATION_THRESHOLD=0.5

# Database (Neon)
SPRING_DATASOURCE_URL=jdbc:postgresql://<host>/neondb?sslmode=require
DB_USERNAME=neondb_owner
DB_PASSWORD=<password>

# DLQ (set true only to drain backlog, then revert to false)
DLQ_AUTO_RETRY=false
```

---

## Troubleshooting

### Gemini 404 on Vertex AI
`publisher model gemini-1.5-flash not found` means the model ID is an unversioned
alias not supported on Vertex AI. Set `GOOGLE_GEMINI_MODEL=gemini-2.0-flash-001`
in `.env` and restart `image_tagger`, `image_captioning`, `scene_recognition`.

### `recommendations_knn` / `media_ai_insights` embedding is NULL
The V3 migration changed the vector column from 512 to 1408 dims. If it hasn't
run yet, execute it:
```bash
ssh root@165.232.179.167
psql "$SPRING_DATASOURCE_URL" -U "$DB_USERNAME" \
  -f ~/Kaleidoscope/kaleidoscope-ai/migrations/V3__upgrade_vector_dimensions.sql
```

### Services not starting
```bash
ssh root@165.232.179.167 \
  'docker compose -f ~/Kaleidoscope/kaleidoscope-ai/docker-compose.prod.yml logs --tail=50'
```

### Secrets exposed via `docker exec printenv`
Rotate immediately: DB password, Redis password, Google service account key.
Update `.env` and `docker compose ... up -d` to pick up new values.

---

## Server Details

- **Host**: `165.232.179.167`
- **User**: `root`
- **App directory**: `~/Kaleidoscope/kaleidoscope-ai`
- **Backend registry**: `ajayprabhu2004/kaleidoscope:backend-latest`
- **AI registry**: `shishir01/kaleidoscope-{service}:latest`
