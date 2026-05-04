# Handoff: kaleidoscope-ai + production + Java `Kaleidoscope` repo

This note is for a teammate after the **May 2026** alignment on **1408-dimensional** face and image embeddings (Vertex AI `multimodalembedding@001`), CI that **builds/pushes only**, and production operations on the droplet.

---

## Part A — What was changed in **kaleidoscope-ai** (`Shishir-S-H/Kaleidoscope` on GitHub)

| Area | Change |
|------|--------|
| **Elasticsearch** | `es_mappings/face_search.json` and `es_mappings/known_faces_index.json`: `face_embedding.dims` **1024 → 1408**. |
| **PostgreSQL** | **`migrations/V4__face_embeddings_vector_1408.sql`**: deletes rows in `read_model_face_search`, `media_detected_faces`, `read_model_known_faces`, then alters embedding columns to **`vector(1408)`**. |
| **Deploy script** | `scripts/deployment/deploy-production.sh`: runs **V4** after V3; recreates ES indices **`recommendations_knn`**, **`face_search`**, **`known_faces_index`**. |
| **One-off DB script** | `scripts/deployment/fix_face_vector_dim.py`: includes **`read_model_known_faces`**; correct column **`face_embedding`** on `read_model_face_search`. |
| **Tests / HF default / `.env.example`** | Face mocks **1408**; `FACE_EMBEDDING_DIM` documented. |
| **Verification** | `scripts/deployment/verify_google_apis.py`: checks face PG columns (expect **1408**). |
| **GitHub Actions** | `.github/workflows/build-and-push.yml`: **no SSH deploy**; build + push only. |

---

## Part B — Local **`Kaleidoscope`** Java/frontend repo (this workspace: `c:\Legion\Micorservice\Kaleidoscope`)

**Remote:** `origin` → `https://github.com/nrashmi06/Kaleidoscope.git` (may differ from production’s `Shishir-S-H/Kaleidoscope` fork — reconcile branches before pushing).

### B1. Git state (May 4, 2026)

- **`git pull` / merge completed:** `main` was merged with **`origin/main`** including **PR #104 / #105** (article UI / bug fixes) while retaining local commits **`3b71c80`** (recommendations_knn ES guard) and **`2bc701d`** (face pipeline / `MediaAiInsights` concurrency). Merge commit: **`aea0afb`**.
- **Stash removed:** `stash@{0}` was **dropped** (not applied). It contained a large **README** rewrite, **docker-compose** tweaks, and small edits to **`MediaAiInsightsConsumer`** / **`ReadModelUpdateService`**. That work was **superseded** by the merge and by the newer **`kaleidoscope-ai`** pipeline; nothing from the stash was merged into the handoff as required code — only noted here for archaeology.

### B2. Java changes still required (confirmed on merged `main`)

These files still assume **1024** for **face** vectors while **PostgreSQL V4** and **Python/ES** expect **1408** for face crops (Vertex multimodal). Until updated, Hibernate/ES may reject inserts or mis-map dimensions.

| File | Issue |
|------|--------|
| `backend/src/main/java/com/kaleidoscope/backend/posts/model/MediaDetectedFace.java` | `columnDefinition = "vector(1024)"` → should be **`vector(1408)`**. |
| `backend/src/main/java/com/kaleidoscope/backend/users/model/UserFaceEmbedding.java` | `vector(1024)` → **`vector(1408)`** (if table still used). |
| `backend/src/main/java/com/kaleidoscope/backend/users/document/UserDocument.java` | `@Field(..., dims = 1024)` for face-related dense vector → **`1408`** if that field is used with the same embedding model. |
| `backend/src/main/java/com/kaleidoscope/backend/users/document/UserFaceEmbeddingDocument.java` | Comment / mapping for **1024** → **1408**. |
| `backend/src/main/java/com/kaleidoscope/backend/users/document/UserProfileDocument.java` | Comment **1024** → **1408**. |
| `backend/src/main/java/com/kaleidoscope/backend/posts/document/MediaDetectedFaceDocument.java` | Comment **1024** → **1408**; ensure Spring Data ES mapping matches `face_search` index (**1408**). |
| `backend/docs/ELASTICSEARCH_INTEGRATION.md` | Update **1024** references for face where applicable. |

**Already aligned to 1408 (image path):** `MediaAiInsights.java` (`image_embedding` `vector(1408)`), `ReadModelUpdateService` / `RecommendationsKnnReadModel` / `MediaSearchReadModel` / ES docs for **image** embeddings (see grep on `1408`).

