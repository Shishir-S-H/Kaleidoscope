# Production Deployment Guide

**Complete guide for deploying Kaleidoscope AI to production**

---

## 🎯 Overview

This guide covers the complete production deployment setup for Kaleidoscope AI on DigitalOcean (or similar VPS).

**Current Production Server**: `165.232.179.167`  
**Domain**: `project-kaleidoscope.tech`  
**Deployment Directory**: `~/Kaleidoscope`

---

## 📋 Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04+ or similar Linux distribution
- **RAM**: Minimum 4GB (8GB recommended)
- **CPU**: 2+ cores
- **Disk**: 20GB+ free space
- **Network**: Public IP with ports 80, 443 open

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Git
- SSH access (with key authentication recommended)

---

## 🚀 Initial Server Setup

### 1. Connect to Server

```bash
ssh root@165.232.179.167
```

### 2. Install Docker

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

# Verify installation
docker --version
```

### 3. Install Docker Compose

```bash
# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verify installation
docker-compose --version
```

### 4. Clone Repository

```bash
cd ~
git clone https://github.com/Shishir-S-H/Kaleidoscope.git
cd Kaleidoscope/kaleidoscope-ai
```

---

## ⚙️ Configuration Setup

### 1. Create Environment File

```bash
# Copy example
cp .env.example .env

# Edit with your values
nano .env
```

### 2. Required Environment Variables

**Docker Configuration**:
```bash
DOCKER_REGISTRY=ajayprabhu2004
DOCKER_USERNAME=shishir01
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-backend
APP_PORT=8080
```

**Application Configuration**:
```bash
APP_NAME=kaleidoscope-backend
APP_BASE_URL=https://project-kaleidoscope.tech
CONTEXT_PATH=/kaleidoscope
SPRING_PROFILES_ACTIVE=prod
```

**Security**:
```bash
REDIS_PASSWORD=your-strong-redis-password
ELASTICSEARCH_PASSWORD=your-strong-elasticsearch-password
HF_API_TOKEN=your-huggingface-api-token
```

**HuggingFace API URLs**:
```bash
HF_API_URL_CONTENT_MODERATION=https://api-inference.huggingface.co/models/...
HF_API_URL_IMAGE_TAGGER=https://api-inference.huggingface.co/models/...
HF_API_URL_SCENE_RECOGNITION=https://api-inference.huggingface.co/models/...
HF_API_URL_IMAGE_CAPTIONING=https://api-inference.huggingface.co/models/...
HF_API_URL_FACE_RECOGNITION=https://api-inference.huggingface.co/models/...
```

**Database (Neon PostgreSQL)**:
```bash
SPRING_DATASOURCE_URL=jdbc:postgresql://ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
DB_USERNAME=neondb_owner
DB_PASSWORD=your-database-password
```

**Elasticsearch**:
```bash
ES_HOST=http://elastic:${ELASTICSEARCH_PASSWORD}@elasticsearch:9200
```

### 3. Configure Nginx

**File**: `nginx/nginx.conf`

```nginx
events {
    worker_connections 1024;
}

