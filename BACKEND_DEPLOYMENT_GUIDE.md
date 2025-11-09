# 🚀 Backend Deployment Guide

**Deploying Backend Service with AI Services on DigitalOcean**

---

## 📋 Prerequisites

- DigitalOcean droplet with Docker and Docker Compose installed
- Git repository cloned to `~/Kaleidoscope/` or `~/kaleidoscope/`
- `.env` file in the root `Kaleidoscope/` directory
- Docker registry access (`rajay04`)

---

## 🏗️ Server Directory Structure

```
~/Kaleidoscope/                    # Root directory (or ~/kaleidoscope/)
├── .env                          # Environment variables (here)
├── backend/                      # Backend service
│   └── docker-compose.yml
└── kaleidoscope-ai/              # AI services
    ├── docker-compose.prod.yml   # Production compose file
    └── services/                 # AI microservices
```

---

## 📝 Environment Variables

Ensure your `.env` file in `~/Kaleidoscope/` contains:

```bash
# Docker Registry Configuration
# DOCKER_REGISTRY: For backend service (ajayprabhu2004/rajay04)
DOCKER_REGISTRY=ajayprabhu2004
# OR: DOCKER_REGISTRY=rajay04

# DOCKER_USERNAME: For AI services (shishir01) - currently AI services are built locally
DOCKER_USERNAME=shishir01

# Redis Configuration (REQUIRED)
REDIS_PASSWORD=your-redis-password

# Elasticsearch Configuration (REQUIRED)
ELASTICSEARCH_PASSWORD=your-elasticsearch-password

# Backend Application (optional - defaults provided)
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-app
APP_PORT=8080

# HuggingFace API (REQUIRED for AI services)
HF_API_TOKEN=your-huggingface-token
HF_API_URL_CONTENT_MODERATION=https://...
HF_API_URL_IMAGE_TAGGER=https://...
HF_API_URL_SCENE_RECOGNITION=https://...
HF_API_URL_IMAGE_CAPTIONING=https://...
HF_API_URL_FACE_RECOGNITION=https://...
```

---

## 🚀 Deployment Steps

### Step 1: SSH into DigitalOcean Server

```bash
ssh root@your-server-ip
```

### Step 2: Navigate to Project Directory

```bash
# If using ~/Kaleidoscope/
cd ~/Kaleidoscope

# OR if using ~/kaleidoscope/
cd ~/kaleidoscope
```

### Step 3: Pull Latest Changes

```bash
git pull origin main
```

### Step 4: Verify .env File

```bash
# Check if .env exists
ls -la .env

# If missing, create it
nano .env
# Paste your environment variables and save (Ctrl+X, Y, Enter)
```

### Step 5: Navigate to AI Services Directory

```bash
cd kaleidoscope-ai
```

### Step 6: Pull Backend Docker Image

```bash
# Pull backend image from ajayprabhu2004/rajay04 registry
# Replace 'ajayprabhu2004' with your DOCKER_REGISTRY value
docker pull ajayprabhu2004/kaleidoscope:backend-latest
# OR if using rajay04:
# docker pull rajay04/kaleidoscope:backend-latest
```

### Step 7: Start Backend Service

**Option A: Start only the backend (if AI services are already running)**

```bash
docker-compose -f docker-compose.prod.yml up -d app
```

**Option B: Start everything together (AI services + backend)**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Step 8: Verify Deployment

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps app

# Check logs
docker-compose -f docker-compose.prod.yml logs app --tail=50

# Test backend health endpoint
curl http://localhost:8080/actuator/health

# View all running services
docker-compose -f docker-compose.prod.yml ps
```

---

## 🔍 Verification Checklist

- [ ] Backend container is running (`kaleidoscope-app`)
- [ ] Backend is accessible on port 8080
- [ ] Backend can connect to Redis
- [ ] Backend can connect to Elasticsearch
- [ ] All services are on the same Docker network
- [ ] No errors in logs

---

## 🐛 Troubleshooting

### Backend Fails to Start

```bash
# Check logs for errors
docker-compose -f docker-compose.prod.yml logs app

# Verify Redis is healthy
docker exec redis redis-cli -a $REDIS_PASSWORD ping

# Verify Elasticsearch is accessible
curl -u elastic:$ELASTICSEARCH_PASSWORD http://localhost:9200/_cluster/health
```

### Image Pull Fails

```bash
# Login to Docker Hub if needed
docker login

# Verify image name/tag (replace with your DOCKER_REGISTRY)
docker pull ajayprabhu2004/kaleidoscope:backend-latest
# OR if using rajay04:
# docker pull rajay04/kaleidoscope:backend-latest
```

### Network Issues

```bash
# Check if services are on the same network
docker network inspect kaleidoscope-ai_kaleidoscope-network

# Verify backend can reach Redis
docker exec kaleidoscope-app ping redis

# Verify backend can reach Elasticsearch
docker exec kaleidoscope-app ping elasticsearch
```

### Port Already in Use

```bash
# Check what's using port 8080
sudo lsof -i :8080

# Or change APP_PORT in .env file
APP_PORT=8081
```

---

## 🔄 Updating Backend

### Pull Latest Image

```bash
cd ~/Kaleidoscope/kaleidoscope-ai
# Pull backend image (replace with your DOCKER_REGISTRY)
docker pull ajayprabhu2004/kaleidoscope:backend-latest
# OR if using rajay04:
# docker pull rajay04/kaleidoscope:backend-latest
docker-compose -f docker-compose.prod.yml up -d app
```

### Restart Backend

```bash
cd ~/Kaleidoscope/kaleidoscope-ai
docker-compose -f docker-compose.prod.yml restart app
```

---

## 📊 Monitoring

### View Resource Usage

```bash
docker stats --no-stream
```

### View Logs

```bash
# Backend logs
docker-compose -f docker-compose.prod.yml logs -f app

# All services logs
docker-compose -f docker-compose.prod.yml logs -f
```

### Check Service Health

```bash
# Backend health
curl http://localhost:8080/actuator/health

# Redis health
docker exec redis redis-cli -a $REDIS_PASSWORD ping

# Elasticsearch health
curl -u elastic:$ELASTICSEARCH_PASSWORD http://localhost:9200/_cluster/health
```

---

## 🔐 Security Notes

- Backend uses the same Redis and Elasticsearch as AI services
- All services communicate via Docker network (internal)
- Port 8080 is exposed publicly (backend API)
- Ensure `.env` file is not committed to git
- Use strong passwords for Redis and Elasticsearch

---

## 📞 Support

If you encounter issues:

1. Check logs: `docker-compose -f docker-compose.prod.yml logs app`
2. Verify environment variables in `.env`
3. Ensure all dependencies (Redis, Elasticsearch) are running
4. Check network connectivity between services

---

**Last Updated:** 2025-01-15