**`FaceSearchReadModel.java`:** uses **`TEXT`** for `face_embedding` in JPA while the DB column is **pgvector** after migrations — confirm Hibernate type mapping does not fight `vector(1408)`; adjust if you see bind/parse errors.

### B3. Hikari pool (critical for Redis burst + Neon)

**File:** `backend/src/main/resources/application.yml`  
**Current:** `spring.datasource.hikari.maximum-pool-size: **2**`  

This matches production incidents (**connection timed out**, `total=2, active=2`) when **`MediaAiInsightsConsumer`**, **`FaceDetectionConsumer`**, and API traffic compete. **Raise** `maximum-pool-size` (e.g. **10–20**, subject to Neon pooler limits) and tune **`minimum-idle`** / transaction boundaries on stream consumers.

### B4. Post aggregation / `read_model_post_search`

If ML completes but aggregated post search is missing, inspect **`PostAggregationTriggerService`**, **`PostInsightsEnrichedConsumer`**, and Redis PEL backlog after pool fixes. See `documentation/handoff_backend_teammate.md`.

---

## Part C — Production droplet (**`165.232.179.167`**) — May 4, 2026 operator run

**Layout:** compose file at **`/root/Kaleidoscope/docker-compose.prod.yml`** (monorepo root = kaleidoscope-ai + backend in one tree on this host).

| Step | Result |
|------|--------|
| **`git fetch` + `reset --hard origin/main`** | Server at **`4400cc9`** (`feat(deploy): face ES/pg 1408 dims, CI build-only`). |
| **`docker compose … pull` + `up -d`** | All services restarted successfully. |
| **Elasticsearch** | **`recommendations_knn`**, **`face_search`**, **`known_faces_index`** deleted and recreated from **`/root/Kaleidoscope/es_mappings/*.json`** (HTTP 200 PUT). |
| **PostgreSQL V4** | Applied via **`docker run postgres:16-alpine psql`** (host had no `psql` binary). Output included **`DELETE`/`ALTER TABLE`** on face tables — **OK**. |
| **Logs (first ~5 min after restart)** | **`kaleidoscope-backend`**: startup sync **26 posts**, **7 users**, **19 blogs**, **0 errors**; Redis stream listeners started. **`es_sync`**, **`face_matcher`**, **`face_recognition`**, **`dlq_processor`**, **`post_aggregator`**: healthy startup lines; **no ERROR/Exception** lines in sampled tail. |

**Follow-ups on prod:** empty **`face_search`** / **`known_faces_index`** / **`recommendations_knn`** until **`es_sync`** and backend republish; users may need **profile re-enrollment** for known faces. Watch **`docker logs kaleidoscope-backend`** for Hibernate **dimension** or **SQL** errors on first new face write after V4.

**Re-run V4 + ES refresh without full deploy:** use `scripts/deployment/deploy-production.sh` or the **`docker run … psql`** + **`curl` DELETE/PUT** pattern from that script. On hosts **without `psql`**, use the **`postgres:16-alpine`** one-off container with **`-v /root/Kaleidoscope/migrations:/mig:ro`**.

---

## Part D — What **you** do next (checklist)

1. **kaleidoscope-ai:** wait for **Actions** “Build & Push AI Images”; on server **`git pull`**; **`docker compose pull && up -d`**.  
2. **Java `Kaleidoscope`:** implement **Part B2** + **B3**, run tests, build **`backend-latest`**, deploy backend image.  
3. **Verify:** `verify_google_apis.py`, `verify_post_pipeline.py`, and a **new post with faces**.  
4. **Forks:** align **`nrashmi06/Kaleidoscope`** vs **`Shishir-S-H/Kaleidoscope`** so `main` does not diverge unintentionally.

---

## Part E — GitHub Actions secrets (kaleidoscope-ai)

- **Required:** `DOCKER_USERNAME`, `DOCKER_PASSWORD`.  
- **Optional cleanup:** remove secrets only used by the **removed** SSH deploy job unless another workflow needs them.

---

## Summary

| Location | Status / action |
|----------|-----------------|
| **kaleidoscope-ai** | 1408 ES + V4 + CI build-only on `main` (e.g. `4400cc9` on Shishir fork). |
| **Prod droplet** | Pulled `4400cc9`, restarted compose, **recreated three ES indices**, **applied V4** via Docker `psql`; startup logs clean. |
| **Local Java `Kaleidoscope`** | Merged `origin/main` → **`aea0afb`**; **stash dropped**; **still need JPA/ES 1408 + Hikari** per Part B. |

Send questions with **`docker logs …`** and **`verify_google_apis.py`** output after the next backend deploy.
