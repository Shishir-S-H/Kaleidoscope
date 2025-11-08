# Security Setup Guide

**Date**: January 15, 2025  
**Status**: ✅ Production-Ready Security Configuration

---

## 🔒 Security Improvements

### 1. Redis Security

- ✅ **Password Protection**: Redis now requires authentication
- ✅ **Protected Mode**: Enabled to prevent unauthorized access
- ✅ **No Public Port**: Redis port removed from public exposure in production
- ✅ **Internal Network Only**: Redis only accessible within Docker network

### 2. Elasticsearch Security

- ✅ **X-Pack Security**: Enabled with password authentication
- ✅ **No Public Port**: Elasticsearch ports removed from public exposure in production (optional)
- ✅ **Internal Network Only**: Elasticsearch only accessible within Docker network

### 3. Network Security

- ✅ **Docker Bridge Network**: All services communicate via isolated Docker network
- ✅ **No Public Database Ports**: Database services not exposed publicly

---

## 📋 Required Environment Variables

Create a `.env` file in the `kaleidoscope-ai` directory with the following variables:

```bash
# Docker Hub Configuration
DOCKER_USERNAME=your-dockerhub-username

# Redis Configuration (REQUIRED)
REDIS_PASSWORD=your-strong-redis-password-here

# Elasticsearch Configuration (REQUIRED)
ELASTICSEARCH_PASSWORD=your-strong-elasticsearch-password-here

# HuggingFace API Configuration (REQUIRED)
HF_API_TOKEN=your-huggingface-api-token-here

# HuggingFace API URLs (REQUIRED - one for each AI service)
HF_API_URL_CONTENT_MODERATION=https://phantomfury-kaleidoscope-content-moderation.hf.space/classify
HF_API_URL_IMAGE_TAGGER=https://phantomfury-kaleidoscope-image-tagger.hf.space/tag
HF_API_URL_SCENE_RECOGNITION=https://phantomfury-kaleidoscope-scene-recognition.hf.space/recognize
HF_API_URL_IMAGE_CAPTIONING=https://phantomfury-kaleidoscope-image-captioning.hf.space/caption
HF_API_URL_FACE_RECOGNITION=https://phantomfury-kaleidoscope-face-recognition.hf.space/detect

# Scene Recognition Configuration (optional)
SCENE_LABELS=beach,mountains,urban,office,restaurant,forest,desert,lake,park,indoor,outdoor,rural,coastal,mountainous,tropical,arctic

# Database Configuration (for ES Sync service)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=kaleidoscope
DB_USER=kaleidoscope_user
DB_PASSWORD=your-database-password-here
```

### Generate Strong Passwords

```bash
# Generate Redis password
openssl rand -base64 32

# Generate Elasticsearch password
openssl rand -base64 32

# Generate Database password
openssl rand -base64 32
```

---

## 🚀 Production Deployment (DigitalOcean)

### Step 1: Create .env File on Server

```bash
# SSH into your DigitalOcean droplet
ssh root@your-droplet-ip

# Navigate to project directory
cd ~/Kaleidoscope/kaleidoscope-ai

# Create .env file
nano .env
```

Paste your environment variables:

```bash
DOCKER_USERNAME=your-dockerhub-username
REDIS_PASSWORD=your-generated-redis-password
ELASTICSEARCH_PASSWORD=your-generated-elasticsearch-password
HF_API_TOKEN=your-huggingface-token
```

Save and exit (Ctrl+X, Y, Enter)

### Step 2: Pull Latest Changes

```bash
cd ~/Kaleidoscope
git pull origin main
cd kaleidoscope-ai
```

### Step 3: Rebuild and Restart Containers

```bash
# Stop existing containers
docker-compose -f docker-compose.prod.yml down

# Pull latest images (if using pre-built images)
docker-compose -f docker-compose.prod.yml pull

# Rebuild and start with new security settings
docker-compose -f docker-compose.prod.yml up -d

# Verify containers are running
docker-compose -f docker-compose.prod.yml ps

# Check logs for any errors
docker-compose -f docker-compose.prod.yml logs --tail=50
```

