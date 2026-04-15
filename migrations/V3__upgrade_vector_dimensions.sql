-- V3: Upgrade VECTOR dimensions from 512 to 1408 to match Vertex AI multimodal embeddings.
--
-- Background: V1 created image_embedding as VECTOR(512) (legacy CLIP size).
-- The production embedding model (multimodalembedding@001) outputs 1408 dimensions.
-- PostgreSQL/pgvector enforces exact dimension matching on INSERT, so the Java backend
-- silently fails to persist embeddings, leaving image_embedding NULL and causing the
-- read_model_recommendations_knn row to never be created.
--
-- Strategy: DROP + ADD is required because ALTER COLUMN TYPE is not supported for
-- vector columns in pgvector. Existing NULL rows are unaffected.

-- ---- media_ai_insights ----
ALTER TABLE media_ai_insights
    DROP COLUMN IF EXISTS image_embedding;

ALTER TABLE media_ai_insights
    ADD COLUMN image_embedding VECTOR(1408);

-- ---- read_model_recommendations_knn ----
ALTER TABLE read_model_recommendations_knn
    DROP COLUMN IF EXISTS image_embedding;

ALTER TABLE read_model_recommendations_knn
    ADD COLUMN image_embedding VECTOR(1408);
