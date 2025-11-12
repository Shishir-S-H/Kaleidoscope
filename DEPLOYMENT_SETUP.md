# Deployment Setup Summary

This document summarizes the unified Docker Compose and CI/CD setup for Kaleidoscope AI services.

## What Was Implemented

### 1. Unified Docker Compose File

**File**: `docker-compose.prod.yml`

- **Consolidated** all services into a single production-ready compose file
- **Proper startup order** with healthchecks:

  1. Infrastructure: `redis` → `elasticsearch`
  2. Backend: `app` (depends on redis/elasticsearch)
  3. AI Services: All 7 services (depend on redis)
  4. Reverse Proxy: `nginx` (depends on app)

- **Image Strategy**:
  - Backend: Pulls from `ajayprabhu2004/kaleidoscope:backend-latest`
  - AI Services: Pull from `shishir01/kaleidoscope-{service}:latest`
  - Infrastructure: Official images

### 2. CI/CD Workflow

**File**: `.github/workflows/build-and-push.yml`

- Already configured to build and push AI services to Docker Hub
- Uses `shishir01` registry (via `DOCKER_USERNAME` secret)
- Backend CI/CD is in separate repository (no changes needed)

### 3. Deployment Scripts

Three new scripts in `scripts/deployment/`:

#### `backup-production-configs.sh`

- Backs up all production configs from server
- Saves to `production-configs/{timestamp}/`
- Includes: `.env`, `nginx.conf`, certbot certificates

#### `deploy-production.sh`

- Pulls latest images from Docker Hub
- Restarts services with new images
- Performs health checks

#### `setup-production.sh`

- Sets up fresh production environment
- Or restores from backup
- Copies configs and starts services

## Directory Structure

```
kaleidoscope-ai/
├── docker-compose.prod.yml          # Unified production compose
├── scripts/
│   └── deployment/
│       ├── backup-production-configs.sh
│       ├── deploy-production.sh
│       ├── setup-production.sh
│       └── README.md
├── production-configs/              # Backup storage (gitignored)
│   └── README.md
└── .github/
    └── workflows/
        └── build-and-push.yml       # CI/CD workflow
```

## Production Server Structure

```
~/kaleidoscope/                      # Single directory
├── docker-compose.prod.yml          # Unified compose file
├── .env                             # Environment variables
├── nginx/
│   └── nginx.conf                   # Nginx configuration
└── (certbot volumes managed by Docker)
```

## Quick Start

### Initial Setup

1. **Backup existing configs** (if any):

   ```bash
   cd kaleidoscope-ai
   ./scripts/deployment/backup-production-configs.sh
   ```

2. **Set up production**:
   ```bash
   ./scripts/deployment/setup-production.sh
   ```
   Or restore from backup:
   ```bash
   ./scripts/deployment/setup-production.sh {timestamp}
   ```

### Regular Deployment

1. **Push code** → CI/CD builds and pushes images
2. **Deploy to production**:
   ```bash
   ./scripts/deployment/deploy-production.sh
   ```

## Image Naming Convention

- **Backend**: `ajayprabhu2004/kaleidoscope:backend-latest`
- **AI Services**: `shishir01/kaleidoscope-{service}:latest`
  - `shishir01/kaleidoscope-content_moderation:latest`
  - `shishir01/kaleidoscope-image_tagger:latest`
  - `shishir01/kaleidoscope-scene_recognition:latest`
  - `shishir01/kaleidoscope-image_captioning:latest`
  - `shishir01/kaleidoscope-face_recognition:latest`
  - `shishir01/kaleidoscope-post_aggregator:latest`
  - `shishir01/kaleidoscope-es_sync:latest`

## Service Startup Order

```
Layer 1: Infrastructure
├── redis (healthcheck: 10s start period)
└── elasticsearch (healthcheck: 60s start period)

Layer 2: Backend
└── app (waits for redis[healthy] + elasticsearch[healthy])

Layer 3: AI Services (parallel, all wait for redis[healthy])
├── content_moderation
├── image_tagger
├── scene_recognition
├── image_captioning
├── face_recognition
├── post_aggregator
└── es_sync (also waits for elasticsearch[healthy])

Layer 4: Reverse Proxy
└── nginx (waits for app[started])
```

## Environment Variables

Required in `.env` file on production server:

```bash
# Docker Registries
DOCKER_REGISTRY=ajayprabhu2004
DOCKER_USERNAME=shishir01
APP_VERSION=latest

# Security
REDIS_PASSWORD=your-redis-password
ELASTICSEARCH_PASSWORD=your-elasticsearch-password

# HuggingFace API
HF_API_TOKEN=your-token
HF_API_URL_CONTENT_MODERATION=https://...
HF_API_URL_IMAGE_TAGGER=https://...
HF_API_URL_SCENE_RECOGNITION=https://...
HF_API_URL_IMAGE_CAPTIONING=https://...
HF_API_URL_FACE_RECOGNITION=https://...

# Backend Configuration
SPRING_DATASOURCE_URL=jdbc:postgresql://...
DB_USERNAME=...
DB_PASSWORD=...
# ... (other backend configs)
```

## Security Notes

- ✅ Production configs are gitignored
- ✅ SSH access required for deployment scripts
- ✅ All services on isolated Docker network
- ✅ Redis/Elasticsearch ports only exposed to localhost
- ✅ Nginx handles public traffic

## Troubleshooting

See `scripts/deployment/README.md` for detailed troubleshooting guide.

## Next Steps

1. **Test the unified compose locally** (if possible)
2. **Backup existing production configs** before first deployment
3. **Deploy using setup script** to initialize production
4. **Verify all services start correctly**
5. **Set up monitoring** (optional)

---

**Last Updated**: 2025-01-15
