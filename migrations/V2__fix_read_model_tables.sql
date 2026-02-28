-- V2: Rename existing read model tables to match es_sync service expectations
-- and create missing read model tables required by the backend + es_sync.

-- ==== RENAME EXISTING TABLES ====

ALTER TABLE IF EXISTS read_model_search RENAME TO read_model_media_search;
ALTER TABLE IF EXISTS read_model_recommendations RENAME TO read_model_recommendations_knn;
ALTER TABLE IF EXISTS read_model_feed RENAME TO read_model_feed_personalized;
ALTER TABLE IF EXISTS read_model_user_profiles RENAME TO read_model_user_search;

-- Rename columns in read_model_media_search to match backend write expectations
ALTER TABLE read_model_media_search
    RENAME COLUMN last_updated TO updated_at;

-- Add missing columns to read_model_media_search
ALTER TABLE read_model_media_search
    ADD COLUMN IF NOT EXISTS uploader_id INTEGER REFERENCES users(user_id),
    ADD COLUMN IF NOT EXISTS uploader_username VARCHAR(100),
    ADD COLUMN IF NOT EXISTS uploader_department VARCHAR(200),
    ADD COLUMN IF NOT EXISTS post_title TEXT,
    ADD COLUMN IF NOT EXISTS post_all_tags TEXT,
    ADD COLUMN IF NOT EXISTS ai_tags TEXT[],
    ADD COLUMN IF NOT EXISTS ai_scenes TEXT[],
    ADD COLUMN IF NOT EXISTS ai_caption TEXT,
    ADD COLUMN IF NOT EXISTS is_safe BOOLEAN DEFAULT true;

-- Add missing columns to read_model_recommendations_knn
ALTER TABLE read_model_recommendations_knn
    ADD COLUMN IF NOT EXISTS caption TEXT,
    ADD COLUMN IF NOT EXISTS is_safe BOOLEAN DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ;

-- Add missing columns to read_model_feed_personalized
ALTER TABLE read_model_feed_personalized
    ADD COLUMN IF NOT EXISTS feed_item_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS target_user_id INTEGER,
    ADD COLUMN IF NOT EXISTS uploader_username VARCHAR(100),
    ADD COLUMN IF NOT EXISTS combined_score FLOAT DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Add missing columns to read_model_user_search
ALTER TABLE read_model_user_search
    ADD COLUMN IF NOT EXISTS username VARCHAR(100),
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS department VARCHAR(200),
    ADD COLUMN IF NOT EXISTS bio TEXT,
    ADD COLUMN IF NOT EXISTS total_posts INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_followers INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS face_enrolled BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS joined_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- ==== CREATE MISSING TABLES ====

CREATE TABLE IF NOT EXISTS read_model_post_search (
    post_id INTEGER PRIMARY KEY REFERENCES posts(post_id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES users(user_id),
    author_username VARCHAR(100),
    author_department VARCHAR(200),
    title TEXT,
    body TEXT,
    all_ai_tags TEXT,
    all_ai_scenes TEXT,
    all_detected_user_ids TEXT,
    inferred_event_type VARCHAR(50),
    inferred_tags TEXT,
    categories TEXT,
    total_reactions INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS read_model_face_search (
    face_id VARCHAR(100) PRIMARY KEY,
    media_id INTEGER REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id INTEGER REFERENCES posts(post_id) ON DELETE CASCADE,
    face_embedding VECTOR(1024),
    bbox INTEGER[],
    identified_user_id INTEGER REFERENCES users(user_id),
    identified_username VARCHAR(100),
    match_confidence FLOAT,
    uploader_id INTEGER REFERENCES users(user_id),
    post_title TEXT,
    media_url VARCHAR(1000),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS read_model_known_faces (
    face_id VARCHAR(100) PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    username VARCHAR(100),
    department VARCHAR(200),
    profile_pic_url VARCHAR(1000),
    face_embedding VECTOR(1024),
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);
