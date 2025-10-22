# 🏗️ Kaleidoscope AI - Project Structure

**Clean, organized codebase structure for easy navigation and maintenance**

---

## 📁 Directory Overview

```
kaleidoscope-ai/
├── 📁 services/                    # Core AI microservices
│   ├── content_moderation/         # NSFW detection service
│   ├── image_tagger/              # Object/scene tagging service
│   ├── scene_recognition/         # Environment detection service
│   ├── image_captioning/          # Image description service
│   ├── face_recognition/          # Face detection service
│   ├── post_aggregator/           # Multi-image aggregation service
│   └── es_sync/                   # Elasticsearch sync service
├── 📁 shared/                     # Shared utilities and libraries
│   ├── redis_streams/             # Redis Streams utilities
│   ├── schemas/                   # Message schemas (Pydantic)
│   ├── utils/                     # Common utilities
│   ├── db/                        # Database models
│   └── env_templates/             # Environment templates
├── 📁 es_mappings/                # Elasticsearch index mappings
│   ├── media_search.json          # Media search index
│   ├── post_search.json           # Post search index
│   ├── user_search.json           # User search index
│   ├── face_search.json           # Face search index
│   ├── recommendations_knn.json   # Recommendations index
│   ├── feed_personalized.json     # Personalized feed index
│   └── known_faces_index.json     # Known faces index
├── 📁 scripts/                    # Utility scripts
│   └── setup_es_indices.py        # ES index creation script
├── 📁 tests/                      # Test suites
│   ├── test_end_to_end.py         # Complete test suite
│   ├── test_es_sync.py            # ES sync tests
│   ├── test_post_aggregator.py    # Post aggregator tests
│   └── test_redis_streams.py      # Redis Streams tests
├── 📁 migrations/                 # Database migrations
│   └── V1__create_ai_tables.sql   # Initial AI tables
├── 📄 docker-compose.yml          # Service orchestration
├── 📄 requirements.txt            # Root dependencies
└── 📄 README.md                   # Main project documentation
```

---

## 🎯 Service Architecture

### Core AI Services (5)

| Service | Purpose | Input Stream | Output Stream | Technology |
|---------|---------|--------------|---------------|------------|
| **content_moderation** | NSFW detection | `post-image-processing` | `ml-insights-results` | HuggingFace API |
| **image_tagger** | Object/scene tagging | `post-image-processing` | `ml-insights-results` | HuggingFace API |
| **scene_recognition** | Environment detection | `post-image-processing` | `ml-insights-results` | HuggingFace API |
| **image_captioning** | Image descriptions | `post-image-processing` | `ml-insights-results` | HuggingFace API |
| **face_recognition** | Face detection | `post-image-processing` | `face-detection-results` | HuggingFace API |

### Processing Services (2)

| Service | Purpose | Input Stream | Output Stream | Technology |
|---------|---------|--------------|---------------|------------|
| **post_aggregator** | Multi-image aggregation | `ml-insights-results` | `post-insights-enriched` | Python + Redis |
| **es_sync** | PostgreSQL → ES sync | `es-sync-queue` | Elasticsearch | Python + ES |

---

## 🔧 Shared Components

### Redis Streams (`shared/redis_streams/`)
- **`publisher.py`** - Redis Stream publisher class
- **`consumer.py`** - Redis Stream consumer class
- **`utils.py`** - Stream utilities and helpers

### Message Schemas (`shared/schemas/`)
- **`message_schemas.py`** - Pydantic models for all messages

### Utilities (`shared/utils/`)
- **`logger.py`** - Structured JSON logging

### Database (`shared/db/`)
- **`models.py`** - SQLAlchemy ORM models

### Environment Templates (`shared/env_templates/`)
- Service-specific environment variable templates

---

## 📊 Elasticsearch Indices

### Search Indices (4)
1. **`media_search`** - Individual media/image search
2. **`post_search`** - Post-level aggregated search
3. **`user_search`** - User profiles and discovery
4. **`face_search`** - Face detection and search

### Recommendation Indices (2)
5. **`recommendations_knn`** - Content-based recommendations
6. **`feed_personalized`** - Personalized user feeds

### Management Indices (1)
7. **`known_faces_index`** - Face enrollment and identification

---

## 🧪 Testing Structure

### Automated Tests
- **`test_end_to_end.py`** - Complete system test (14 tests)
- **`test_es_sync.py`** - Elasticsearch sync tests
- **`test_post_aggregator.py`** - Post aggregation tests
- **`test_redis_streams.py`** - Redis Streams tests

### Test Coverage
- ✅ Infrastructure (Redis, Elasticsearch, Docker)
- ✅ Write Path (Image processing pipeline)
- ✅ Read Path (Search functionality)
- ✅ Performance (Response times, throughput)

---

## 📋 File Organization Principles

### 1. **Single Responsibility**
- Each service has one clear purpose
- Shared code is centralized
- No duplicate functionality

### 2. **Clear Hierarchy**
- Services grouped by function
- Shared components centralized
- Configuration files at appropriate levels

### 3. **Easy Navigation**
- Descriptive directory names
- Consistent file naming
- Clear separation of concerns

### 4. **Maintainability**
- No redundant files
- Centralized shared code
- Clear dependencies

---

## 🚀 Quick Navigation

### For Development
```
services/           # Main development area
├── [service_name]/ # Individual service development
└── shared/         # Shared utilities and schemas
```

### For Testing
```
tests/              # All test files
├── test_end_to_end.py  # Complete test suite
└── [specific_tests]    # Individual component tests
```

### For Configuration
```
es_mappings/        # Elasticsearch configurations
shared/env_templates/ # Environment configurations
docker-compose.yml  # Service orchestration
```

### For Documentation
```
README.md           # Main project documentation
START_HERE.md       # Quick start guide
[other_docs].md     # Detailed documentation
```

---

## 📈 Benefits of This Structure

### ✅ **Clean Organization**
- No redundant files or directories
- Clear separation of concerns
- Easy to navigate and understand

### ✅ **Maintainable**
- Centralized shared code
- Consistent structure across services
- Easy to add new services

### ✅ **Scalable**
- Clear service boundaries
- Shared utilities reduce duplication
- Easy to extend functionality

### ✅ **Developer Friendly**
- Intuitive directory structure
- Clear file naming conventions
- Easy to find what you need

---

## 🔄 Migration Summary

### Files Removed (25+ files)
- ❌ `deployment/` directory (redundant with services)
- ❌ `trigger_job.py` (outdated RabbitMQ)
- ❌ `text_embedding/` service (unused)
- ❌ `search_service/` service (unused)
- ❌ `collector/` service (unused)
- ❌ Duplicate ES mappings
- ❌ Redundant test scripts
- ❌ Unused environment templates
- ❌ Individual service shared directories

### Structure Optimized
- ✅ Centralized shared code
- ✅ Clean service organization
- ✅ Streamlined testing
- ✅ Simplified configuration

---

## 🎯 Next Steps

### For Development
1. **Add New Services**: Follow the established pattern in `services/`
2. **Shared Code**: Add to `shared/` directory
3. **Testing**: Add tests to `tests/` directory

### For Maintenance
1. **Keep Structure**: Maintain the clean organization
2. **Avoid Duplication**: Use shared components
3. **Update Documentation**: Keep structure docs current

---

**🎉 Your codebase is now clean, organized, and easy to navigate!**

**Total Impact**: 25+ redundant files removed, clean structure established, easy maintenance enabled.
