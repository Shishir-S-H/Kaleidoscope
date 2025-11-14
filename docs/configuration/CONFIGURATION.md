# Configuration Guide

**Environment variables and configuration for Kaleidoscope AI**

---

## Environment Variables

### Required Variables

Create a `.env` file in the `kaleidoscope-ai/` directory with the following:

#### Redis Configuration

```bash
REDIS_PASSWORD=your-strong-redis-password
```

#### Elasticsearch Configuration

```bash
ELASTICSEARCH_PASSWORD=your-strong-elasticsearch-password
```

#### HuggingFace API Configuration

```bash
# API Token (required)
HF_API_TOKEN=your-huggingface-api-token

# API URLs (one for each AI service)
HF_API_URL_CONTENT_MODERATION=https://your-space.hf.space/classify
HF_API_URL_IMAGE_TAGGER=https://your-space.hf.space/tag
HF_API_URL_SCENE_RECOGNITION=https://your-space.hf.space/recognize
HF_API_URL_IMAGE_CAPTIONING=https://your-space.hf.space/caption
HF_API_URL_FACE_RECOGNITION=https://your-space.hf.space/detect
```

#### Docker Registry (Production)

```bash
# Backend service registry
DOCKER_REGISTRY=ajayprabhu2004

# AI services registry
DOCKER_USERNAME=shishir01

# App version
APP_VERSION=latest
```

#### PostgreSQL (ES Sync Service)

```bash
# Option 1: JDBC URL format
SPRING_DATASOURCE_URL=jdbc:postgresql://host:port/database

# Option 2: Individual variables
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kaleidoscope
DB_USER=postgres
DB_PASSWORD=your-database-password
```

---

## Service-Specific Configuration

### Content Moderation

**Environment File**: `shared/env_templates/content_moderation.env`

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
HF_API_URL=${HF_API_URL_CONTENT_MODERATION}
HF_API_TOKEN=${HF_API_TOKEN}
```

### Image Tagger

**Environment File**: `shared/env_templates/image_tagger.env`

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
HF_API_URL=${HF_API_URL_IMAGE_TAGGER}
HF_API_TOKEN=${HF_API_TOKEN}
DEFAULT_TOP_N=5
DEFAULT_THRESHOLD=0.01
```

### Scene Recognition

**Environment File**: `shared/env_templates/scene_recognition.env`

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
HF_API_URL=${HF_API_URL_SCENE_RECOGNITION}
HF_API_TOKEN=${HF_API_TOKEN}
```

### Image Captioning

**Environment File**: `shared/env_templates/image_captioning.env`

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
HF_API_URL=${HF_API_URL_IMAGE_CAPTIONING}
HF_API_TOKEN=${HF_API_TOKEN}
```

### Face Recognition

**Environment File**: `shared/env_templates/face_recognition.env`

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
HF_API_URL=${HF_API_URL_FACE_RECOGNITION}
HF_API_TOKEN=${HF_API_TOKEN}
```

### Post Aggregator

**Configuration**:

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
AGGREGATION_WAIT_SECONDS=6
AGGREGATION_POLL_INTERVAL=0.5
```

### ES Sync

**Configuration**:

```bash
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
ES_HOST=http://elastic:${ELASTICSEARCH_PASSWORD}@elasticsearch:9200
SPRING_DATASOURCE_URL=jdbc:postgresql://...
# OR
DB_HOST=...
DB_PORT=...
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
```

---

## Docker Compose Configuration

### Development (`docker-compose.yml`)

- Uses local builds
- Volume mounts for hot-reload
- Exposes ports for local access

### Production (`docker-compose.prod.yml`)

- Pulls images from Docker Hub
- No volume mounts
- Internal network only
- Healthchecks configured

---

## Security Configuration

### Redis Security

- Password protection enabled
- Protected mode enabled
- Internal network only (production)

### Elasticsearch Security

- X-Pack security enabled
- Password authentication required
- Internal network only (production)

### Network Security

- All services on isolated Docker network
- No public database ports
- Nginx handles public traffic

---

## Configuration Validation

### Check Configuration

```bash
# Check environment variables are loaded
docker compose exec content_moderation env | grep HF_API

# Check Redis connection
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Check Elasticsearch connection
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200
```

---

## Troubleshooting Configuration

### Missing Environment Variables

**Symptoms**: Services fail to start or can't connect

**Solution**:

1. Check `.env` file exists
2. Verify all required variables are set
3. Check variable names match exactly
4. Restart services after changes

### Invalid Configuration

**Symptoms**: Services start but fail to process

**Solution**:

1. Check service logs for specific errors
2. Verify API URLs are correct
3. Check API tokens are valid
4. Test API endpoints manually

---

**For deployment configuration, see [DEPLOYMENT.md](DEPLOYMENT.md)**
