SELECT media_id, post_id, (ai_caption IS NOT NULL) AS has_ai_caption, (image_embedding IS NOT NULL) AS has_embedding, (ai_tags IS NOT NULL) AS has_tags
FROM read_model_media_search WHERE media_id = 2;

SELECT post_id, title, inferred_event_type, (all_ai_tags IS NOT NULL) AS has_tags
FROM read_model_post_search WHERE post_id = 2;
