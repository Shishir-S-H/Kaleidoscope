# System Architecture — Kaleidoscope Platform

> **Edition:** Phase C (April 2026)  
> **Scope:** Full-stack platform — React Frontend → Java Spring Boot → Redis Streams → Python AI Workers → Elasticsearch / PostgreSQL  
> **Status:** Reflects all Phase C schema-alignment patches.

---

## Table of Contents

1. [Full-Stack Macro Diagram](#1-full-stack-macro-diagram)
2. [Technology Stack by Layer](#2-technology-stack-by-layer)
3. [Python Microservice Topology](#3-python-microservice-topology)
4. [Active Redis Stream Inventory](#4-active-redis-stream-inventory)
5. [Elasticsearch Index Inventory](#5-elasticsearch-index-inventory)
6. [Infrastructure Services](#6-infrastructure-services)
7. [Shared Library Overview](#7-shared-library-overview)
8. [Provider Abstraction Layer](#8-provider-abstraction-layer)
9. [Health & Observability](#9-health--observability)
10. [Security Model](#10-security-model)
11. [Five-Phase Build History](#11-five-phase-build-history)

---

## 1. Full-Stack Macro Diagram

```mermaid
graph TD
    subgraph FE["Frontend — Next.js (React)"]
        UI[User Interface]
    end

    subgraph BE["Backend — Java Spring Boot (port 8080)"]
        CTRL[REST Controllers]
        SVC[Service Layer]
        PG[(PostgreSQL\nCore + Read Models)]
        RPUB[Redis Stream Publishers]
        RCON[Redis Stream Consumers]
    end

    subgraph REDIS["Message Broker — Redis Streams"]
        R1[post-image-processing]
        R2[profile-picture-processing]
        R3[ml-insights-results]
        R4[face-detection-results]
        R5[face-recognition-results]
        R6[user-profile-face-embedding-results]
        R7[post-aggregation-trigger]
        R8[post-insights-enriched]
        R9[es-sync-queue]
        R10[ml-inference-tasks]
        R11[ai-processing-dlq]
        R12[federated-gradient-updates]
        R13[global-model-state]
        R14[privacy-audit-queue]
    end

    subgraph AI["kaleidoscope-ai — Python Workers"]
        MP[media_preprocessor]
        CM[content_moderation]
        IT[image_tagger]
        SR[scene_recognition]
        IC[image_captioning]
        FR[face_recognition]
        FM[face_matcher]
        PE[profile_enrollment]
        PA[post_aggregator]
        ES[es_sync]
        DLQ[dlq_processor]
        FA[federated_aggregator]
    end

    subgraph INFRA["Storage & Search"]
        ESI[(Elasticsearch 8.x\n7 Indices)]
        HF[HuggingFace\nInference API]
    end

    UI -- "HTTPS REST" --> CTRL
    CTRL --> SVC --> PG
    SVC --> RPUB

    RPUB --> R1
    RPUB --> R2
    RPUB --> R7
    RPUB --> R9
    RPUB --> R12

    R1 --> MP
    R1 --> CM
    R1 --> IT
    R1 --> SR
    R1 --> IC
    R1 --> FR

    MP --> R10
    CM --> R3
    IT --> R3
    SR --> R3
    IC --> R3
    FR --> R4

    R4 --> FM
    FM --> R5

    R2 --> PE
    PE --> R6

    R3 --> RCON
    R4 --> RCON
    R5 --> RCON
    R6 --> RCON
    R8 --> RCON

    RCON --> SVC

    R7 --> PA
    PA --> R8

    R9 --> ES
    ES --> ESI
    ES --> PG

    R11 --> DLQ
    DLQ --> R1

    R12 --> FA
    FA --> R13

    CM --> HF
    IT --> HF
    SR --> HF
    IC --> HF
    FR --> HF
    PE --> HF
```

---

## 2. Technology Stack by Layer

### Frontend

| Concern | Technology |
|---------|-----------|
| Framework | Next.js 14 (React 18, App Router) |
| Language | TypeScript |
| State Management | Redux Toolkit |
| HTTP Client | Axios with interceptors |
| Styling | Tailwind CSS |
| Media Upload | Cloudinary direct upload |

### Backend (Java — read-only from this repo)

| Concern | Technology |
|---------|-----------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| ORM | Spring Data JPA (Hibernate) |
| Database | PostgreSQL 15 |
| Caching / Messaging | Spring Data Redis (RedisTemplate, `XADD` / `XREADGROUP`) |
| Search | Spring Data Elasticsearch |
| Media CDN | Cloudinary |
| Port | 8080 |

### AI Microservices Layer (`kaleidoscope-ai`)

| Concern | Technology |
|---------|-----------|
| Language | Python 3.11+ |
| HTTP / Async API | FastAPI (health server) |
| Data Validation | Pydantic v2 (strict `BaseModel`) |
| Redis Client | `redis-py` |
| HTTP Client | `requests` (singleton session) |
| ML Inference | HuggingFace `InferenceClient` + direct HTTP |
| Logging | Structured JSON (`shared/utils/logger.py`) |
| Containerisation | Docker Compose — one process per service |

### Infrastructure

| Concern | Technology |
|---------|-----------|
| Message Broker | Redis 7 (Alpine) — AOF persistence |
| Search Engine | Elasticsearch 8.10.2 |
| Object Storage / CDN | Cloudinary |
| Container Runtime | Docker Compose |
| CI / CD | GitHub Actions → Docker Hub (`ajayprabhu2004/kaleidoscope`) |

---

## 3. Python Microservice Topology

> **Phase C note:** `consent_gateway` was retired and its `hasConsent` field removed from all Python DTOs. `media_preprocessor` now consumes directly from `post-image-processing`.

| Service | Consumes From | Produces To | Consumer Group |
|---------|--------------|-------------|----------------|
| `media_preprocessor` | `post-image-processing` | `ml-inference-tasks` | `media-preprocessor-group` |
| `content_moderation` | `post-image-processing` | `ml-insights-results` | `content-moderation-group` |
| `image_tagger` | `post-image-processing` | `ml-insights-results` | `image-tagger-group` |
| `scene_recognition` | `post-image-processing` | `ml-insights-results` | `scene-recognition-group` |
| `image_captioning` | `post-image-processing` | `ml-insights-results` | `image-captioning-group` |
| `face_recognition` | `post-image-processing` | `face-detection-results` | `face-recognition-group` |
| `face_matcher` | `face-detection-results` | `face-recognition-results` | `face-matcher-group` |
| `profile_enrollment` | `profile-picture-processing` | `user-profile-face-embedding-results` | `profile-enrollment-group` |
| `post_aggregator` | `post-aggregation-trigger` | `post-insights-enriched` | `post-aggregator-group` |
| `es_sync` | `es-sync-queue` | Elasticsearch (HTTP) | `es-sync-group` |
| `dlq_processor` | `ai-processing-dlq` | `post-image-processing` (retry) | `dlq-processor-group` |
| `federated_aggregator` | `federated-gradient-updates` | `global-model-state` | `federated-aggregator-group` |

**Fan-out pattern on `post-image-processing`:** Six independent consumer groups read from this single stream simultaneously, each with its own cursor. Every message is processed by all six services.

---

## 4. Active Redis Stream Inventory

All field values are UTF-8 strings. Arrays and objects are JSON-encoded strings. Booleans are `"true"` / `"false"`.

| Stream | Direction | Producer | Consumer(s) |
|--------|-----------|----------|------------|
| `post-image-processing` | Java → Python | Java backend | `media_preprocessor`, `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `face_recognition` |
| `profile-picture-processing` | Java → Python | Java backend | `profile_enrollment` |
| `post-aggregation-trigger` | Java → Python | Java backend / scheduler | `post_aggregator` |
| `es-sync-queue` | Java → Python | Java backend | `es_sync` |
| `federated-gradient-updates` | Edge → Python | Edge nodes | `federated_aggregator` |
| `ml-inference-tasks` | Python → Python | `media_preprocessor` | *(pending — see Tech Debt TD-1)* |
| `ml-insights-results` | Python → Java | `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning` | Java `MediaAiInsightsConsumer` |
| `face-detection-results` | Python → Python+Java | `face_recognition` | `face_matcher`, Java `FaceDetectionConsumer` |
| `face-recognition-results` | Python → Java | `face_matcher` | Java `FaceRecognitionConsumer` |
| `user-profile-face-embedding-results` | Python → Java | `profile_enrollment` | Java `UserProfileFaceEmbeddingConsumer` |
| `post-insights-enriched` | Python → Java | `post_aggregator` | Java `PostInsightsConsumer` |
| `ai-processing-dlq` | Python → Python | Any worker (on failure) | `dlq_processor` |
| `global-model-state` | Python → consumers | `federated_aggregator` | Edge nodes / model update consumers |
| `privacy-audit-queue` | Java → audit | Java backend | Audit / compliance consumers |

---

## 5. Elasticsearch Index Inventory

The `es_sync` worker reads from PostgreSQL read-model tables and indexes into Elasticsearch via the `es-sync-queue` message.

| Index Name | Primary Use | Key Fields | Vector Search |
|-----------|-------------|-----------|---------------|
| `media_search` | Per-image semantic search | `ai_caption`, `ai_tags[]`, `ai_scenes[]`, `is_safe`, `media_url` | `image_embedding` (1408-dim) |
| `post_search` | Post-level aggregated discovery | `all_ai_tags[]`, `inferred_event_type`, `combined_caption`, `total_faces` | — |
| `user_search` | User profile discovery | `username`, `department`, `bio` | — |
| `face_search` | Face search across posts | `detected_user_ids[]`, `bbox`, `confidence` | `face_embedding` (1408-dim) |
| `recommendations_knn` | Content-based recommendations | `post_id`, `tags`, `scenes` | `content_embedding` (KNN) |
| `feed_personalized` | Personalised feed ranking | `affinity_score`, `recency_score`, `user_id` | — |
| `known_faces_index` | Face enrollment / identification | `user_id`, `username`, `department`, `profile_pic_url`, `is_active` | `face_embedding` (1408-dim, cosine) |

**`known_faces_index` mapping highlights:**  
- `face_embedding`: `dense_vector`, `dims: 1408`, `similarity: cosine`, indexed for KNN  
- `is_active`: boolean filter applied at query time to exclude deactivated profiles

**Elasticsearch index domain ownership** — write authority is split between layers:

| Layer | Owns | Write Mechanism |
|-------|------|-----------------|
| Java (Spring Boot) | `post_search`, `user_search`, `media_search`, `blog_search` | `ElasticsearchStartupSyncService` (bulk on startup) + incremental Spring Data ES saves |
| Python `es_sync` | `face_search`, `recommendations_knn`, `feed_personalized`, `known_faces_index` | `es-sync-queue` consumer → reads PostgreSQL read-model → Elasticsearch bulk API |

Only the Python-owned indices are ever written by the `es_sync` worker. The Java-owned indices are managed exclusively by the Java Spring Boot layer. This split is enforced in `services/es_sync/worker.py` via `INDEX_MAPPING`.

---

## 6. Infrastructure Services

Defined in `docker-compose.yml`:

| Service | Image | Purpose | Ports |
|---------|-------|---------|-------|
| `redis` | `redis:alpine` | Message broker — all streams | 6379 |
| `elasticsearch` | `elasticsearch:8.10.2` | Full-text + vector search | 9200, 9300 |
| `app` | `ajayprabhu2004/kaleidoscope:backend-*` | Java Spring Boot backend | 8080 |

**Named volumes:**

| Volume | Service | Purpose |
|--------|---------|---------|
| `redis-data` | Redis | AOF write-ahead persistence |
| `es-data` | Elasticsearch | Index data |
| `./shared:/app/shared` | All Python workers | Live bind-mount of shared library |
| `./local_media_cache:/tmp/kaleidoscope_media` | `media_preprocessor` + ML workers | Shared downloaded image cache |

---

## 7. Shared Library Overview

All Python workers import from `shared/` via a bind-mount at `/app/shared`.

```
shared/
├── __init__.py               # Empty namespace
├── requirements.txt          # redis, pydantic, python-dotenv, psycopg2-binary, elasticsearch
├── redis_streams/
│   ├── publisher.py          # RedisStreamPublisher (XADD, pipeline batch)
│   ├── consumer.py           # RedisStreamConsumer (XREADGROUP, XACK, XCLAIM)
│   └── utils.py              # decode_message() — bytes→str + JSON parse
├── schemas/
│   ├── schemas.py            # Strict Pydantic v2 DTOs — Java contract mirrors
│   └── message_schemas.py    # Wire schemas + validate_incoming/validate_outgoing
├── providers/
│   ├── base.py               # Abstract base classes per AI task
│   ├── registry.py           # get_provider() factory + auto-register defaults
│   ├── types.py              # Result dataclasses (ModerationResult, TaggingResult, …)
│   └── huggingface/          # Concrete HF provider implementations
│       ├── moderation.py
│       ├── tagger.py
│       ├── scene.py
│       ├── captioning.py
│       └── face.py
└── utils/
    ├── circuit_breaker.py    # CircuitBreaker (CLOSED/OPEN/HALF_OPEN, 5 fail → OPEN 60 s)
    ├── health.py             # check_health() — metrics-threshold evaluation
    ├── health_server.py      # GET /health · /ready · /metrics on HEALTH_PORT (default 8080)
    ├── hf_inference.py       # InferenceClient + legacy HTTP helpers for HF API
    ├── http_client.py        # get_http_session() — singleton requests.Session
    ├── image_downloader.py   # download_image() with retry + exponential backoff
    ├── logger.py             # get_logger() — structured JSON output
    ├── metrics.py            # Thread-safe counters; p50/p95/p99 latency window
    ├── retry.py              # retry_with_backoff + publish_to_dlq()
    ├── secrets.py            # Docker Swarm secrets + env-var fallback
    └── url_validator.py      # validate_url() — scheme check + SSRF prevention
```

---

## 8. Provider Abstraction Layer

AI model calls are isolated behind abstract base classes in `shared/providers/base.py`. Each AI task has four components:

1. A **base class** (`BaseModerationProvider`, `BaseTaggingProvider`, etc.) with a mandatory `analyze()` / `tag()` / `detect()` method signature.
2. A **result dataclass** (`ModerationResult`, `TaggingResult`, `SceneResult`, `CaptionResult`, `FaceResult`) in `shared/providers/types.py`.
3. A **HuggingFace concrete implementation** in `shared/providers/huggingface/` for each task.
4. A **registry** (`shared/providers/registry.py`) that maps `(task, platform)` → class and caches singleton instances.

**Switching inference backends** requires only:
1. Setting `AI_PLATFORM=<platform>` (applies to all tasks) or `<TASK>_PLATFORM=<platform>` (per-task override).
2. Registering a new provider class via `ProviderRegistry.register(task, platform, cls)`.
3. No changes to any worker code.

**HuggingFace dual-mode support** (transparent to worker code):

| `HF_*_API_URL` value | Backend used |
|---------------------|-------------|
| A model ID (`org/model-name`) | `huggingface_hub.InferenceClient` (new Inference Providers API) |
| A full `https://` URL | Direct HTTP POST (HuggingFace Spaces or self-hosted) |

---

## 9. Health & Observability

Every Python worker exposes an HTTP health server on `HEALTH_PORT` (default `8080`). Set a unique port per service in `docker-compose.yml` to avoid conflicts:

| Endpoint | Probe Type | Behaviour |
|----------|-----------|-----------|
| `GET /health` | Liveness | Evaluates in-process metric thresholds; always returns 200 (body contains `"healthy"` / `"unhealthy"`) |
| `GET /ready` | Readiness | Returns 200 after consumer group creation and first successful consume; 503 before that |
| `GET /metrics` | Metrics | JSON object: `total_processed`, `success_count`, `failure_count`, `success_rate`, `retry_count`, `dlq_count`, latency percentiles |

**Health thresholds** (defined in `shared/utils/health.py`):

| Condition | State |
|-----------|-------|
| No messages in last 10 minutes | Unhealthy |
| Success rate below 50 % | Unhealthy |
| Average latency > 60 s | Unhealthy |
| Any messages in DLQ | Warning |

All log lines are structured JSON and include: `timestamp`, `level`, `logger`, `message`, `source` (file / line / function), `process`, and optional `extra` context. Compatible with Loki, CloudWatch, Datadog, and any JSON-log aggregator.

---

## 10. Security Model

| Concern | Implementation |
|---------|---------------|
| Consent enforcement | Handled upstream by the Java backend before events are published to Redis Streams; no Python service inspects a consent field |
| SSRF prevention | `validate_url()` in `shared/utils/url_validator.py` resolves the hostname and rejects private / loopback / link-local IPs before any download attempt |
| Image domain allowlist | `ALLOWED_IMAGE_DOMAINS` env var; defaults to `res.cloudinary.com`. Requests to unlisted domains are rejected with a logged warning |
| Redis auth | `requirepass` set in `docker-compose.yml`; all workers supply `REDIS_PASSWORD` via the env / Docker Swarm secret |
| Elasticsearch auth | Basic auth (`elastic` / `ELASTICSEARCH_PASSWORD`) injected into the `ES_HOST` URL at compose time |
| Secrets management | `get_secret()` in `shared/utils/secrets.py` — checks `/run/secrets/<name>` (Docker Swarm) before falling back to environment variables; never hard-codes credentials |
| HuggingFace token | Loaded exclusively via `get_secret("HF_API_TOKEN")` |
| Circuit breaker | `shared/utils/circuit_breaker.py` — 5 consecutive failures → OPEN state for 60 s; prevents cascade failures to HuggingFace or Elasticsearch |

---

## 11. Five-Phase Build History

A chronological record of how the `kaleidoscope-ai` layer was assembled. Useful context for understanding why certain services exist (or were retired).

### Phase 1 — Core Redis Stream Infrastructure
- Built `shared/redis_streams/` (`RedisStreamPublisher`, `RedisStreamConsumer`).
- Established consumer-group semantics: `XREADGROUP` + `XACK`, automatic group creation, pending-message reclaim via `XCLAIM`.
- Defined the canonical Pydantic DTOs in `shared/schemas/schemas.py` mirroring Java backend contracts.

### Phase 2 — Consent Enforcement (Retired Python Service)
- Originally housed `services/consent_gateway/worker.py` which routed events by a `hasConsent` flag.
- **Retired in Phase C:** Consent is now enforced upstream by the Java backend before any event reaches Redis Streams. The `consent_gateway` Python service has been deleted and the `hasConsent` field removed from all Python DTOs (`PostImageEventDTO` GAP-6 fix). No Python worker inspects consent headers.

### Phase 3 — ML Inference Workers (Fan-Out Pattern)
- Built five parallel inference workers, each operating as an independent consumer group on `post-image-processing`:
  - `content_moderation` — NSFW/safety classification via HuggingFace.
  - `image_tagger` — Zero-shot semantic tagging.
  - `scene_recognition` — Zero-shot scene classification.
  - `image_captioning` — Image-to-text captioning.
  - `face_recognition` — Face detection + embedding extraction.
- Built `shared/providers/` abstraction layer so inference backends are swappable via `AI_PLATFORM` env var (see Section 8).

### Phase 4 — Aggregation, Persistence & Resilience
- Built `services/post_aggregator/worker.py`: waits for all media in a post to complete ML processing, then publishes a merged `PostInsightsEnrichedMessage` to `post-insights-enriched`.
- Built `services/es_sync/worker.py`: consumes `es-sync-queue` and writes structured documents to Elasticsearch 8.x (ML/vector indices only — see Section 5 domain ownership).
- Built `services/dlq_processor/worker.py`: monitors `ai-processing-dlq`; supports configurable auto-retry via `DLQ_AUTO_RETRY` env var.
- Added circuit breaker, exponential-backoff retry, SSRF-prevention URL validation, and Docker-secrets-aware secret loading to `shared/utils/`.

### Phase 5 — Media Pre-processing & Federated Learning
- Built `services/media_preprocessor/worker.py`: downloads images from Cloudinary URLs to a shared Docker volume (`/tmp/kaleidoscope_media`), then publishes `LocalMediaEventDTO` to `ml-inference-tasks` to avoid redundant network fetches by downstream ML workers.

  > **Note (TD-1):** The migration is half-complete — ML workers still consume from `post-image-processing` and download images independently. See `audit_report_and_tech_debt.md` § Python Internal Tech Debt.

- Built `services/federated_aggregator/worker.py`: averages gradient payloads from edge nodes (`federated-gradient-updates`) and publishes global model state to `global-model-state`.
- Built the face auto-tagging pipeline:
  - `profile_enrollment`: extracts 1408-dim face embeddings from profile pictures (Vertex multimodal, same as post face crops) and routes them to Java via `user-profile-face-embedding-results` (GAP-2 fix — was incorrectly publishing to `es-sync-queue`).
  - `face_matcher`: runs KNN searches against `known_faces_index` in Elasticsearch for each detected face and publishes matches to `face-recognition-results` (GAP-1/GAP-3 fix — was publishing to the non-existent `face-tag-suggestions` stream).
