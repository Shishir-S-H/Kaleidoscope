# 📊 Complete Database Schema - Kaleidoscope Platform

**Date**: October 15, 2025  
**Version**: Final Architecture  
**Database**: PostgreSQL with pgvector extension  
**Total Tables**: 17 (3 core + 3 AI + 4 existing read models → 7 new read models)

---

## 📋 Table of Contents

1. [Core Tables](#section-1-core-tables) (3 tables - Existing, No Changes)
2. [AI Insight Tables](#section-2-ai-insight-tables) (3 tables - Minor Updates)
3. [Read Model Tables](#section-3-read-model-tables) (7 tables - NEW Simplified)
4. [Complete SQL Schema](#complete-sql-schema)
5. [DBDiagram.io Format](#dbdiagramio-format)
6. [Entity Relationship Diagram](#entity-relationship-diagram)

---

## SECTION 1: CORE TABLES

### ✅ Status: Keep As-Is (Owned by Main Backend)

These tables are the **single source of truth** for core application data.

### Table 1.1: `users`

**Purpose**: User accounts and profiles

```sql
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    department VARCHAR(100),
    designation VARCHAR(100),
    bio TEXT,
    profile_picture_url VARCHAR(255),
    cover_photo_url VARCHAR(255),
    role VARCHAR(20) NOT NULL,                    -- ADMIN, USER, MODERATOR
    account_status VARCHAR(20) NOT NULL,          -- ACTIVE, SUSPENDED, DELETED
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_status ON users(account_status);

COMMENT ON TABLE users IS 'Core user accounts and profiles';
COMMENT ON COLUMN users.role IS 'User role: ADMIN, USER, MODERATOR';
COMMENT ON COLUMN users.account_status IS 'Account status: ACTIVE, SUSPENDED, DELETED';
```

---

### Table 1.2: `posts`

**Purpose**: User-generated posts (can contain multiple media)

```sql
CREATE TABLE posts (
    post_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(200),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',          -- DRAFT, PUBLISHED, ARCHIVED
    visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',     -- PUBLIC, PRIVATE, FOLLOWERS
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_visibility ON posts(visibility);
CREATE INDEX idx_posts_created ON posts(created_at DESC);

COMMENT ON TABLE posts IS 'User posts that can contain multiple media items';
COMMENT ON COLUMN posts.status IS 'Post status: DRAFT, PUBLISHED, ARCHIVED';
COMMENT ON COLUMN posts.visibility IS 'Who can see this post: PUBLIC, PRIVATE, FOLLOWERS';
```

---

### Table 1.3: `post_media`

**Purpose**: Individual media items (images/videos) within posts

```sql
CREATE TABLE post_media (
    media_id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL,              -- IMAGE, VIDEO
    media_url VARCHAR(1000) NOT NULL,
    thumbnail_url VARCHAR(1000),
    position INTEGER DEFAULT 0,                    -- Order in carousel (0-indexed)
    width INTEGER,
    height INTEGER,
    file_size_kb INTEGER,
    duration_seconds INTEGER,                      -- For videos
    extra_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_post_media_post ON post_media(post_id);
CREATE INDEX idx_post_media_type ON post_media(media_type);
CREATE INDEX idx_post_media_position ON post_media(post_id, position);

COMMENT ON TABLE post_media IS 'Individual media items (images/videos) within posts';
COMMENT ON COLUMN post_media.position IS 'Position in post carousel, 0-indexed';
COMMENT ON COLUMN post_media.media_url IS 'Cloudinary URL for the media';
```

---

## SECTION 2: AI INSIGHT TABLES

### ✅ Status: Minor Updates (BIGINT instead of INTEGER)

These tables store raw AI processing results.

### Table 2.1: `media_ai_insights`

**Purpose**: AI-generated insights for each media item

```sql
CREATE TABLE media_ai_insights (
    media_id BIGINT PRIMARY KEY
        REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id BIGINT NOT NULL
        REFERENCES posts(post_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'PROCESSING'
        CHECK (status IN ('PROCESSING', 'COMPLETED', 'UNSAFE', 'FAILED')),
    is_safe BOOLEAN,
    caption TEXT,
    tags TEXT[],
    scenes TEXT[],
    image_embedding VECTOR(512),                   -- CLIP embedding for similarity
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mai_post ON media_ai_insights(post_id);
CREATE INDEX idx_mai_status ON media_ai_insights(status);
CREATE INDEX idx_mai_safe ON media_ai_insights(is_safe) WHERE is_safe = true;

COMMENT ON TABLE media_ai_insights IS 'AI-generated insights for each media item';
COMMENT ON COLUMN media_ai_insights.status IS 'Processing status: PROCESSING, COMPLETED, UNSAFE, FAILED';
COMMENT ON COLUMN media_ai_insights.image_embedding IS '512-dimensional CLIP vector for semantic similarity';
COMMENT ON COLUMN media_ai_insights.tags IS 'AI-generated tags (e.g., beach, person, food)';
COMMENT ON COLUMN media_ai_insights.scenes IS 'AI-detected scenes (e.g., outdoor, office, party)';
```

---

### Table 2.2: `user_face_embeddings`

**Purpose**: Enrolled face embeddings for user identification

```sql
CREATE TABLE user_face_embeddings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE
        REFERENCES users(user_id) ON DELETE CASCADE,
    embedding VECTOR(1024) NOT NULL,               -- AdaFace 1024-dim embedding
    source_image_url VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ufe_user ON user_face_embeddings(user_id);
CREATE INDEX idx_ufe_active ON user_face_embeddings(is_active) WHERE is_active = true;

COMMENT ON TABLE user_face_embeddings IS 'Enrolled face embeddings for automatic user identification';
COMMENT ON COLUMN user_face_embeddings.embedding IS '1024-dimensional AdaFace vector for face matching';
COMMENT ON COLUMN user_face_embeddings.is_active IS 'Whether this face enrollment is currently active';
```

---

### Table 2.3: `media_detected_faces`

**Purpose**: Faces detected in media with identification

```sql
CREATE TABLE media_detected_faces (
    id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL
        REFERENCES media_ai_insights(media_id) ON DELETE CASCADE,
    bbox INTEGER[] NOT NULL,                       -- [x, y, width, height]
    embedding VECTOR(1024) NOT NULL,               -- AdaFace 1024-dim embedding
    identified_user_id BIGINT
        REFERENCES users(user_id) ON DELETE SET NULL,
    suggested_user_id BIGINT
        REFERENCES users(user_id) ON DELETE SET NULL,
    confidence_score FLOAT,
    status VARCHAR(20) NOT NULL DEFAULT 'UNIDENTIFIED'
        CHECK (status IN ('UNIDENTIFIED', 'SUGGESTED', 'CONFIRMED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mdf_media ON media_detected_faces(media_id);
CREATE INDEX idx_mdf_identified_user ON media_detected_faces(identified_user_id);
CREATE INDEX idx_mdf_status ON media_detected_faces(status);

COMMENT ON TABLE media_detected_faces IS 'Faces detected in media with identification status';
COMMENT ON COLUMN media_detected_faces.bbox IS 'Bounding box coordinates [x, y, width, height]';
COMMENT ON COLUMN media_detected_faces.embedding IS '1024-dimensional AdaFace embedding for matching';
COMMENT ON COLUMN media_detected_faces.status IS 'UNIDENTIFIED (< 0.70), SUGGESTED (0.70-0.85), CONFIRMED (> 0.85)';
```

---

## SECTION 3: READ MODEL TABLES (NEW - SIMPLIFIED)

### ✅ Status: Replace Existing 4 Tables with 7 Simplified Tables

**Key Design Principles**:

- ✅ **No Foreign Keys** - Completely independent, fully denormalized
- ✅ **Simplified** - Only 5-16 essential fields per table
- ✅ **Backend Owned** - Backend creates, updates, maintains 100%
- ✅ **ES Sync Source** - These tables are read by ES sync service

---

### Table 3.1: `read_model_media_search`

**Purpose**: Source of truth for `media_search` Elasticsearch index  
**Fields**: 16 fields  
**Updates**: After AI results, post aggregation, face identification, engagement changes

```sql
CREATE TABLE read_model_media_search (
    -- Primary Keys (NO FOREIGN KEYS)
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,

    -- Post Context (Denormalized from posts table)
    post_title VARCHAR(200),
    post_all_tags TEXT[],              -- ⭐ Aggregated tags from ALL images in post

    -- Media Info (Copied from post_media table)
    media_url VARCHAR(1000) NOT NULL,

    -- AI Insights (Copied from media_ai_insights table)
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    image_embedding TEXT,              -- 512-dim vector as JSON string
    is_safe BOOLEAN DEFAULT true,

    -- Detected Faces (Aggregated from media_detected_faces table)
    detected_user_ids BIGINT[],
    detected_usernames TEXT[],

    -- Uploader Info (Copied from users table)
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50) NOT NULL,
    uploader_department VARCHAR(100),

    -- Engagement (Copied from reactions/comments tables)
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rms_post ON read_model_media_search(post_id);
CREATE INDEX idx_rms_updated ON read_model_media_search(updated_at DESC);

COMMENT ON TABLE read_model_media_search IS 'Denormalized read model for media search - synced to ES media_search index';
COMMENT ON COLUMN read_model_media_search.post_all_tags IS '⭐ KEY FIELD: Aggregated tags from ALL images in post for contextual search';
COMMENT ON COLUMN read_model_media_search.image_embedding IS 'CLIP 512-dim vector stored as JSON text';
```

---

### Table 3.2: `read_model_post_search`

**Purpose**: Source of truth for `post_search` Elasticsearch index  
**Fields**: 13 fields  
**Updates**: Post created/updated, all media AI complete, post aggregation

```sql
CREATE TABLE read_model_post_search (
    -- Primary Key (NO FOREIGN KEYS)
    post_id BIGINT PRIMARY KEY,

    -- Author Info (Copied from users table)
    author_id BIGINT NOT NULL,
    author_username VARCHAR(50) NOT NULL,
    author_department VARCHAR(100),

    -- Post Content (Copied from posts table)
    title VARCHAR(200),
    body TEXT,

    -- Aggregated AI (Union of all media AI results)
    all_ai_tags TEXT[],                -- ⭐ Union of ALL media tags
    all_ai_scenes TEXT[],
    all_detected_user_ids BIGINT[],

    -- Post-Level AI (From post_aggregator service)
    inferred_event_type VARCHAR(50),   -- ⭐ e.g., "beach_party", "meeting"
    inferred_tags TEXT[],              -- ⭐ e.g., ["beach_party", "team_event"]

    -- Categories (Copied from posts table)
    categories TEXT[],

    -- Engagement (Aggregated from all media)
    total_reactions INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rps_author ON read_model_post_search(author_id);
CREATE INDEX idx_rps_updated ON read_model_post_search(updated_at DESC);

COMMENT ON TABLE read_model_post_search IS 'Denormalized read model for post-level search - synced to ES post_search index';
COMMENT ON COLUMN read_model_post_search.inferred_event_type IS '⭐ Post aggregator infers context (e.g., beach_party from beach+people+food)';
COMMENT ON COLUMN read_model_post_search.all_ai_tags IS 'Union of tags from ALL images in post';
```

---

### Table 3.3: `read_model_user_search`

**Purpose**: Source of truth for `user_search` Elasticsearch index  
**Fields**: 9 fields  
**Updates**: User profile updated, posts/follows change, face enrolled

```sql
CREATE TABLE read_model_user_search (
    -- Primary Key (NO FOREIGN KEYS)
    user_id BIGINT PRIMARY KEY,

    -- User Info (Copied from users table)
    username VARCHAR(50) NOT NULL,
    full_name VARCHAR(100),
    department VARCHAR(100),
    bio TEXT,

    -- Statistics (Calculated)
    total_posts INTEGER DEFAULT 0,
    total_followers INTEGER DEFAULT 0,

    -- Face Enrollment Status
    face_enrolled BOOLEAN DEFAULT false,

    -- Metadata
    joined_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rus_department ON read_model_user_search(department);

COMMENT ON TABLE read_model_user_search IS 'Denormalized read model for user discovery - synced to ES user_search index';
```

---

### Table 3.4: `read_model_face_search`

**Purpose**: Source of truth for `face_search` Elasticsearch index  
**Fields**: 12 fields  
**Updates**: Face detected, face identified

```sql
CREATE TABLE read_model_face_search (
    -- Primary Key (NO FOREIGN KEYS)
    id BIGSERIAL PRIMARY KEY,
    face_id VARCHAR(50) UNIQUE NOT NULL,
    media_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,

    -- Face Data (Copied from media_detected_faces)
    face_embedding TEXT NOT NULL,      -- 1024-dim vector as JSON string
    bbox INTEGER[],                    -- [x, y, width, height]

    -- Identification (Computed by backend after KNN matching)
    identified_user_id BIGINT,
    identified_username VARCHAR(50),
    match_confidence FLOAT,

    -- Context (For search result display)
    uploader_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    media_url VARCHAR(1000),

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_rfs_identified_user ON read_model_face_search(identified_user_id);
CREATE INDEX idx_rfs_media ON read_model_face_search(media_id);

COMMENT ON TABLE read_model_face_search IS 'Denormalized read model for face-based search - synced to ES face_search index';
COMMENT ON COLUMN read_model_face_search.face_embedding IS 'AdaFace 1024-dim vector stored as JSON text';
```

---

### Table 3.5: `read_model_recommendations_knn`

**Purpose**: Source of truth for `recommendations_knn` Elasticsearch index  
**Fields**: 5 fields (minimal for performance)  
**Updates**: AI insights complete

```sql
CREATE TABLE read_model_recommendations_knn (
    -- Primary Key (NO FOREIGN KEYS)
    media_id BIGINT PRIMARY KEY,

    -- Minimal Fields for KNN Performance
    image_embedding TEXT NOT NULL,     -- 512-dim vector as JSON string
    media_url VARCHAR(1000) NOT NULL,
    caption TEXT,
    is_safe BOOLEAN DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE read_model_recommendations_knn IS 'Lightweight read model for visual similarity - synced to ES recommendations_knn index';
COMMENT ON COLUMN read_model_recommendations_knn.image_embedding IS 'CLIP 512-dim vector optimized for KNN search';
```

---

### Table 3.6: `read_model_feed_personalized`

**Purpose**: Source of truth for `feed_personalized` Elasticsearch index  
**Fields**: 9 fields  
**Updates**: Periodically computed, new post published

```sql
CREATE TABLE read_model_feed_personalized (
    -- Primary Key (NO FOREIGN KEYS)
    id BIGSERIAL PRIMARY KEY,
    feed_item_id VARCHAR(100) UNIQUE NOT NULL,
    target_user_id BIGINT NOT NULL,    -- ⭐ User who will see this in their feed
    media_id BIGINT NOT NULL,

    -- Content Preview
    media_url VARCHAR(1000),
    caption TEXT,

    -- Uploader Info
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50),

    -- Relevance Score (Computed by backend algorithm)
    combined_score FLOAT DEFAULT 0,    -- ⭐ Higher = more relevant to target_user

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ             -- TTL for feed items (e.g., 7 days)
);

CREATE INDEX idx_rfp_target_score ON read_model_feed_personalized(target_user_id, combined_score DESC);
CREATE INDEX idx_rfp_expires ON read_model_feed_personalized(expires_at);

COMMENT ON TABLE read_model_feed_personalized IS 'Pre-computed personalized feed items - synced to ES feed_personalized index';
COMMENT ON COLUMN read_model_feed_personalized.target_user_id IS 'User who will see this in their personalized feed';
COMMENT ON COLUMN read_model_feed_personalized.combined_score IS 'Relevance score: higher = more relevant';
```

---

### Table 3.7: `read_model_known_faces`

**Purpose**: Source of truth for `known_faces_index` Elasticsearch index  
**Fields**: 7 fields  
**Updates**: User enrolls face, profile picture updated

```sql
CREATE TABLE read_model_known_faces (
    -- Primary Key (NO FOREIGN KEYS)
    user_id BIGINT PRIMARY KEY,

    -- User Info (Copied from users table)
    username VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    profile_pic_url VARCHAR(255),

    -- Face Data (Copied from user_face_embeddings)
    face_embedding TEXT NOT NULL,      -- 1024-dim vector as JSON string

    -- Metadata
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_rkf_active ON read_model_known_faces(is_active) WHERE is_active = true;

COMMENT ON TABLE read_model_known_faces IS 'Known faces database for identification - synced to ES known_faces_index';
COMMENT ON COLUMN read_model_known_faces.face_embedding IS 'AdaFace 1024-dim vector for KNN face matching';
```

---

## COMPLETE SQL SCHEMA

### Complete DDL (All 13 Tables)

```sql
-- =====================================================
-- KALEIDOSCOPE PLATFORM - COMPLETE DATABASE SCHEMA
-- =====================================================
-- Version: Final Architecture (October 15, 2025)
-- Database: PostgreSQL 14+ with pgvector extension
-- Total Tables: 13 (3 core + 3 AI + 7 read models)
-- =====================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- SECTION 1: CORE TABLES (3 tables)
-- =====================================================

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    department VARCHAR(100),
    designation VARCHAR(100),
    bio TEXT,
    profile_picture_url VARCHAR(255),
    cover_photo_url VARCHAR(255),
    role VARCHAR(20) NOT NULL,
    account_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

CREATE TABLE posts (
    post_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(200),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_created ON posts(created_at DESC);

CREATE TABLE post_media (
    media_id BIGSERIAL PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL,
    media_url VARCHAR(1000) NOT NULL,
    thumbnail_url VARCHAR(1000),
    position INTEGER DEFAULT 0,
    width INTEGER,
    height INTEGER,
    file_size_kb INTEGER,
    duration_seconds INTEGER,
    extra_metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_post_media_post ON post_media(post_id);

-- =====================================================
-- SECTION 2: AI INSIGHT TABLES (3 tables)
-- =====================================================

CREATE TABLE media_ai_insights (
    media_id BIGINT PRIMARY KEY
        REFERENCES post_media(media_id) ON DELETE CASCADE,
    post_id BIGINT NOT NULL
        REFERENCES posts(post_id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'PROCESSING'
        CHECK (status IN ('PROCESSING', 'COMPLETED', 'UNSAFE', 'FAILED')),
    is_safe BOOLEAN,
    caption TEXT,
    tags TEXT[],
    scenes TEXT[],
    image_embedding VECTOR(512),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mai_post ON media_ai_insights(post_id);
CREATE INDEX idx_mai_status ON media_ai_insights(status);

CREATE TABLE user_face_embeddings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE
        REFERENCES users(user_id) ON DELETE CASCADE,
    embedding VECTOR(1024) NOT NULL,
    source_image_url VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ufe_user ON user_face_embeddings(user_id);

CREATE TABLE media_detected_faces (
    id BIGSERIAL PRIMARY KEY,
    media_id BIGINT NOT NULL
        REFERENCES media_ai_insights(media_id) ON DELETE CASCADE,
    bbox INTEGER[] NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    identified_user_id BIGINT
        REFERENCES users(user_id) ON DELETE SET NULL,
    suggested_user_id BIGINT
        REFERENCES users(user_id) ON DELETE SET NULL,
    confidence_score FLOAT,
    status VARCHAR(20) NOT NULL DEFAULT 'UNIDENTIFIED'
        CHECK (status IN ('UNIDENTIFIED', 'SUGGESTED', 'CONFIRMED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mdf_media ON media_detected_faces(media_id);
CREATE INDEX idx_mdf_identified_user ON media_detected_faces(identified_user_id);

-- =====================================================
-- SECTION 3: READ MODEL TABLES (7 tables - NO FK)
-- =====================================================

CREATE TABLE read_model_media_search (
    media_id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    post_all_tags TEXT[],
    media_url VARCHAR(1000) NOT NULL,
    ai_caption TEXT,
    ai_tags TEXT[],
    ai_scenes TEXT[],
    image_embedding TEXT,
    is_safe BOOLEAN DEFAULT true,
    detected_user_ids BIGINT[],
    detected_usernames TEXT[],
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50) NOT NULL,
    uploader_department VARCHAR(100),
    reaction_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rms_post ON read_model_media_search(post_id);

CREATE TABLE read_model_post_search (
    post_id BIGINT PRIMARY KEY,
    author_id BIGINT NOT NULL,
    author_username VARCHAR(50) NOT NULL,
    author_department VARCHAR(100),
    title VARCHAR(200),
    body TEXT,
    all_ai_tags TEXT[],
    all_ai_scenes TEXT[],
    all_detected_user_ids BIGINT[],
    inferred_event_type VARCHAR(50),
    inferred_tags TEXT[],
    categories TEXT[],
    total_reactions INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rps_author ON read_model_post_search(author_id);

CREATE TABLE read_model_user_search (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    full_name VARCHAR(100),
    department VARCHAR(100),
    bio TEXT,
    total_posts INTEGER DEFAULT 0,
    total_followers INTEGER DEFAULT 0,
    face_enrolled BOOLEAN DEFAULT false,
    joined_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE read_model_face_search (
    id BIGSERIAL PRIMARY KEY,
    face_id VARCHAR(50) UNIQUE NOT NULL,
    media_id BIGINT NOT NULL,
    post_id BIGINT NOT NULL,
    face_embedding TEXT NOT NULL,
    bbox INTEGER[],
    identified_user_id BIGINT,
    identified_username VARCHAR(50),
    match_confidence FLOAT,
    uploader_id BIGINT NOT NULL,
    post_title VARCHAR(200),
    media_url VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_rfs_identified_user ON read_model_face_search(identified_user_id);

CREATE TABLE read_model_recommendations_knn (
    media_id BIGINT PRIMARY KEY,
    image_embedding TEXT NOT NULL,
    media_url VARCHAR(1000) NOT NULL,
    caption TEXT,
    is_safe BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE read_model_feed_personalized (
    id BIGSERIAL PRIMARY KEY,
    feed_item_id VARCHAR(100) UNIQUE NOT NULL,
    target_user_id BIGINT NOT NULL,
    media_id BIGINT NOT NULL,
    media_url VARCHAR(1000),
    caption TEXT,
    uploader_id BIGINT NOT NULL,
    uploader_username VARCHAR(50),
    combined_score FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_rfp_target_score ON read_model_feed_personalized(target_user_id, combined_score DESC);

CREATE TABLE read_model_known_faces (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    profile_pic_url VARCHAR(255),
    face_embedding TEXT NOT NULL,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_rkf_active ON read_model_known_faces(is_active) WHERE is_active = true;
```

---

## DBDIAGRAM.IO FORMAT

Copy and paste this into [dbdiagram.io](https://dbdiagram.io) for instant visualization:

```dbml
// =====================================================
// KALEIDOSCOPE PLATFORM - DATABASE SCHEMA
// =====================================================
// Visualization: https://dbdiagram.io
// Total Tables: 13
// =====================================================

// SECTION 1: CORE TABLES
Table users {
  user_id bigserial [pk]
  username varchar(50) [unique, not null]
  email varchar(100) [unique, not null]
  password varchar(255) [not null]
  full_name varchar(100)
  department varchar(100)
  designation varchar(100)
  bio text
  profile_picture_url varchar(255)
  cover_photo_url varchar(255)
  role varchar(20) [not null, note: 'ADMIN, USER, MODERATOR']
  account_status varchar(20) [not null, note: 'ACTIVE, SUSPENDED, DELETED']
  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  Note: 'Core user accounts and profiles'
}

Table posts {
  post_id bigserial [pk]
  user_id bigint [ref: > users.user_id, not null]
  title varchar(200)
  body text
  status varchar(20) [not null, default: 'DRAFT', note: 'DRAFT, PUBLISHED, ARCHIVED']
  visibility varchar(20) [not null, default: 'PUBLIC', note: 'PUBLIC, PRIVATE, FOLLOWERS']
  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  Note: 'User posts that can contain multiple media items'
}

Table post_media {
  media_id bigserial [pk]
  post_id bigint [ref: > posts.post_id, not null]
  media_type varchar(20) [not null, note: 'IMAGE, VIDEO']
  media_url varchar(1000) [not null, note: 'Cloudinary URL']
  thumbnail_url varchar(1000)
  position integer [default: 0, note: '0-indexed position in carousel']
  width integer
  height integer
  file_size_kb integer
  duration_seconds integer
  extra_metadata jsonb
  created_at timestamptz [not null, default: `now()`]

  Note: 'Individual media items (images/videos) within posts'
}

// SECTION 2: AI INSIGHT TABLES
Table media_ai_insights {
  media_id bigint [pk, ref: - post_media.media_id]
  post_id bigint [ref: > posts.post_id, not null]
  status varchar(20) [not null, default: 'PROCESSING', note: 'PROCESSING, COMPLETED, UNSAFE, FAILED']
  is_safe boolean
  caption text [note: 'AI-generated caption']
  tags text[] [note: 'AI tags: beach, person, food']
  scenes text[] [note: 'AI scenes: outdoor, office, party']
  image_embedding vector(512) [note: 'CLIP 512-dim for similarity']
  updated_at timestamptz [not null, default: `now()`]

  Note: 'AI-generated insights for each media item'
}

Table user_face_embeddings {
  id bigserial [pk]
  user_id bigint [ref: - users.user_id, unique, not null]
  embedding vector(1024) [not null, note: 'AdaFace 1024-dim']
  source_image_url varchar(255)
  is_active boolean [not null, default: true]
  enrolled_at timestamptz [not null, default: `now()`]
  updated_at timestamptz [not null, default: `now()`]

  Note: 'Enrolled face embeddings for user identification'
}

Table media_detected_faces {
  id bigserial [pk]
  media_id bigint [ref: > media_ai_insights.media_id, not null]
  bbox integer[] [not null, note: '[x, y, width, height]']
  embedding vector(1024) [not null, note: 'AdaFace 1024-dim']
  identified_user_id bigint [ref: > users.user_id]
  suggested_user_id bigint [ref: > users.user_id]
  confidence_score float
  status varchar(20) [not null, default: 'UNIDENTIFIED', note: 'UNIDENTIFIED, SUGGESTED, CONFIRMED']
  created_at timestamptz [not null, default: `now()`]

  Note: 'Faces detected in media with identification'
}

// SECTION 3: READ MODEL TABLES (NO FOREIGN KEYS)
Table read_model_media_search {
  media_id bigint [pk, note: '⭐ No FK - denormalized']
  post_id bigint [not null]
  post_title varchar(200)
  post_all_tags text[] [note: '⭐ Aggregated from ALL images in post']
  media_url varchar(1000) [not null]
  ai_caption text
  ai_tags text[]
  ai_scenes text[]
  image_embedding text [note: '512-dim as JSON string']
  is_safe boolean [default: true]
  detected_user_ids bigint[]
  detected_usernames text[]
  uploader_id bigint [not null]
  uploader_username varchar(50) [not null]
  uploader_department varchar(100)
  reaction_count integer [default: 0]
  comment_count integer [default: 0]
  created_at timestamptz [not null]
  updated_at timestamptz [default: `now()`]

  Note: 'Read model for ES media_search index (16 fields)'
}

Table read_model_post_search {
  post_id bigint [pk, note: '⭐ No FK - denormalized']
  author_id bigint [not null]
  author_username varchar(50) [not null]
  author_department varchar(100)
  title varchar(200)
  body text
  all_ai_tags text[] [note: 'Union of ALL media tags']
  all_ai_scenes text[]
  all_detected_user_ids bigint[]
  inferred_event_type varchar(50) [note: '⭐ beach_party, meeting, etc.']
  inferred_tags text[] [note: '⭐ From post aggregator']
  categories text[]
  total_reactions integer [default: 0]
  total_comments integer [default: 0]
  created_at timestamptz [not null]
  updated_at timestamptz [default: `now()`]

  Note: 'Read model for ES post_search index (13 fields)'
}

Table read_model_user_search {
  user_id bigint [pk, note: '⭐ No FK - denormalized']
  username varchar(50) [not null]
  full_name varchar(100)
  department varchar(100)
  bio text
  total_posts integer [default: 0]
  total_followers integer [default: 0]
  face_enrolled boolean [default: false]
  joined_at timestamptz [not null]
  updated_at timestamptz [default: `now()`]

  Note: 'Read model for ES user_search index (9 fields)'
}

Table read_model_face_search {
  id bigserial [pk, note: '⭐ No FK - denormalized']
  face_id varchar(50) [unique, not null]
  media_id bigint [not null]
  post_id bigint [not null]
  face_embedding text [not null, note: '1024-dim as JSON']
  bbox integer[]
  identified_user_id bigint
  identified_username varchar(50)
  match_confidence float
  uploader_id bigint [not null]
  post_title varchar(200)
  media_url varchar(1000)
  created_at timestamptz [not null]

  Note: 'Read model for ES face_search index (12 fields)'
}

Table read_model_recommendations_knn {
  media_id bigint [pk, note: '⭐ No FK - denormalized']
  image_embedding text [not null, note: '512-dim as JSON']
  media_url varchar(1000) [not null]
  caption text
  is_safe boolean [default: true]
  created_at timestamptz [not null]

  Note: 'Read model for ES recommendations_knn index (5 fields - minimal)'
}

Table read_model_feed_personalized {
  id bigserial [pk, note: '⭐ No FK - denormalized']
  feed_item_id varchar(100) [unique, not null]
  target_user_id bigint [not null, note: 'User who sees this in feed']
  media_id bigint [not null]
  media_url varchar(1000)
  caption text
  uploader_id bigint [not null]
  uploader_username varchar(50)
  combined_score float [default: 0, note: 'Relevance score']
  created_at timestamptz [not null]
  expires_at timestamptz [note: 'TTL 7 days']

  Note: 'Read model for ES feed_personalized index (9 fields)'
}

Table read_model_known_faces {
  user_id bigint [pk, note: '⭐ No FK - denormalized']
  username varchar(50) [not null]
  department varchar(100)
  profile_pic_url varchar(255)
  face_embedding text [not null, note: '1024-dim as JSON']
  enrolled_at timestamptz [not null, default: `now()`]
  is_active boolean [default: true]

  Note: 'Read model for ES known_faces_index (7 fields)'
}
```

---

## ENTITY RELATIONSHIP DIAGRAM

### Visual Representation

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECTION 1: CORE TABLES                       │
│                 (With Foreign Key Relationships)                │
└─────────────────────────────────────────────────────────────────┘

     ┌──────────────┐
     │    users     │
     │──────────────│
     │ user_id (PK) │
     │ username     │
     │ email        │
     │ ...          │
     └──────────────┘
            │ 1
            │
            │ N
     ┌──────────────┐
     │    posts     │
     │──────────────│
     │ post_id (PK) │──┐
     │ user_id (FK) │  │
     │ title        │  │
     │ ...          │  │
     └──────────────┘  │
            │ 1        │
            │          │
            │ N        │
     ┌──────────────┐  │
     │ post_media   │  │
     │──────────────│  │
     │ media_id(PK) │──┼──┐
     │ post_id (FK) │  │  │
     │ media_url    │  │  │
     │ ...          │  │  │
     └──────────────┘  │  │
            │ 1        │  │
            │          │  │
            │ 1        │  │
     ┌──────────────┐  │  │
     │media_ai_     │  │  │
     │  insights    │  │  │
     │──────────────│  │  │
     │media_id(PK,FK)  │  │
     │post_id (FK)  │──┘  │
     │ is_safe      │     │
     │ tags[]       │     │
     │ scenes[]     │     │
     │ embedding    │     │
     └──────────────┘     │
            │ 1           │
            │             │
            │ N           │
     ┌──────────────┐     │
     │media_detected│     │
     │    _faces    │     │
     │──────────────│     │
     │ id (PK)      │     │
     │media_id (FK) │     │
     │ bbox[]       │     │
     │ embedding    │     │
     │identified_   │     │
     │ user_id (FK) │─────┘
     └──────────────┘

     ┌──────────────┐
     │user_face_    │
     │ embeddings   │
     │──────────────│
     │ id (PK)      │
     │user_id (FK)  │───┐
     │ embedding    │   │
     └──────────────┘   │
                        │
                        │
           ┌────────────┘
           │
           └──> (back to users)

┌─────────────────────────────────────────────────────────────────┐
│               SECTION 3: READ MODEL TABLES                      │
│          (NO Foreign Keys - Completely Independent)             │
└─────────────────────────────────────────────────────────────────┘

  ┌───────────────────┐     ┌───────────────────┐
  │read_model_media   │     │read_model_post    │
  │     _search       │     │     _search       │
  │───────────────────│     │───────────────────│
  │media_id (PK)      │     │post_id (PK)       │
  │post_all_tags[]⭐  │     │all_ai_tags[]      │
  │ai_tags[]          │     │inferred_event⭐   │
  │image_embedding    │     │inferred_tags[]⭐  │
  └───────────────────┘     └───────────────────┘
           │                         │
           └─────────┬───────────────┘
                     │
                     ▼
              Synced to Elasticsearch
                     │
           ┌─────────┴───────────┐
           │                     │
  ┌────────────────┐    ┌────────────────┐
  │ media_search   │    │ post_search    │
  │  (ES Index)    │    │  (ES Index)    │
  └────────────────┘    └────────────────┘


  ┌───────────────────┐     ┌───────────────────┐
  │read_model_user    │     │read_model_face    │
  │     _search       │     │     _search       │
  │───────────────────│     │───────────────────│
  │user_id (PK)       │     │id (PK)            │
  │username           │     │face_embedding     │
  │face_enrolled      │     │identified_user_id │
  └───────────────────┘     └───────────────────┘

  ┌───────────────────┐     ┌───────────────────┐
  │read_model_        │     │read_model_feed    │
  │recommendations_knn│     │  _personalized    │
  │───────────────────│     │───────────────────│
  │media_id (PK)      │     │id (PK)            │
  │image_embedding    │     │target_user_id⭐   │
  │(5 fields only)    │     │combined_score⭐   │
  └───────────────────┘     └───────────────────┘

  ┌───────────────────┐
  │read_model_known   │
  │     _faces        │
  │───────────────────│
  │user_id (PK)       │
  │face_embedding     │
  │is_active          │
  └───────────────────┘
```

---

## 📊 SUMMARY STATISTICS

| Category              | Tables | Total Fields | Foreign Keys | Indexes |
| --------------------- | ------ | ------------ | ------------ | ------- |
| **Core Tables**       | 3      | ~25          | 2            | 6       |
| **AI Insight Tables** | 3      | ~20          | 5            | 7       |
| **Read Model Tables** | 7      | ~75          | 0 ⭐         | 7       |
| **TOTAL**             | **13** | **~120**     | **7**        | **20**  |

### Key Statistics

- **Vector Columns**: 5 total

  - CLIP 512-dim: 1 (in media_ai_insights)
  - AdaFace 1024-dim: 2 (in user_face_embeddings, media_detected_faces)
  - Vectors as TEXT in read models: 2 (image_embedding, face_embedding)

- **Array Columns**: 15 total

  - tags[], scenes[], detected_user_ids[], etc.

- **Read Model Design**:
  - ⭐ **0 Foreign Keys** in read models (completely independent)
  - ⭐ **Fully Denormalized** (all data copied)
  - ⭐ **Backend Owned** (backend writes, AI team reads)

---

## 🎯 KEY INNOVATIONS

1. **Post Aggregation Fields** ⭐

   - `read_model_media_search.post_all_tags` - Tags from ALL images in post
   - `read_model_post_search.inferred_event_type` - AI-detected event (beach_party, meeting)
   - `read_model_post_search.inferred_tags` - Enhanced semantic tags

2. **Independent Read Models** ⭐

   - No foreign keys = no cascade issues
   - Easy to rebuild from core tables
   - ES sync can continue even if core tables change

3. **Dual Vector Storage** ⭐

   - pgvector for core tables (real vectors)
   - TEXT (JSON) for read models (easier ES sync)

4. **Personalized Feed** ⭐
   - Pre-computed relevance scores
   - TTL-based expiry
   - Per-user feed items

---

**Ready to visualize at [dbdiagram.io](https://dbdiagram.io)!** 🚀

Copy the DBDiagram.io section and paste it into the site for instant ERD generation.
