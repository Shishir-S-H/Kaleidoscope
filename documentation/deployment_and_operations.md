# Deployment & Operations Guide — kaleidoscope-ai

> **Edition:** Phase C (April 2026)  
> **Scope:** Production deployment on a Linux VPS (DigitalOcean or equivalent), CI/CD pipeline, SSL configuration, backup/restore, and monitoring.

---

## Table of Contents

1. [Production Server Specs](#1-production-server-specs)
2. [Initial Server Setup](#2-initial-server-setup)
3. [Production Environment Configuration](#3-production-environment-configuration)
4. [Docker Image Registry](#4-docker-image-registry)
5. [Deployment Methods](#5-deployment-methods)
6. [Nginx Reverse Proxy & SSL](#6-nginx-reverse-proxy--ssl)
7. [Service Startup Order & Networking](#7-service-startup-order--networking)
8. [Verification & Health Checks](#8-verification--health-checks)
9. [Backup & Restore](#9-backup--restore)
10. [Monitoring](#10-monitoring)
11. [Updating the Deployment](#11-updating-the-deployment)
12. [DigitalOcean Quick-Start](#12-digitalocean-quick-start)
13. [Security Checklist](#13-security-checklist)

---

## 1. Production Server Specs

| Attribute | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS |
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4 cores |
| Disk | 20 GB SSD | 40 GB SSD |
| Network | Public IP, ports 80 + 443 open | Same |

**Current production reference:**  
- Server: `165.232.179.167`  
- Domain: `project-kaleidoscope.tech`  
- Deployment directory: `~/Kaleidoscope/kaleidoscope-ai`

---

## 2. Initial Server Setup

### Install Docker

```bash
apt update && apt upgrade -y

curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker

docker --version
```

### Install Docker Compose v2

```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

docker-compose --version
```

### Clone the repository

```bash
cd ~
git clone https://github.com/Shishir-S-H/Kaleidoscope.git
cd Kaleidoscope/kaleidoscope-ai
```

---

## 3. Production Environment Configuration

Create `.env` from the example and fill in production values:

```bash
cp .env.example .env
nano .env
```

Full variable reference for production:

```bash
# ── Docker Registry ───────────────────────────────────────────────────────────
DOCKER_REGISTRY=ajayprabhu2004
DOCKER_USERNAME=shishir01

# ── Application ───────────────────────────────────────────────────────────────
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-backend
APP_PORT=8080
APP_NAME=kaleidoscope-backend
APP_BASE_URL=https://project-kaleidoscope.tech
CONTEXT_PATH=/kaleidoscope
SPRING_PROFILES_ACTIVE=prod
ENVIRONMENT=production

# ── Security ─────────────────────────────────────────────────────────────────
REDIS_PASSWORD=<generate with: openssl rand -base64 32>
ELASTICSEARCH_PASSWORD=<generate with: openssl rand -base64 32>
HF_API_TOKEN=hf_...your_token_here...

# ── HuggingFace API Endpoints ─────────────────────────────────────────────────
HF_API_URL_CONTENT_MODERATION=https://api-inference.huggingface.co/models/...
HF_API_URL_IMAGE_TAGGER=https://api-inference.huggingface.co/models/...
HF_API_URL_SCENE_RECOGNITION=https://api-inference.huggingface.co/models/...
HF_API_URL_IMAGE_CAPTIONING=https://api-inference.huggingface.co/models/...
HF_API_URL_FACE_RECOGNITION=https://api-inference.huggingface.co/models/...

# ── Database (Neon PostgreSQL) ────────────────────────────────────────────────
SPRING_DATASOURCE_URL=jdbc:postgresql://ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
DB_USERNAME=neondb_owner
DB_PASSWORD=<your database password>

# ── Elasticsearch ─────────────────────────────────────────────────────────────
ES_HOST=http://elastic:${ELASTICSEARCH_PASSWORD}@elasticsearch:9200

# ── Scene Recognition (optional) ─────────────────────────────────────────────
SCENE_LABELS=beach,mountains,urban,office,restaurant,forest,desert,lake,park,indoor,outdoor,rural,coastal,mountainous,tropical,arctic
```

---

## 4. Docker Image Registry

| Component | Registry | Image Tag Pattern |
|-----------|----------|------------------|
| Java backend | `ajayprabhu2004` | `kaleidoscope:backend-<APP_VERSION>` |
| AI services (7) | `shishir01` | `kaleidoscope-<service>:latest` |
| Redis | Docker Hub official | `redis:alpine` |
| Elasticsearch | Docker Hub official | `elasticsearch:8.10.2` |
| Nginx | Docker Hub official | `nginx:alpine` |
| Certbot | Docker Hub official | `certbot/certbot` |

Pull a specific backend image manually:
```bash
docker pull ajayprabhu2004/kaleidoscope:backend-latest
```

Pull a specific AI service image manually:
```bash
docker pull shishir01/kaleidoscope-content_moderation:latest
```

---

## 5. Deployment Methods

### Method A — Deployment scripts (recommended)

Initial server provisioning (run once from your local machine):

```bash
cd kaleidoscope-ai
./scripts/deployment/setup-production.sh
```

Subsequent deployments after code changes:

```bash
./scripts/deployment/deploy-production.sh
```

From the server directly:

```bash
cd ~/Kaleidoscope/kaleidoscope-ai
./scripts/deployment/deploy.sh
```

### Method B — Manual deployment

```bash
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

## 6. Nginx Reverse Proxy & SSL

### Nginx configuration

File: `nginx/nginx.conf`

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

### Initial SSL certificate (Let's Encrypt via Certbot)

```bash
# Start Nginx first (HTTP only, for ACME challenge)
docker-compose -f docker-compose.prod.yml up -d nginx

# Issue the certificate
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d project-kaleidoscope.tech \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Restart Nginx with SSL enabled
docker-compose -f docker-compose.prod.yml restart nginx
```

### Automatic certificate renewal

Add to the server's crontab (`crontab -e`):

```cron
0 2 * * * cd ~/Kaleidoscope/kaleidoscope-ai && \
  docker-compose -f docker-compose.prod.yml run --rm certbot renew && \
  docker-compose -f docker-compose.prod.yml restart nginx
```

---

## 7. Service Startup Order & Networking

### Startup order (defined by `depends_on` in `docker-compose.prod.yml`)

1. **Infrastructure:** Redis → Elasticsearch (both with healthchecks)
2. **Backend:** Spring Boot app (waits for Redis + Elasticsearch healthy)
3. **AI services (parallel):** content_moderation, image_tagger, scene_recognition, image_captioning, face_recognition, face_matcher, profile_enrollment, post_aggregator, es_sync, dlq_processor, federated_aggregator
4. **Reverse proxy:** Nginx (waits for app)

### Network and port mapping

| Port | Binding | Purpose |
|------|---------|---------|
| `80` | `0.0.0.0:80` | HTTP → HTTPS redirect (Nginx) |
| `443` | `0.0.0.0:443` | HTTPS (Nginx) |
| `6379` | `127.0.0.1:6379` | Redis — SSH tunnel access only |
| `9200` | `127.0.0.1:9200` | Elasticsearch — SSH tunnel access only |

All services communicate internally via the `kaleidoscope-network` bridge network using Docker service names.

If you need external access to Redis or Elasticsearch for debugging, use an SSH tunnel:

```bash
# Redis tunnel
ssh -L 6379:localhost:6379 root@165.232.179.167

# Elasticsearch tunnel
ssh -L 9200:localhost:9200 root@165.232.179.167
```

---

## 8. Verification & Health Checks

```bash
# All services running
docker-compose -f docker-compose.prod.yml ps

# Redis (should return PONG)
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Elasticsearch cluster health (should be yellow or green)
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health

# Java backend actuator (via Nginx, requires HTTPS)
curl https://project-kaleidoscope.tech/kaleidoscope/actuator/health

# Python service health endpoints (one per worker, exposed on HEALTH_PORT=8080 inside Docker network)
# GET /health — liveness
# GET /ready  — readiness
# GET /metrics — counters + latency percentiles

# Container resource usage
docker stats --no-stream
```

---

## 9. Backup & Restore

### Create a backup

```bash
# From local machine (uses the backup script)
./scripts/deployment/backup-production-configs.sh
```

Backs up:
- `.env`
- `nginx/nginx.conf`
- `docker-compose.prod.yml`
- Certbot SSL certificates
- File listings

Saved to: `production-configs/<timestamp>/`

### Restore from backup

```bash
./scripts/deployment/setup-production.sh <timestamp>

# Example
./scripts/deployment/setup-production.sh 20250115_143022
```

---

## 10. Monitoring

### Service logs

```bash
docker-compose -f docker-compose.prod.yml logs -f [service_name]
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Continuous monitoring script

```bash
./scripts/monitoring/monitor_services.sh
```

### Log aggregation (recommended for production)

All Python workers emit structured JSON logs compatible with:
- **Loki** (Grafana stack)
- **CloudWatch** (AWS)
- **Datadog** (cloud-hosted)
- Any JSON-capable log aggregator

### Disk and memory

```bash
df -h
free -h
docker system df  # Docker-specific disk usage
```

### Recommended external tooling

| Tool | Purpose |
|------|---------|
| Grafana + Prometheus | Metrics dashboards |
| Loki | Log aggregation |
| UptimeRobot / Pingdom | External uptime monitoring |
| htop | Real-time server resource monitoring |

---

## 11. Updating the Deployment

### After GitHub Actions CI/CD builds new images

CI/CD (`.github/workflows/build-and-push.yml`) **builds and pushes** Docker images to Docker Hub on every push to `main`. It does **not** SSH into the droplet. Once the workflow completes, deploy from a machine with SSH access:

```bash
./scripts/deployment/deploy-production.sh
```

That script syncs git on the server, applies **V3/V4** migrations when not skipped, recreates **`recommendations_knn`**, **`face_search`**, and **`known_faces_index`** in Elasticsearch, pulls images, and restarts compose. See `documentation/handoff_teammate_java_kaleidoscope_repo.md` for a full checklist.

### Rolling update of a single service

```bash
docker pull shishir01/kaleidoscope-content_moderation:latest
docker-compose -f docker-compose.prod.yml up -d --no-deps content_moderation
```

### Pull latest code on the server

```bash
cd ~/Kaleidoscope
git pull origin main
cd kaleidoscope-ai
docker-compose -f docker-compose.prod.yml up -d
```

---

## 12. DigitalOcean Quick-Start

If you are setting up a new DigitalOcean droplet:

### Recommended droplet configuration

| Setting | Value |
|---------|-------|
| Image | Ubuntu 22.04 LTS |
| Plan | Basic — $24/month (4 GB RAM, 2 vCPU, 80 GB SSD) |
| Region | Closest to your users |
| Auth | SSH key (recommended over password) |
| Hostname | `kaleidoscope-ai` |

**Student credits:** If eligible, claim $200 DigitalOcean credit via the [GitHub Student Developer Pack](https://education.github.com/pack).

### Firewall setup (UFW)

```bash
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw enable
ufw status
```

### Elasticsearch OOM on low-RAM droplets

If Elasticsearch exits with code `137` (OOM kill):

```bash
# Cap the JVM heap to 1 GB — add to .env
ES_JAVA_OPTS=-Xms1g -Xmx1g

docker-compose -f docker-compose.prod.yml restart elasticsearch
```

Alternatively, add swap space:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Cost estimate

| Resource | Cost |
|----------|------|
| Basic droplet (4 GB RAM) | ~$24/month |
| With student credits | ~Free for first 8 months |

---

## 13. Security Checklist

### Implemented in `docker-compose.prod.yml`

- ✅ Redis password-protected (`requirepass`)
- ✅ Elasticsearch X-Pack security enabled (`xpack.security.enabled=true`)
- ✅ Redis and Elasticsearch ports bound to `127.0.0.1` only (not publicly exposed)
- ✅ All services on isolated Docker bridge network (`kaleidoscope-network`)
- ✅ HTTPS enforced via Nginx + Let's Encrypt
- ✅ HTTP → HTTPS redirect

### Recommended hardening

- Add `bucket4j` rate limiting to Java auth endpoints (GAP-8 in `audit_report_and_tech_debt.md`)
- Replace 10-char email verification tokens with 32-byte `SecureRandom` tokens (GAP-9)
- Migrate React access token from `localStorage` to HTTP-only cookies (GAP-16)
- Set up automated security updates: `unattended-upgrades`
- Rotate credentials every 90 days
- Review container logs weekly for anomalous access patterns
