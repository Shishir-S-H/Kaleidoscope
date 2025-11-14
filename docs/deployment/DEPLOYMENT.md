# Deployment Guide

**Deployment guide for Kaleidoscope AI services**

---

## Development Deployment

### Prerequisites

- Docker Desktop
- Python 3.8+
- Internet connection

### Quick Start

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f [service_name]
```

### Environment Variables

Create `.env` file in `kaleidoscope-ai/` directory:

```bash
# Redis
REDIS_PASSWORD=your-redis-password

# Elasticsearch
ELASTICSEARCH_PASSWORD=your-elasticsearch-password

# HuggingFace API
HF_API_TOKEN=your-huggingface-token
HF_API_URL_CONTENT_MODERATION=https://...
HF_API_URL_IMAGE_TAGGER=https://...
HF_API_URL_SCENE_RECOGNITION=https://...
HF_API_URL_IMAGE_CAPTIONING=https://...
HF_API_URL_FACE_RECOGNITION=https://...
```

See **[../configuration/CONFIGURATION.md](../configuration/CONFIGURATION.md)** for complete configuration.

---

## Production Deployment

### Quick Links

- **[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)** - Complete production deployment guide
- **[scripts/deployment/README.md](../../scripts/deployment/README.md)** - Deployment scripts documentation

### Prerequisites

- Docker and Docker Compose on server
- SSH access to production server (`root@165.232.179.167`)
- Docker Hub access for images

### Production Server Details

- **Server**: `165.232.179.167`
- **Domain**: `project-kaleidoscope.tech`
- **Directory**: `~/Kaleidoscope/kaleidoscope-ai`

### Deployment Scripts

**Location**: `scripts/deployment/`

#### Initial Setup

```bash
# Backup existing configs (if any)
./scripts/deployment/backup-production-configs.sh

# Set up production environment
./scripts/deployment/setup-production.sh
```

#### Regular Deployment

```bash
# Deploy latest images
./scripts/deployment/deploy-production.sh
```

### Production Configuration

**File**: `docker-compose.prod.yml`

**Services**:

- Infrastructure: Redis, Elasticsearch
- Backend: Spring Boot application
- AI Services: 7 microservices (content_moderation, image_tagger, scene_recognition, image_captioning, face_recognition, post_aggregator, es_sync)
- Reverse Proxy: Nginx
- SSL: Certbot

**Image Sources**:

- Backend: `ajayprabhu2004/kaleidoscope:backend-latest`
- AI Services: `shishir01/kaleidoscope-{service}:latest`
- Infrastructure: Official images (redis:alpine, elasticsearch:8.10.2, nginx:alpine, certbot/certbot)

### Environment Variables (Production)

Create `.env` file on production server:

```bash
# Docker Registries
DOCKER_REGISTRY=ajayprabhu2004
DOCKER_USERNAME=shishir01
APP_VERSION=latest

# Security
REDIS_PASSWORD=strong-redis-password
ELASTICSEARCH_PASSWORD=strong-elasticsearch-password

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
```

---

## Service Startup Order

1. **Infrastructure** (Redis, Elasticsearch) - with healthchecks
2. **Backend** - waits for infrastructure to be healthy
3. **AI Services** - wait for Redis to be healthy
4. **Nginx** - waits for app to start

---

## Verification

### Check Services

```bash
# Check all services
docker compose -f docker-compose.prod.yml ps

# Check specific service
docker compose -f docker-compose.prod.yml ps [service_name]
```

### Check Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs

# Specific service
docker compose -f docker-compose.prod.yml logs [service_name]

# Follow logs
docker compose -f docker-compose.prod.yml logs -f [service_name]
```

### Health Checks

```bash
# Redis
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Elasticsearch
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200

# Backend (if health endpoint available)
curl http://localhost:8080/actuator/health
```

---

## CI/CD

### GitHub Actions

The repository includes CI/CD workflows that:

- Build all 7 AI service images
- Push to Docker Hub (shishir01 registry)
- Tag with `latest`

### Manual Deployment

If CI/CD is not available:

```bash
# Build images locally
docker build -t shishir01/kaleidoscope-content_moderation:latest ./services/content_moderation
# ... repeat for all services

# Push to Docker Hub
docker push shishir01/kaleidoscope-content_moderation:latest
# ... repeat for all services

# Deploy to production
./scripts/deployment/deploy-production.sh
```

---

## Troubleshooting

### Services Won't Start

1. Check Docker is running
2. Check ports are available
3. Check disk space and memory
4. Check logs for errors

### Images Not Found

1. Verify images exist on Docker Hub
2. Check Docker Hub credentials
3. Verify image names match configuration

### Connection Errors

1. Check environment variables
2. Verify network connectivity
3. Check service logs

See **[../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)** for detailed troubleshooting.

---

## Backup and Recovery

### Backup Production Configs

```bash
# From local machine
./scripts/deployment/backup-production-configs.sh
```

**Backs up**:
- `.env` file (environment variables)
- `nginx/nginx.conf` (Nginx configuration)
- `docker-compose.prod.yml` (Docker Compose file)
- Certbot SSL certificates
- File listings

**Location**: `production-configs/{timestamp}/`

### Restore from Backup

```bash
# Restore from specific backup
./scripts/deployment/setup-production.sh {timestamp}

# Example
./scripts/deployment/setup-production.sh 20250115_143022
```

---

## Security Considerations

- ✅ Redis password protection enabled
- ✅ Elasticsearch X-Pack security enabled
- ✅ Services on isolated Docker network (`kaleidoscope-network`)
- ✅ Production configs gitignored
- ✅ No public database ports (Redis/Elasticsearch only on localhost)
- ✅ SSL/TLS encryption (HTTPS via Let's Encrypt)
- ✅ Nginx reverse proxy with proper headers

---

**For configuration details, see [../configuration/CONFIGURATION.md](../configuration/CONFIGURATION.md)**
