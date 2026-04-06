# Kaleidoscope AI — Architecture Reference

> **Last updated:** April 2026  
> **Scope:** `kaleidoscope-ai` Python microservices layer only.  
> The Java Spring backend (`Kaleidoscope/`) is read-only from this repo's perspective.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Five-Phase Build History](#2-five-phase-build-history)
3. [Microservice Topology](#3-microservice-topology)
4. [Redis Stream Contracts](#4-redis-stream-contracts)
5. [Shared Library Inventory](#5-shared-library-inventory)
6. [Infrastructure Services](#6-infrastructure-services)
7. [Provider Abstraction Layer](#7-provider-abstraction-layer)
8. [Health & Observability](#8-health--observability)
9. [Security Model](#9-security-model)
10. [Known Technical Debt](#10-known-technical-debt)

---

## 1. System Overview

Kaleidoscope AI is the event-driven AI processing layer that sits alongside a Java Spring backend. It communicates exclusively through **Redis Streams** — it neither exposes HTTP APIs to the backend nor calls it directly.

```
┌──────────────────────────────────────────────────────────────────┐
│                        EXTERNAL CLIENTS                          │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTPS
                        ┌───────▼────────┐
                        │  Java Backend  │  Spring Boot
                        │  (PostgreSQL,  │  port 8080
                        │  Elasticsearch)│
                        └───────┬────────┘
                                │ Redis Streams (XADD / XREADGROUP)
                                ▼
             ┌──────────────────────────────────────┐
             │         kaleidoscope-ai               │
             │   12 Python worker microservices      │
             │   + shared library (shared/)          │
             └──────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             Elasticsearch 8.x         HuggingFace
             (es_sync writes)          Inference API
                                       (ML workers)
```

All workers are single-process, long-running Python processes. They use `XREADGROUP` for at-least-once delivery and `XACK` only after successful processing. Failed messages accumulate in `ai-processing-dlq`.

---

## 2. Five-Phase Build History

### Phase 1 — Core Redis Stream Infrastructure
- Built `shared/redis_streams/` (`RedisStreamPublisher`, `RedisStreamConsumer`).
- Established consumer-group semantics: `XREADGROUP` + `XACK`, automatic group creation, pending-message reclaim via `XCLAIM`.
- Defined the canonical Pydantic DTOs in `shared/schemas/schemas.py` that mirror Java backend contracts.

### Phase 2 — Consent Enforcement (Retired Python Service)
- Originally housed `services/consent_gateway/worker.py` which routed events by `hasConsent` flag.
- **Retired:** Consent is now enforced upstream by the Java backend before any event reaches Redis Streams. The `consent_gateway` Python service has been deleted. No Python worker inspects `hasConsent`.

### Phase 3 — ML Inference Workers (Fan-Out Pattern)
- Built five parallel inference workers, each operating as an independent consumer group on `post-image-processing`:
  - `content_moderation` — NSFW/safety classification via HuggingFace.
  - `image_tagger` — Zero-shot semantic tagging.
  - `scene_recognition` — Zero-shot scene classification.
  - `image_captioning` — Image-to-text captioning.
  - `face_recognition` — Face detection + embedding extraction.
- Built `shared/providers/` abstraction layer so inference backends are swappable via `AI_PLATFORM` env var.

### Phase 4 — Aggregation, Persistence & Resilience
- Built `services/post_aggregator/worker.py`: reads from `ml-insights-results` + `face-detection-results`, waits for all media in a post to complete, then publishes a merged `PostInsightsEnrichedMessage` to `post-insights-enriched`.
- Built `services/es_sync/worker.py`: consumes `es-sync-queue` and writes structured documents to Elasticsearch 8.x.
- Built `services/dlq_processor/worker.py`: monitors `ai-processing-dlq`; supports configurable auto-retry (`DLQ_AUTO_RETRY` env var).
- Added circuit breaker (`shared/utils/circuit_breaker.py`), exponential-backoff retry decorator (`shared/utils/retry.py`), SSRF-prevention URL validation (`shared/utils/url_validator.py`), and Docker-secrets-aware secret loading (`shared/utils/secrets.py`).

### Phase 5 — Media Pre-processing & Federated Learning
- Built `services/media_preprocessor/worker.py`: downloads images from URLs to a shared Docker volume, then publishes `LocalMediaEventDTO` to `ml-inference-tasks` so downstream workers can avoid redundant network fetches.
- Built `services/federated_aggregator/worker.py`: averages gradient payloads from edge nodes (stream: `federated-gradient-updates`) and publishes global model state to `global-model-state`.
- Built face auto-tagging pipeline: `profile_enrollment` extracts 1024-dim HuggingFace face embeddings and routes them to Java via `user-profile-face-embedding-results`; `face_matcher` runs KNN searches against `known_faces_index` in Elasticsearch to suggest tags, publishing matches to `face-recognition-results`.

---

## 3. Microservice Topology

| Service | Consumes From | Produces To | Consumer Group |
|---------|--------------|-------------|----------------|
| `media_preprocessor` | `post-image-processing` | `ml-inference-tasks` | `media-preprocessor-group` |
| `content_moderation` | `post-image-processing` | `ml-insights-results` | `content-moderation-group` |
| `image_tagger` | `post-image-processing` | `ml-insights-results` | `image-tagger-group` |
| `scene_recognition` | `post-image-processing` | `ml-insights-results` | `scene-recognition-group` |
| `image_captioning` | `post-image-processing` | `ml-insights-results` | `image-captioning-group` |
| `face_recognition` | `post-image-processing` | `face-detection-results` | `face-recognition-group` |
| `profile_enrollment` | `profile-picture-processing` | `user-profile-face-embedding-results` | `profile-enrollment-group` |
| `face_matcher` | `face-detection-results` | `face-recognition-results` | `face-matcher-group` |
| `post_aggregator` | `post-aggregation-trigger` + reads `ml-insights-results` + `face-detection-results` | `post-insights-enriched` | `post-aggregator-group` |
| `es_sync` | `es-sync-queue` | Elasticsearch — ML/vector indices only (HTTP) | `es-sync-group` |
| `dlq_processor` | `ai-processing-dlq` | `post-image-processing` (retry) | `dlq-processor-group` |
| `federated_aggregator` | `federated-gradient-updates` | `global-model-state` | `federated-aggregator-group` |

---

## 4. Redis Stream Contracts

All field values are stored as UTF-8 strings. Lists and dicts are JSON-encoded. Booleans are `"true"` / `"false"`.

### `post-image-processing`
Entry point. Published by the Java backend. Java enforces consent before publishing — all events on this stream have implicit consent.

| Field | Type | Description |
|-------|------|-------------|
| `mediaId` | string | Unique media asset ID |
| `postId` | string | Owning post ID |
| `mediaUrl` | string | Publicly accessible image URL |
| `correlationId` | string | End-to-end trace identifier |
| `version` | string (optional) | Schema version |

Pydantic schema: `PostImageProcessingMessage` (`shared/schemas/message_schemas.py`)  
Strict DTO (Java contract): `PostImageEventDTO` (`shared/schemas/schemas.py`)

---

### `ml-inference-tasks`
Published by `media_preprocessor` after downloading the image to the shared volume.

| Field | Type | Description |
|-------|------|-------------|
| `mediaId` | string | Unique media asset ID |
| `localFilePath` | string | Absolute path to the downloaded image on the shared volume |
| `correlationId` | string | Echoed correlation ID |

Strict DTO: `LocalMediaEventDTO` (`shared/schemas/schemas.py`)

> ⚠️ **Note:** No ML inference worker currently consumes from this stream. See [Technical Debt §10](#10-known-technical-debt).

---

### `ml-insights-results`
Published by `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`.

| Field | Type | Description |
|-------|------|-------------|
| `mediaId` | string | Media asset ID |
| `postId` | string | Owning post ID |
| `service` | string | Originating service name |
| `timestamp` | string | ISO-8601 timestamp |
| `version` | string | Schema version (default `"1"`) |
| `isSafe` | string (optional) | `"true"\|"false"` — from moderation |
| `moderationConfidence` | string (optional) | Float string |
| `tags` | string (optional) | JSON-encoded `List[str]` |
| `scenes` | string (optional) | JSON-encoded `List[str]` |
| `caption` | string (optional) | Natural language caption |

Pydantic schema: `MLInsightsResultMessage`

---

### `face-detection-results`
Published by `face_recognition`.

| Field | Type | Description |
|-------|------|-------------|
| `mediaId` | string | Media asset ID |
| `postId` | string | Owning post ID |
| `facesDetected` | string | Integer count |
| `faces` | string | JSON-encoded list of face objects (bbox, embedding, confidence) |
| `timestamp` | string | ISO-8601 timestamp |
| `version` | string | Schema version (default `"1"`) |

Pydantic schema: `FaceDetectionResultMessage`

---

### `post-aggregation-trigger`
Trigger published (typically by the Java backend or a scheduler) to initiate post-level aggregation.

| Field | Type | Description |
|-------|------|-------------|
| `postId` | string | Post to aggregate |
| `mediaInsights` | string | JSON-encoded pre-fetched insights (optional) |
| `allMediaIds` | string | JSON-encoded list of expected media IDs |
| `totalMedia` | string | Integer count of expected media items |
| `correlationId` | string (optional) | Trace ID |

Pydantic schema: `PostAggregationTriggerMessage`

---

### `post-insights-enriched`
Published by `post_aggregator`. Consumed downstream (e.g., by `es-sync-queue` indirectly, or directly by the Java backend).

| Field | Type | Description |
|-------|------|-------------|
| `postId` | string | Post ID |
| `mediaCount` | string | Integer |
| `allAiTags` | string | JSON-encoded all tags across media |
| `allAiScenes` | string | JSON-encoded all scenes |
| `aggregatedTags` | string | JSON-encoded deduplicated top tags |
| `aggregatedScenes` | string | JSON-encoded deduplicated top scenes |
| `totalFaces` | string | Integer |
| `isSafe` | string | `"true"\|"false"` — aggregate safety verdict |
| `moderationConfidence` | string | Float string |
| `inferredEventType` | string | Inferred event category |
| `combinedCaption` | string | Merged caption |
| `hasMultipleImages` | string | `"true"\|"false"` |
| `timestamp` | string | ISO-8601 |
| `correlationId` | string | Trace ID |
| `version` | string | Schema version (default `"1"`) |

Pydantic schema: `PostInsightsEnrichedMessage`

---

### `es-sync-queue`
Published by the Java backend to trigger Elasticsearch indexing of ML/vector indices.

**Domain ownership — strictly enforced:**
- **Python `es_sync` owns:** `face_search`, `recommendations_knn`, `feed_personalized`, `known_faces_index`
- **Java owns directly** (Spring Data ES, startup sync): `post_search`, `user_search`, `media_search`, `blog_search`

Java only publishes `face_search` events to this queue; the other three ML indices receive events from their respective AI pipeline results.

| Field | Type | Description |
|-------|------|-------------|
| `indexType` | string | Target ML index name (see ownership table above) |
| `documentId` | string | Document ID |
| `operation` | string | `"index"` \| `"delete"` (default `"index"`) |

Pydantic schema: `ESSyncEventMessage`

---

### `ai-processing-dlq`
Poison-message queue. Written by any worker after exhausting retries.

| Field | Type | Description |
|-------|------|-------------|
| `originalMessageId` | string | Redis message ID of the failed message |
| `serviceName` | string | Worker that failed |
| `error` | string | Error message |
| `errorType` | string | Exception class name |
| `retryCount` | string | Integer |
| `timestamp` | string | Unix timestamp string |
| `version` | string | `"1"` |

Pydantic schema: `DLQMessage`

---

### `federated-gradient-updates`
Published by edge nodes.

| Field | Type | Description |
|-------|------|-------------|
| `nodeId` | string | Edge node identifier |
| `modelName` | string | Model name/version |
| `gradientPayload` | string | JSON-encoded `List[float]` |
| `correlationId` | string | Trace ID |

Strict DTO: `ModelUpdateEventDTO`

---

### `global-model-state`
Published by `federated_aggregator` after averaging gradients.

| Field | Type | Description |
|-------|------|-------------|
| `modelName` | string | Model name/version |
| `aggregatedGradients` | string | JSON-encoded averaged `List[float]` |
| `nodeCount` | string | Number of nodes contributing |
| `correlationId` | string | Trace ID |
| `timestamp` | string | ISO-8601 |

---

## 5. Shared Library Inventory

All code under `shared/` is mounted into every service container at build time.

```
shared/
├── __init__.py               # Empty namespace (no public re-exports)
├── requirements.txt          # redis, pydantic, python-dotenv, psycopg2-binary, elasticsearch
├── redis_streams/
│   ├── publisher.py          # RedisStreamPublisher (XADD, pipeline batch)
│   ├── consumer.py           # RedisStreamConsumer (XREADGROUP, XACK, XCLAIM)
│   └── utils.py              # decode_message() — bytes→str, JSON parse
├── schemas/
│   ├── schemas.py            # Strict Pydantic v2 DTOs mirroring Java contracts
│   └── message_schemas.py    # Loose wire schemas + validate_incoming/validate_outgoing
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
    ├── circuit_breaker.py    # CircuitBreaker (CLOSED/OPEN/HALF_OPEN, thread-safe)
    ├── health.py             # check_health() — metrics-driven health evaluation
    ├── health_server.py      # HTTP health server (/health, /ready, /metrics)
    ├── hf_inference.py       # InferenceClient + legacy HTTP helpers for HF API
    ├── http_client.py        # get_http_session() — singleton requests.Session
    ├── image_downloader.py   # download_image() with retry + exponential backoff
    ├── logger.py             # get_logger() — structured JSON logging
    ├── metrics.py            # Thread-safe in-process metrics counters + get_metrics()
    ├── retry.py              # retry_with_backoff decorator + publish_to_dlq()
    ├── secrets.py            # get_secret() — Docker Swarm secrets + env fallback
    └── url_validator.py      # validate_url() — scheme check + SSRF prevention
```

---

## 6. Infrastructure Services

Defined in `docker-compose.yml`:

| Service | Image | Purpose |
|---------|-------|---------|
| `redis` | `redis:alpine` | Message broker — all streams live here |
| `elasticsearch` | `elasticsearch:8.10.2` | Full-text + vector search |
| `app` | `ajayprabhu2004/kaleidoscope:backend-*` | Java Spring Boot backend |

**Volumes:**
- `redis-data` — Redis AOF persistence
- `es-data` — Elasticsearch index data

**Elasticsearch Index Domain Ownership:**

| Layer | Owns | Mechanism |
|-------|------|-----------|
| Java (Spring Boot) | `post_search`, `user_search`, `media_search`, `blog_search` | `ElasticsearchStartupSyncService` (bulk on boot) + incremental Spring Data ES saves |
| Python `es_sync` | `face_search`, `recommendations_knn`, `feed_personalized`, `known_faces_index` | Redis Stream `es-sync-queue` consumer → PostgreSQL read models → ES bulk API |

**Shared mount pattern (ML workers):**  
`./shared:/app/shared` — the shared library is bind-mounted so changes are live in dev without rebuilding.

**Phase 2–5 workers** use `context: .` builds so they can import `shared/` from the repo root.

---

## 7. Provider Abstraction Layer

AI model calls are isolated behind abstract base classes in `shared/providers/base.py`. Each task (moderation, tagging, scene, captioning, face) has:

1. A **base class** (`BaseModerationProvider`, etc.) with a mandatory `analyze()`/`tag()`/etc. method.
2. A **result dataclass** (`ModerationResult`, `TaggingResult`, etc.) in `shared/providers/types.py`.
3. A **HuggingFace concrete implementation** in `shared/providers/huggingface/`.
4. A **registry** (`shared/providers/registry.py`) that maps `(task, platform)` → class and caches instances.

**Switching inference platforms** requires only setting `AI_PLATFORM=<platform>` (or `<TASK>_PLATFORM` for per-task override) and registering a new provider class via `ProviderRegistry.register()`.

HuggingFace providers support two backends transparently:
- **InferenceClient** (new Inference Providers API) — when `HF_*_API_URL` is a model ID (e.g. `org/model`).
- **HTTP / HF Spaces** — when `HF_*_API_URL` is a full `https://` URL.

---

## 8. Health & Observability

Every worker runs a lightweight HTTP health server on port `8080` (configurable via `HEALTH_PORT`):

| Endpoint | Purpose | Success code |
|----------|---------|-------------|
| `GET /health` | Liveness probe — evaluates metrics thresholds | 200 always (body contains status) |
| `GET /ready` | Readiness probe — true after group create + first consume | 200 ready / 503 not-ready |
| `GET /metrics` | In-process metrics JSON | 200 |

Health thresholds (`shared/utils/health.py`):
- Unhealthy if no messages processed in last **10 minutes**
- Unhealthy if success rate drops below **50%**
- Unhealthy if average latency exceeds **60 seconds**
- Warning if any messages are in the DLQ

Metrics tracked per-service (in-process, thread-safe):
- `total_processed`, `success_count`, `failure_count`, `success_rate`
- `retry_count`, `dlq_count`
- Latency percentiles: p50, p95, p99 (sliding window of last 1,000 messages)

Structured JSON logging via `shared/utils/logger.py` — all log lines include `timestamp`, `level`, `logger`, `message`, `source` (file/line/function), `process`, and optional `extra` context dict. Compatible with any JSON log aggregator (Loki, CloudWatch, Datadog, etc.).

---

## 9. Security Model

| Concern | Implementation |
|---------|---------------|
| Consent enforcement | Handled upstream by the Java backend before events are published to Redis Streams; no Python service inspects consent headers |
| SSRF prevention | `validate_url()` checks scheme + resolves hostname to block private/loopback IPs |
| Domain allowlist | `ALLOWED_IMAGE_DOMAINS` env var; defaults to `res.cloudinary.com` |
| Redis auth | `requirepass` + `REDIS_PASSWORD` injected at compose time |
| Elasticsearch auth | Basic auth via `ELASTICSEARCH_PASSWORD` |
| Secrets management | `get_secret()` checks `/run/secrets/<name>` (Docker Swarm) before env vars |
| HuggingFace token | Loaded via `get_secret("HF_API_TOKEN")` |
| Circuit breaker | Prevents cascade failure to external APIs (5 failures → OPEN for 60 s) |

---

## 10. Technical Debt & Future Work

### TD-1 — Incomplete `ml-inference-tasks` Migration ⚠️ HIGH PRIORITY

**Status:** Open  
**Phase introduced:** Phase 5  
**Location:** `services/media_preprocessor/worker.py` and all five ML inference workers (`content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `face_recognition`)

**Description:**  
The `media_preprocessor` service was built to eliminate redundant network fetches by downloading each image once to a shared Docker volume (`/tmp/kaleidoscope_media`) and publishing a `LocalMediaEventDTO` to `ml-inference-tasks`. The intent was for downstream ML workers to read the file from disk instead of independently fetching the same URL from Cloudinary.

**However, the migration was only half-completed:**
- ✅ `media_preprocessor` downloads images and publishes `LocalMediaEventDTO` to `ml-inference-tasks`
- ❌ All five ML inference workers still consume from `post-image-processing` and download images independently from the original URL

**Impact:**
- Every media item triggers **5 redundant Cloudinary fetches** (one per ML worker)
- Additional HuggingFace round-trips carry the same bytes repeatedly
- The `ml-inference-tasks` stream accumulates messages with no consumer — it is effectively a queue that fills and is never drained

**Resolution path:**
1. Update each ML worker's `STREAM_INPUT` constant from `"post-image-processing"` to `"ml-inference-tasks"`
2. Replace URL-download logic with a local `open(localFilePath, "rb").read()` call
3. Update the `CONSUMER_GROUP` constants accordingly
4. Verify the shared volume mount (`./local_media_cache:/tmp/kaleidoscope_media`) is present for each ML worker in `docker-compose.yml`

---

### Resolved Debt

| ID | Severity | Description | Resolution |
|----|---------|-------------|------------|
| ~~TD-2~~ | Medium | `shared/__init__.py` imported from non-existent `shared.models`, silently failing on every startup | **Deleted** — replaced with a minimal namespace comment (April 2026) |
| ~~TD-3~~ | Medium | `shared/utils/worker_base.py` (`BaseWorker`) and `shared/utils/prometheus_exporter.py` were defined but never imported | **Deleted** both files (April 2026) |
| ~~TD-4~~ | Medium | `shared/db/models.py` contained SQLAlchemy ORM models never imported anywhere; `pgvector` not in any `requirements.txt` | **Deleted** file and `shared/db/` directory (April 2026) |
| ~~TD-5~~ | Low | `shared/utils/metrics.py` — `ProcessingTimer` class and `record_retry()` were never called | **Deleted** both symbols (April 2026) |
| ~~TD-6~~ | Low | `shared/redis_streams/utils.py` — `encode_message()` was never imported | **Deleted** function (April 2026) |
| ~~TD-7~~ | Low | `scripts/setup/setup_es_indices.py` `MAPPINGS_DIR` resolved to `scripts/es_mappings` (nonexistent) instead of repo root `es_mappings/` | **Fixed** path to `Path(__file__).resolve().parents[2] / "es_mappings"` (April 2026) |
| ~~TD-8~~ | Low | `docker-compose.yml` declared volumes `pgdata`, `minio_data`, `pgadmin_data` whose services were commented out | **Deleted** all three orphaned volume declarations (April 2026) |
| ~~TD-11~~ | Medium | `services/es_sync/worker.py` `INDEX_MAPPING` contained `post_search`, `user_search`, `media_search` — indices owned and managed by the Java layer — causing ambiguous write ownership | **Removed** from Python `INDEX_MAPPING`; Python es_sync now exclusively owns ML/vector indices (April 2026) |
| ~~TD-12~~ | Low | `services/es_sync/worker.py` contained a dead `documentData` direct-embed branch from the retired `profile_enrollment → es-sync-queue` path (GAP-2 fix routed profile enrollment to Java instead) | **Removed** unreachable branch (April 2026) |
| ~~TD-13~~ | Low | `services/edge-media/` (`ConsentMiddleware`) was a Starlette service not present in any compose file; consent is Java's responsibility | **Deleted** directory (April 2026) |

---

### Remaining Open Items

| ID | Severity | Description | Location |
|----|---------|-------------|----------|
| TD-1 | High | All five ML inference workers still consume from `post-image-processing` and download images independently, ignoring `ml-inference-tasks`; see full description above | `services/{content_moderation,image_tagger,scene_recognition,image_captioning,face_recognition}/worker.py` |
| TD-9 | Low | The trigger source for `post-aggregation-trigger` stream is not in this repo — believed to originate from the Java backend or a scheduler external to this layer | `services/post_aggregator/worker.py` |
| TD-10 | Low | `shared/utils/logger.py` uses `datetime.utcnow()` which is deprecated in Python 3.12+; should migrate to `datetime.now(datetime.UTC)` | `shared/utils/logger.py` line 34 |
