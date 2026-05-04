# Handoff: kaleidoscope-ai (done) + production steps + Java `Kaleidoscope` repo

This note is for a teammate after the **May 2026** changes on branch `main` of **kaleidoscope-ai**: face vectors and Elasticsearch mappings are aligned to **1408 dimensions** (Vertex AI `multimodalembedding@001`), GitHub Actions **only builds and pushes** Docker images (no automatic SSH deploy), and deploy scripts recreate the relevant ES indices.

---

## Part A — What was changed in **kaleidoscope-ai** (already in repo)

| Area | Change |
|------|--------|
| **Elasticsearch** | `es_mappings/face_search.json` and `es_mappings/known_faces_index.json`: `face_embedding.dims` **1024 → 1408**. |
| **PostgreSQL** | New **`migrations/V4__face_embeddings_vector_1408.sql`**: deletes rows in `read_model_face_search`, `media_detected_faces`, `read_model_known_faces`, then alters embedding columns to **`vector(1408)`**. |
| **Deploy script** | `scripts/deployment/deploy-production.sh`: runs **V4** after V3; recreates ES indices **`recommendations_knn`**, **`face_search`**, **`known_faces_index`** (delete + PUT from JSON). |
| **One-off DB script** | `scripts/deployment/fix_face_vector_dim.py`: extended to **`read_model_known_faces`**; fixed wrong column name on `read_model_face_search` (`face_embedding`). |
| **Tests** | `tests/test_face_matcher.py`, `tests/test_profile_enrollment.py`: mock vectors **1408** long. |
| **HF provider default** | `shared/providers/huggingface/face.py`: default **`FACE_EMBEDDING_DIM=1408`** (Google path already used 1408). |
| **`.env.example`** | Documents **`FACE_EMBEDDING_DIM=1408`**. |
| **Verification** | `scripts/deployment/verify_google_apis.py`: PostgreSQL check includes face columns’ **`vector(1408)`** via `format_type`. |
| **Docs** | `system_architecture.md`, `integration_contracts.md`, `user_journeys.md`, `developer_setup.md`, `scripts/deployment/README.md`: face/image dims updated to **1408** where applicable. |
| **Profile worker** | `services/profile_enrollment/worker.py`: docstring no longer says “HF only”. |
| **GitHub Actions** | `.github/workflows/build-and-push.yml`: **removed** SSH deploy job; workflow **builds + pushes** images only; final job prints manual deploy reminders. |

---

## Part B — What **you** do on production (after CI is green)

Assume droplet **`root@165.232.179.167`** and repo layout **`~/Kaleidoscope`** (adjust if your server uses `~/Kaleidoscope` as the kaleidoscope-ai root only).

### B1. Wait for GitHub Actions

1. Open the repo on GitHub → **Actions** → wait for **“Build & Push AI Images”** to finish successfully for the commit you care about.

### B2. Pull latest **kaleidoscope-ai** on the server

```bash
ssh root@165.232.179.167
# If monorepo with nested kaleidoscope-ai:
cd ~/Kaleidoscope && git fetch origin main && git reset --hard origin/main
# If kaleidoscope-ai is standalone, cd to that repo instead and pull main.
```

### B3. Apply database migrations (if not already applied)

From the server (or any host with `psql` and credentials):

- **V3** (image embeddings 512→1408): `migrations/V3__upgrade_vector_dimensions.sql` — idempotent in most cases.  
- **V4** (face vectors 1024→1408): **`migrations/V4__face_embeddings_vector_1408.sql`** — **destructive** for face tables (deletes all face rows before alter).

Easiest path: run the full local deploy script from a laptop with SSH keys (it runs V3, V4, ES refresh, compose):

```bash
./scripts/deployment/deploy-production.sh
```

To **skip** migrations if both V3 and V4 are already applied but you still want ES + compose refresh:

```bash
./scripts/deployment/deploy-production.sh --skip-migration
```

Then **manually** recreate the three indices if mappings changed (same `curl` DELETE/PUT pattern as in `deploy-production.sh`).

### B4. Pull new containers and restart