http {
    resolver 8.8.8.8;

    server {
        listen 80;
        server_name project-kaleidoscope.tech;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name project-kaleidoscope.tech;

        ssl_certificate /etc/letsencrypt/live/project-kaleidoscope.tech/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/project-kaleidoscope.tech/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        location / {
            proxy_pass http://app:8080/kaleidoscope/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## 🐳 Docker Images

### Image Sources

**Backend**:
- Registry: `ajayprabhu2004`
- Image: `kaleidoscope:backend-latest`
- Pull: `docker pull ajayprabhu2004/kaleidoscope:backend-latest`

**AI Services** (7 services):
- Registry: `shishir01`
- Images: `kaleidoscope-{service}:latest`
- Services: `content_moderation`, `image_tagger`, `scene_recognition`, `image_captioning`, `face_recognition`, `post_aggregator`, `es_sync`
- Pull: `docker pull shishir01/kaleidoscope-content_moderation:latest` (repeat for each)

**Infrastructure**:
- Redis: `redis:alpine`
- Elasticsearch: `elasticsearch:8.10.2`
- Nginx: `nginx:alpine`
- Certbot: `certbot/certbot`

---

## 🚀 Deployment Methods

### Method 1: Using Deployment Scripts (Recommended)

**From Local Machine**:

```bash
# Navigate to project
cd kaleidoscope-ai

# Initial setup
./scripts/deployment/setup-production.sh

# Regular deployment (after code changes)
./scripts/deployment/deploy-production.sh
```

**From Server**:

```bash
cd ~/Kaleidoscope/kaleidoscope-ai

# Deploy
./scripts/deployment/deploy.sh
```

### Method 2: Manual Deployment

```bash
# SSH to server
ssh root@165.232.179.167
cd ~/Kaleidoscope/kaleidoscope-ai

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Stop existing services
docker-compose -f docker-compose.prod.yml down

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```

---

## 🔒 SSL Certificate Setup

### Initial Certificate Generation

```bash
# Start services without SSL first
docker-compose -f docker-compose.prod.yml up -d nginx

# Generate certificate
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d project-kaleidoscope.tech \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Restart nginx with SSL
docker-compose -f docker-compose.prod.yml restart nginx
```

### Certificate Renewal

Certbot certificates expire every 90 days. Set up automatic renewal:

```bash
# Add to crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * cd ~/Kaleidoscope/kaleidoscope-ai && docker-compose -f docker-compose.prod.yml run --rm certbot renew && docker-compose -f docker-compose.prod.yml restart nginx
```

---

## 📊 Service Architecture

### Service Startup Order

1. **Infrastructure Layer**:
   - Redis (with healthcheck)
   - Elasticsearch (with healthcheck)

2. **Backend Layer**:
   - Spring Boot Application (waits for Redis/Elasticsearch)

3. **AI Services Layer** (parallel):
   - Content Moderation
   - Image Tagger
   - Scene Recognition
   - Image Captioning
   - Face Recognition
   - Post Aggregator
   - ES Sync

4. **Reverse Proxy Layer**:
   - Nginx (waits for app)

### Network Architecture

- **Docker Network**: `kaleidoscope-network` (bridge)
- **Internal Communication**: Services communicate via Docker service names
- **External Access**: Only Nginx (ports 80, 443) exposed publicly
- **Redis/Elasticsearch**: Exposed only to localhost (127.0.0.1) for SSH tunnel access

### Port Mapping

- **80**: HTTP (redirects to HTTPS)
- **443**: HTTPS (Nginx)
- **127.0.0.1:6379**: Redis (SSH tunnel only)
- **127.0.0.1:9200**: Elasticsearch (SSH tunnel only)

---

## ✅ Verification

### Check Service Status

```bash
# All services
docker-compose -f docker-compose.prod.yml ps

# Specific service
docker-compose -f docker-compose.prod.yml ps [service_name]
```

### Check Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs

# Specific service
docker-compose -f docker-compose.prod.yml logs -f [service_name]

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Health Checks

```bash
# Redis
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Elasticsearch
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health

# Backend
curl https://project-kaleidoscope.tech/kaleidoscope/actuator/health

# Nginx
curl -I https://project-kaleidoscope.tech
```

### Monitor Resources

```bash
# Container stats
docker stats

# Disk usage
df -h

# Memory usage
free -h
```

---

## 🔄 Update Deployment

### After Code Changes

1. **CI/CD Builds Images**: GitHub Actions builds and pushes to Docker Hub
2. **Wait for CI/CD**: Ensure all workflows complete successfully
3. **Deploy to Production**:
   ```bash
   ./scripts/deployment/deploy-production.sh
   ```

### Manual Image Update

```bash
# Pull specific service
docker pull shishir01/kaleidoscope-content_moderation:latest

# Restart service
docker-compose -f docker-compose.prod.yml up -d --no-deps content_moderation
```

---

## 💾 Backup and Recovery

### Backup Configuration

```bash
# From local machine
./scripts/deployment/backup-production-configs.sh
```

**Backs up**:
- `.env` file
- `nginx/nginx.conf`
- `docker-compose.prod.yml`
- Certbot SSL certificates
- File listings

**Location**: `production-configs/{timestamp}/`

### Restore from Backup

```bash
# From local machine
./scripts/deployment/setup-production.sh {timestamp}
```

Example:
```bash
./scripts/deployment/setup-production.sh 20250115_143022
```

---

## 🛠️ Troubleshooting

### Services Won't Start

1. **Check Docker**:
   ```bash
   docker info
   systemctl status docker
   ```

2. **Check Ports**:
   ```bash
   netstat -tulpn | grep -E '80|443|6379|9200'
   ```

3. **Check Disk Space**:
   ```bash
   df -h
   docker system df
   ```

4. **Check Logs**:
   ```bash
   docker-compose -f docker-compose.prod.yml logs
   ```

### Images Not Found

1. **Verify Images Exist**:
   ```bash
   docker pull ajayprabhu2004/kaleidoscope:backend-latest
   docker pull shishir01/kaleidoscope-content_moderation:latest
   ```

2. **Check Docker Hub Access**:
   ```bash
   docker login
   ```

### SSL Certificate Issues

1. **Check Certificate**:
   ```bash
   docker-compose -f docker-compose.prod.yml exec nginx ls -la /etc/letsencrypt/live/
   ```

2. **Renew Certificate**:
   ```bash
   docker-compose -f docker-compose.prod.yml run --rm certbot renew
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

### Connection Errors

1. **Check Network**:
   ```bash
   docker network inspect kaleidoscope-network
   ```

2. **Test Internal Connectivity**:
   ```bash
   docker exec redis ping elasticsearch
   docker exec app curl http://elasticsearch:9200
   ```

---

## 🔐 Security Best Practices

### ✅ Implemented

- ✅ Redis password protection
- ✅ Elasticsearch X-Pack security
- ✅ Services on isolated Docker network
- ✅ No public database ports
- ✅ SSL/TLS encryption (HTTPS)
- ✅ Nginx reverse proxy

### 📝 Recommendations

- Use secrets management (e.g., Docker Secrets, HashiCorp Vault)
- Implement firewall rules (UFW)
- Regular security updates
- Monitor logs for suspicious activity
- Use strong passwords
- Rotate credentials regularly

---

## 📈 Monitoring

### Service Monitoring

```bash
# Use monitoring script
./scripts/monitoring/monitor_services.sh
```

### Log Aggregation

Consider setting up:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Prometheus + Grafana**
- **CloudWatch** (if using AWS)

---

## 🔗 Related Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - General deployment guide
- **[../configuration/CONFIGURATION.md](../configuration/CONFIGURATION.md)** - Configuration reference
- **[../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)** - Troubleshooting guide
- **[scripts/deployment/README.md](../../scripts/deployment/README.md)** - Deployment scripts documentation

---

## 📞 Support

### Quick Commands

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart service
docker-compose -f docker-compose.prod.yml restart [service_name]

# Stop all
docker-compose -f docker-compose.prod.yml down

# Start all
docker-compose -f docker-compose.prod.yml up -d
```

---

**Last Updated**: January 2025  
**Production Server**: 165.232.179.167  
**Domain**: project-kaleidoscope.tech

