# Backend handoff: pipeline fixes (May 2026, inc. production **Test-24** / post_id **35**)

This document consolidates **Java `Kaleidoscope` backend** work items for whoever owns merges and **`backend-latest` Docker** deploys. It incorporates prior handoff notes (**1408 face dims**, **Hikari**, **patches**) and **new evidence** from live monitoring on **`165.232.179.167`** (`2026-05-04`).

Companion AI repo (**`kaleidoscope-ai`**) notes: **`es_sync` PG retries** are already on `main`; optional items are listed at the end. Ops verification improvements may land as **`scripts/deployment/verify_post_pipeline.py`** updates in this repo.

---

## 1. Incident summary (**Test-24**, `post_id=35`)

| Observation | Meaning |
|-------------|---------|
| `PostProcessingStatusService` never satisfied | Logs: **“PostId: 35 is still processing other media. Aggregation not triggered.”** despite **single** media — gate is **`services_completed` in SQL**, not “number of attachments”. |
| `ObjectOptimisticLockingFailureException` | **`MediaAiInsights#35`** failed while finishing **`image_captioning`**; message **left in Redis PEL**; **`media_ai_insights.caption`** stayed **null**. |
| **`read_model_post_search`**: 0 rows | No aggregated post-level read model. |
| **`post_search/_doc/35`**: `found: false`** | **`post_aggregator`** had **no** log line for **`post_id` 35** — trigger never published. |
| **`media_search`**: `detectedFaceCount: 0`** | **4** rows in **`media_detected_faces`** — ES document not refreshed after faces (backend indexing). |

**Root cause chain (technical):**

1. Concurrent updates on **`MediaAiInsights`** (**`MediaAiInsightsConsumer`** vs **`FaceDetectionConsumer`**) caused **lost / stuck** **`image_captioning`** completion.
2. **`MediaAiInsightsRepository.countFullyProcessedByPostId`** requires  
   **`services_completed @> ARRAY['moderation','tagging','scene_recognition','image_captioning']`**  
   Until all four are present on **every** medium for the post, **`allMediaProcessedForPost`** stays **false** → **no** **`post-aggregation-trigger`** → **no** **`read_model_post_search`** / **`post_search`** aggregated doc.

```30:35:Kaleidoscope/backend/src/main/java/com/kaleidoscope/backend/posts/repository/MediaAiInsightsRepository.java
    @Query(value = """
            SELECT COUNT(*) FROM media_ai_insights
            WHERE post_id = :postId
              AND services_completed @> ARRAY['moderation','tagging','scene_recognition','image_captioning']
            """, nativeQuery = true)
    long countFullyProcessedByPostId(@Param("postId") Long postId);
```

3. **`FaceDetectionConsumer`** **`face_detection`** is **not** part of this array (may be intentional). Decide explicitly whether aggregation should wait for faces before **`post_search`** totals (`totalFaces`).

---

## 2. Priority backlog (backend only)

### P0 — Database pool (Neon + concurrent consumers)

**File:** `backend/src/main/resources/application.yml`

- Raise **`spring.datasource.hikari.maximum-pool-size`** from **2** toward **10–20** (subject to Neon pooler tier).
- Set sensible **`minimum-idle`** so **`MediaAiInsightsConsumer`**, **`FaceDetectionConsumer`**, and HTTP traffic do not contend into **timeouts** / **SSL disconnects** seen by **`es_sync`**.

---

### P0 — **`MediaAiInsights` concurrency (caption / PEL)**

**Files:** **`MediaAiInsightsConsumer`**, **`FaceDetectionConsumer`**, **`ReadModelUpdateService`** (as needed)

- Eliminate **`ObjectOptimisticLockingFailureException`** when **caption**, **tags**, **faces**, and **`services_completed`** updates overlap:
  - Short transactions; **reload + merge + save** with **bounded retries** on optimistic lock (pattern already partly used on **`FaceDetectionConsumer`**).
  - Optionally **defer** heavy read-model / ES writes to **after** the core **`MediaAiInsights`** row is stable, or use **serialized** updates per **`media_id`** where practical.
- On **recoverable** lock failure: **retry** or **explicit reclaim** strategy; avoid leaving **`ml-insights-results`** entries **forever** in PEL without a DLQ/alarm.

**Reference patches (may already exist on a clone; apply via `documentation/handoff_backend_patches/` in `kaleidoscope-ai`):**

- `0002-fix-async-prevent-face-pipeline-failures-from-concur.patch` — face pipeline vs concurrent insights.

---

### P0 — Face / Elasticsearch **dimensions 1408** (PG + ES alignment)

