-- Enable the pgvector extension if it's not already
CREATE EXTENSION IF NOT EXISTS vector;

-- ==== AI INSIGHT TABLES ====

CREATE TABLE media_ai_insights (
    media_id INTEGER PRIMARY KEY REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PROCESSING', 'COMPLETED', 'UNSAFE', 'FAILED')),
    is_safe BOOLEAN,
    caption TEXT,
    tags TEXT[],
    scenes TEXT[],
    image_embedding VECTOR(512),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_face_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    embedding VECTOR(1024) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE media_detected_faces (
    id SERIAL PRIMARY KEY,
    media_id INTEGER NOT NULL REFERENCES media_ai_insights(media_id) ON DELETE CASCADE,
    bbox INTEGER[] NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    identified_user_id INTEGER REFERENCES users(user_id),
    suggested_user_id INTEGER REFERENCES users(user_id),
    confidence_score FLOAT,
    status VARCHAR(20) NOT NULL DEFAULT 'UNIDENTIFIED' CHECK (status IN ('UNIDENTIFIED', 'SUGGESTED', 'CONFIRMED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==== READ MODEL TABLES ====

CREATE TABLE read_model_search (
    media_id INTEGER PRIMARY KEY REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    media_url VARCHAR(1000),
    uploader_info JSONB,
    post_info JSONB,
    caption TEXT,
    tags TEXT[],
    scenes TEXT[],
    image_embedding VECTOR(512),
    detected_users JSONB,
    reaction_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE read_model_recommendations (
    media_id INTEGER PRIMARY KEY REFERENCES post_media(media_id) ON DELETE CASCADE,
    image_embedding VECTOR(512),
    media_url VARCHAR(1000)
);

CREATE TABLE read_model_feed (
    media_id INTEGER PRIMARY KEY REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    uploader_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    media_url VARCHAR(1000),
    caption TEXT,
    reaction_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ
);

CREATE TABLE read_model_user_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    profile_info JSONB,
    follower_count INTEGER NOT NULL DEFAULT 0,
    interests TEXT[],
    face_embedding VECTOR(1024),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now()
);