### Step 4: Verify Security

```bash
# Test Redis connection (should require password)
docker exec -it redis redis-cli -a $REDIS_PASSWORD ping
# Should return: PONG

# Test Elasticsearch connection (should require password)
curl -u elastic:$ELASTICSEARCH_PASSWORD http://localhost:9200/_cluster/health
# Should return cluster health JSON

# Verify Redis port is NOT publicly accessible
# From your local machine, try:
# redis-cli -h your-droplet-ip -p 6379 ping
# Should fail or timeout (good!)
```

---

## 🔧 Development Setup

For local development, the `docker-compose.yml` file uses default passwords that can be overridden:

```bash
# Create .env file with your passwords
cp .env.example .env
nano .env

# Start services
docker-compose up -d
```

**Note**: Development setup still exposes ports for local testing, but uses passwords for security.

---

## 🛡️ Additional Security Recommendations

### 1. Firewall Configuration

On your DigitalOcean droplet, configure UFW firewall:

```bash
# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS (if you have a web server)
ufw allow 80/tcp
ufw allow 443/tcp

# Deny all other incoming connections
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
ufw enable
ufw status
```

### 2. Redis Access (If External Access Needed)

If you need external Redis access (not recommended), use SSH tunnel:

```bash
# From your local machine
ssh -L 6379:localhost:6379 root@your-droplet-ip

# Then connect locally
redis-cli -a your-redis-password
```

### 3. Elasticsearch Access (If External Access Needed)

If you need external Elasticsearch access, use reverse proxy with authentication:

```nginx
# Nginx configuration example
location /elasticsearch/ {
    proxy_pass http://localhost:9200/;
    proxy_set_header Authorization "Basic base64(elastic:password)";
}
```

### 4. Regular Security Updates

```bash
# Update Docker images regularly
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Update system packages
apt update && apt upgrade -y
```

---

## 📝 Backend Integration Notes

### Redis Connection String

Backend should use the following Redis connection string:

```java
// Redis connection with password
String redisUrl = "redis://:" + redisPassword + "@redis-host:6379";
```

### Elasticsearch Connection

Backend should use the following Elasticsearch connection:

```java
// Elasticsearch connection with authentication
String esUrl = "http://elastic:" + elasticsearchPassword + "@elasticsearch-host:9200";
```

---

## ⚠️ Important Notes

1. **Never commit `.env` file to git** - It's already in `.gitignore`
2. **Use strong passwords** - Generate with `openssl rand -base64 32`
3. **Rotate passwords regularly** - Update passwords every 90 days
4. **Monitor access logs** - Check Docker logs regularly for unauthorized access attempts
5. **Backup credentials** - Store passwords securely (password manager, encrypted vault)

---

## 🐛 Troubleshooting

### Redis Connection Errors

```bash
# Check if Redis is running
docker-compose -f docker-compose.prod.yml ps redis

# Check Redis logs
docker-compose -f docker-compose.prod.yml logs redis

# Test Redis connection
docker exec -it redis redis-cli -a $REDIS_PASSWORD ping
```

### Elasticsearch Connection Errors

```bash
# Check if Elasticsearch is running
docker-compose -f docker-compose.prod.yml ps elasticsearch

# Check Elasticsearch logs
docker-compose -f docker-compose.prod.yml logs elasticsearch

# Test Elasticsearch connection
curl -u elastic:$ELASTICSEARCH_PASSWORD http://localhost:9200/_cluster/health
```

### Service Connection Issues

If services can't connect to Redis/Elasticsearch:

1. Verify `.env` file has correct passwords
2. Check that services are on the same Docker network
3. Verify environment variables are loaded: `docker-compose -f docker-compose.prod.yml config`

---

**Questions or Issues?**  
Check logs: `docker-compose -f docker-compose.prod.yml logs [service-name]`