**Still required** on **`main`** for several entities/docs (PG **V4** + Vertex **`multimodalembedding@001`**):

| Area | Files (see **`handoff_teammate_java_kaleidoscope_repo.md` § B2**) |
|------|---------------------------------------------------------------------|
| JPA **`vector(1024)`** | **`MediaDetectedFace`**, **`UserFaceEmbedding`**, etc. → **`1408`** |
| Spring Data ES **`@Field` dims** | **`UserDocument`**, **`MediaDetectedFaceDocument`**, profile docs |

Also validate **`FaceSearchReadModel`** **TEXT vs pgvector** mapping for Hibernate.

---

### P1 — Aggregation gate vs product semantics

**Files:** **`PostProcessingStatusService`**, **`MediaAiInsightsRepository`** ( **`countFullyProcessedByPostId`** query ), possibly config

- Document the **canonical** list of services that must finish before **`post-aggregation-trigger`**.
- Decide whether to require **`image_embedding`** and/or **`face_detection`** before aggregation (today: **SQL does not** require **`image_embedding`** by name — only caption/scene/tag/moderation).
- If **`image_embedding`** must block aggregation, extend the **`ARRAY[...]`** predicate accordingly (and ensure Python workers emit the matching **`service`** string).

---

### P1 — **`media_search`** **face count** and consistency

**Files:** **`MediaAiInsightsConsumer`**, **`FaceDetectionConsumer`**, **`MediaSearchDocument`** mapping

- After **`media_detected_faces`** stabilize (or after **`FaceDetectionConsumer`** completes), **re-save** **`media_search`** so **`detectedFaceCount`** matches **`COUNT(media_detected_faces)`**.
- Optionally refresh when **`FaceMatcher`** updates identification (if product exposes that in **`media_search`**).

---

### P1 — **`PostAggregationTriggerService` payload**

**Already improved in patch narrative** (`handoff_backend_teammate.md`): include **`mediaInsights`** JSON so **`post_aggregator`** does not depend on re-reading ACKed stream history after retries.

Ensure this commit is **on** the deployed **`backend-latest`** used in production.

---

### P2 — Operational follow-ups after deploy

- **Replay / fix** Redis PEL messages stuck after **`StaleObjectStateException`** (per **`messageId`** in logs).
- **One-off** for broken posts: re-publish **`post-aggregation-trigger`** or run a guarded repair job once concurrency fixes are deployed.
- Run **`verify_post_pipeline.py`** (updated in **`kaleidoscope-ai`**) against a needle title — checks **`post_search/_doc/{post_id}`**, **`services_completed`**, and ES vs PG face counts.

---

## 3. Patches / cross-repo pointers

| Resource | Purpose |
|----------|---------|
| `kaleidoscope-ai/documentation/handoff_backend_teammate.md` | Patch files **`0001`**, **`0002`**, **`git am`** instructions |
| `kaleidoscope-ai/documentation/handoff_teammate_java_kaleidoscope_repo.md` | **B2** entity list, **B3** Hikari, **B4** aggregation |
| `kaleidoscope-ai/documentation/handoff_backend_fixes_team_may2026.md` | **This file** — consolidated backend checklist + **Test-24** RCA |

---

## 4. AI services (`kaleidoscope-ai`) — scope for Python team

| Item | Action |
|------|--------|
| **`post_aggregator`** | **No change required for Test-24** — it never received a trigger for `post_id=35`. Validate again after backend publishes **`post-aggregation-trigger`** consistently. |
| **`es_sync`** | **Retries** **`ES_SYNC_PG_READ_*`** are on `main`. Redeploy image if prod lags behind. |
| **`dlq_processor`** | Optional: health logs when idle (**P3** — cosmetic). |
| **Verification** | Use updated **`verify_post_pipeline.py`** to catch missing **`post_search`** docs and **`detectedFaceCount`** mismatches early. |

---

## 5. Verification checklist (post-fix)

1. New post with **image + faces**, title needle e.g. **`Test-{n}`**.
2. PostgreSQL: **`media_ai_insights.services_completed`** contains required services; **`caption`** populated when captioning succeeds.
3. **`read_model_post_search`** row present; **`post_search/_doc/{post_id}`** **found**.
4. **`media_search`**: **`detectedFaceCount`** equals face row count for that media.
5. Backend logs: **no** repeated optimistic lock errors; **no** stuck PEL for **`ml-insights-results`** without alerting.

---

## 6. Document history

| Date | Notes |
|------|-------|
| 2026-05-04 | Created from production monitoring (**Test-24**) + merge of earlier handoff items. |
