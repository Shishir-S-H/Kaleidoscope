# Handoff: local backend work + pipeline fixes (April 2026)

This document is for a teammate who has push access to the **Kaleidoscope** backend repo (`nrashmi06/Kaleidoscope`). The machine that did this work could not push to that remote (403 as a different GitHub user). After syncing with upstream, **two commits remain only on this clone** until someone pushes them or applies the patches below.

---

## 1. What was done on the Kaleidoscope (Java) repo

### 1.1 Sync with upstream

- Fetched `origin/main` and **rebased** local work onto the latest upstream tip (includes merge PR #103 / `57038a0` and follow-ups).
- Working tree was already clean; **`git stash` reported nothing to save** (no uncommitted edits at stash time).

### 1.2 Commits still ahead of `origin/main` (must land on shared `main`)

Run from `Kaleidoscope/`:

```bash
git log --oneline origin/main..HEAD
```

Expected (subject lines may match exactly):

| Order | Commit   | Summary |
|-------|----------|---------|
| 1     | `3b71c80` | `fix: guard recommendations_knn ES sync and improve KNN error logging` |
| 2     | `2bc701d` | `fix(async): prevent face pipeline failures from concurrent MediaAiInsights updates` |

**What `2bc701d` changes (high level)**

- **`FaceDetectionConsumer`**: Persist detected faces in one transaction; append `face_detection` to `media_ai_insights.services_completed` in **separate** short transactions with **retries on optimistic lock conflicts**, so concurrent `MediaAiInsightsConsumer` updates no longer roll back face rows or stall `face-detection-results` processing.
- **`PostAggregationTriggerService`**: Adds a **DB-backed `mediaInsights` JSON** payload on `post-aggregation-trigger` so the Python `post_aggregator` does not depend on re-reading already-ACKed `ml-insights-results` history (avoids stuck aggregation on retriggers).

**What `3b71c80` changes**

- Guards / logging around **recommendations_knn** Elasticsearch sync paths (reduces noisy failures when embeddings or index state are missing).

### 1.3 Applying the same changes without this clone

Patch files (generated after rebase) live in **this repo**:

`kaleidoscope-ai/documentation/handoff_backend_patches/`

- `0001-fix-guard-recommendations_knn-ES-sync-and-improve-KN.patch`
- `0002-fix-async-prevent-face-pipeline-failures-from-concur.patch`

On a clean `Kaleidoscope` checkout **at current `origin/main`**:

```bash
cd /path/to/Kaleidoscope
git fetch origin
git checkout main
git reset --hard origin/main
git am ../path/to/kaleidoscope-ai/documentation/handoff_backend_patches/*.patch
# resolve conflicts if any, then:
git push origin main
```

Alternatively cherry-pick by SHA if you add this machine as a remote:

```bash
git fetch <remote-name>
git cherry-pick 3b71c80 2bc701d
```

(After a force-push or re-clone, SHAs will differ; prefer **`git am` with the patch files** or cherry-pick from a remote that still has these commits.)

### 1.4 CI

- Pushing `main` on `Kaleidoscope` triggers `.github/workflows/backend-docker-build.yml` (paths: `backend/**`) and publishes `kaleidoscope:backend-latest` (per repo secrets).

---

## 2. Kaleidoscope AI repo (`kaleidoscope-ai`) — already on GitHub `main`

These are separate from the Java repo and were pushed by the same session:

| Commit     | Summary |
|------------|---------|
| `fcb5cfa9` | **`fix(es_sync): flush batched ES writes on Redis read idle`** — `RedisStreamConsumer` optional `idle_callback`; `es_sync` uses it so partial `face_search` batches flush when Redis `XREADGROUP` returns no new messages (fixes stuck last documents in ES). |

Earlier related commits on `main` include Vertex face dependency and deployment scripts (`9d9df283`, `cdbca1ff`, etc.).

---

## 3. Optional: local-only / ops scripts in `kaleidoscope-ai`

Several **diagnostic and one-off deployment helpers** were added under `scripts/deployment/` (PEL clears, post-specific inspectors, aggregator retriggers). They are intended for production debugging; review before committing. **Do not commit `.env`** (secrets).

---

## 4. Checklist for teammate

1. [ ] Pull or apply backend patches above; push `Kaleidoscope` `main`.
2. [ ] Confirm GitHub Actions backend image build succeeded.
3. [ ] On the droplet: `docker compose pull` and restart backend (or full stack per your runbook).
4. [ ] Smoke-test: new post with faces → `media_detected_faces`, `read_model_face_search`, `face_search` index, no `ObjectOptimisticLockingFailureException` in backend logs.

Questions: refer to `documentation/java_backend_handoff_google_migration.md` and recent `post_aggregator` / `es_sync` behavior in chat history.
