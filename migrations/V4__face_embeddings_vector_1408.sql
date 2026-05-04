-- V4: Face embedding columns VECTOR(1408) for Vertex AI multimodalembedding@001
-- (face crops use the same multimodal embedding model as post images → 1408 dims).
--
-- Destructive: removes all stored face vectors so column types can be resized.
-- Repopulate via new posts, profile re-enrollment, and es_sync as applicable.

DELETE FROM read_model_face_search;
DELETE FROM media_detected_faces;
DELETE FROM read_model_known_faces;

ALTER TABLE media_detected_faces
    ALTER COLUMN embedding TYPE vector(1408)
    USING embedding::text::vector(1408);

ALTER TABLE read_model_face_search
    ALTER COLUMN face_embedding TYPE vector(1408)
    USING face_embedding::text::vector(1408);

ALTER TABLE read_model_known_faces
    ALTER COLUMN face_embedding TYPE vector(1408)
    USING face_embedding::text::vector(1408);