```bash
cd ~/Kaleidoscope/kaleidoscope-ai   # or your actual compose directory
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### B5. Server `.env`

Ensure:

- `GOOGLE_EMBEDDING_MODEL=multimodalembedding@001`  
- **`FACE_EMBEDDING_DIM=1408`** (explicit is best).  

### B6. Post-deploy checks

```bash
python3 ~/Kaleidoscope/kaleidoscope-ai/scripts/deployment/verify_google_apis.py
python3 ~/Kaleidoscope/kaleidoscope-ai/scripts/deployment/verify_post_pipeline.py "<post-title>"
```

### B7. Operational follow-ups

- **Redis PEL**: If messages were stuck on `ml-insights-results` / `face-detection-results`, reclaim or retry after DB pool / dim fixes.  
- **DLQ**: Use `deploy-production.sh --drain-dlq` or toggle `DLQ_AUTO_RETRY` per runbook.  
- **Reindex**: Recreating **`face_search`** / **`known_faces_index`** clears ES documents; **`es_sync`** and/or backend flows must republish. Users may need to **re-upload profile photos** for `known_faces_index` rows.

---

## Part C — **`Kaleidoscope` Java backend** repo (separate codebase; not modified here)

Send your teammate this checklist for the **Java** monorepo (often cloned as `~/Kaleidoscope` with `kaleidoscope-ai` inside or sibling — match your layout).

### C1. Hikari / connection pool (production stability)

Symptoms: `KaleidoscopeHikariCP - Connection is not available, request timed out` with **`total=2`** while Redis consumers run in parallel.

**Suggested changes** (Spring Boot):

- Increase **`spring.datasource.hikari.maximum-pool-size`** (e.g. 10–20; tune against Neon pooler limits).  
- Review **`minimum-idle`**, **`connection-timeout`**, and transaction scope on **`MediaAiInsightsConsumer`**, **`FaceDetectionConsumer`**, and other stream consumers so connections are not held for tens of seconds under burst.

Set via **`application-prod.yml`** or environment variables exposed on the **`app`** service in compose (if you add `SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE` or equivalent supported property).

### C2. Face and image embedding dimensions (1408)

- Any Java code that **validates**, **truncates**, or assumes **1024** or **512** for **face** or **image** embeddings must use **1408** for the Vertex multimodal model path.  
- **`read_model_known_faces`**, **`media_detected_faces`**, **`read_model_face_search`**: entity / JDBC types must accept **`vector(1408)`** (or `float[]` length 1408) after V4 runs.  
- Elasticsearch **Java-owned** documents: if any code builds KNN queries against indices that now store **1408** dims, query vectors must match.

### C3. Post aggregation / `read_model_post_search`

If posts complete ML but **aggregation** or **`post_search`** ES docs are missing, verify:

- **`PostAggregationTriggerService`** / **`PostInsightsConsumer`** paths after ML completion.  
- Redis consumer errors (same pool exhaustion can skip aggregation).  
- Optional **retrigger** tooling/scripts your team uses for `post-aggregation-trigger`.

### C4. Sync Java repo on server

```bash
cd ~/Kaleidoscope   # Java repo root, if applicable
git pull origin main
# Rebuild/restart backend image if you build on CI: docker pull … && compose up app
```

### C5. References in this repo

- `documentation/java_backend_handoff_google_migration.md` — image 512→1408, Vision faces, enrollment.  
- `documentation/handoff_backend_teammate.md` — prior backend patches / PEL notes.

---

## Part D — GitHub repository settings reminder

- Actions secrets: **only `DOCKER_USERNAME` + `DOCKER_PASSWORD`** are required for the new workflow.  
- You may **delete** obsolete secrets used only by the old deploy job (`DO_SSH_PRIVATE_KEY`, `SPRING_DATASOURCE_URL`, `DB_*`, `GOOGLE_*` on GitHub) **unless** another workflow still needs them.

---

## Summary

| Location | Action |
|----------|--------|
| **kaleidoscope-ai `main`** | Merged: 1408 face mappings, V4 migration, deploy script, CI build-only, docs/tests. |
| **Production server** | After CI: `git pull`, run migrations / `deploy-production.sh`, `docker compose pull && up`, verify scripts. |
| **Java `Kaleidoscope` repo** | Teammate: pool size, 1408 validation, aggregation/PEL — see Part C. |

Questions: reply in your team channel with logs from `verify_google_apis.py` and `docker logs kaleidoscope-backend --since 30m` after deploy.
