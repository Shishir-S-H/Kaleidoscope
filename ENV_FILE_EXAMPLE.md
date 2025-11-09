# 📝 Complete .env File Example

**Environment variables for Kaleidoscope AI Services with dual Docker registry setup**

---

## 🏗️ Docker Registry Setup

- **Backend Service**: Uses `DOCKER_REGISTRY` (ajayprabhu2004/rajay04)
- **AI Services**: Uses `DOCKER_USERNAME` (shishir01) - currently built locally

---

## 📋 Complete .env File

```bash
# ============================================
# Docker Registry Configuration
# ============================================
# DOCKER_REGISTRY: For backend service (ajayprabhu2004/rajay04)
DOCKER_REGISTRY=ajayprabhu2004
# OR if using rajay04:
# DOCKER_REGISTRY=rajay04

# DOCKER_USERNAME: For AI services (shishir01) - currently AI services are built locally
DOCKER_USERNAME=shishir01

# ============================================
# HuggingFace API Configuration
# ============================================
HF_API_TOKEN=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

# HuggingFace API URLs (REQUIRED - one for each AI service)
HF_API_URL_CONTENT_MODERATION=https://phantomfury-kaleidoscope-content-moderation.hf.space/classify
HF_API_URL_IMAGE_TAGGER=https://phantomfury-kaleidoscope-image-tagger.hf.space/tag
HF_API_URL_SCENE_RECOGNITION=https://phantomfury-kaleidoscope-scene-recognition.hf.space/recognize
HF_API_URL_IMAGE_CAPTIONING=https://phantomfury-kaleidoscope-image-captioning.hf.space/caption
HF_API_URL_FACE_RECOGNITION=https://phantomfury-kaleidoscope-face-recognition.hf.space/detect

# ============================================
# Security Configuration
# ============================================
# Redis Security
REDIS_PASSWORD=kaleidoscope1-reddis

# Elastic Search
ELASTICSEARCH_PASSWORD=kaleidoscope1-elastic

# ============================================
# Environment Configuration
# ============================================
ENVIRONMENT=production

# ============================================
# Scene Recognition Configuration
# ============================================
# Scene Recognition Configuration (optional - has default)
SCENE_LABELS=beach,mountains,urban,office,restaurant,forest,desert,lake,park,indoor,outdoor,rural,coastal,mountainous,tropical,arctic

# ============================================
# Backend Application Configuration
# ============================================
# Backend Application Configuration (optional - defaults provided)
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-app
APP_PORT=8080
```

---

## 🔍 Registry Usage

### Backend Service

- **Registry**: `ajayprabhu2004` or `rajay04` (set via `DOCKER_REGISTRY`)
- **Image**: `${DOCKER_REGISTRY}/kaleidoscope:backend-${APP_VERSION}`
- **Example**: `ajayprabhu2004/kaleidoscope:backend-latest`

### AI Services

- **Registry**: `shishir01` (set via `DOCKER_USERNAME`)
- **Status**: Currently built locally (not pulled from registry)
- **Future**: Can be configured to pull from `shishir01` registry if needed

---

## 📝 Notes

1. **DOCKER_REGISTRY** is used by the backend service to pull the image
2. **DOCKER_USERNAME** is for AI services (currently not used, but kept for future reference)
3. **AI services** are built locally using `build:` directives in docker-compose
4. **Backend** is pulled from Docker Hub using the `image:` directive

---

## 🔐 Security Reminders

- ✅ Never commit `.env` file to git
- ✅ Use strong passwords for Redis and Elasticsearch
- ✅ Keep HuggingFace API token secure
- ✅ Rotate passwords regularly

---

**Last Updated**: 2025-01-15
