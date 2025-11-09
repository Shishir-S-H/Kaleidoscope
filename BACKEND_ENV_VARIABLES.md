# 📝 Backend Environment Variables for DigitalOcean

**Add these variables to your `.env` file in `~/Kaleidoscope/` directory**

---

## 🔧 Required Variables to Add

Add these to your existing `.env` file:

```bash
# ============================================
# Docker Compose Specific Variables
# ============================================
DOCKER_REGISTRY=ajayprabhu2004
APP_VERSION=latest
APP_CONTAINER_NAME=kaleidoscope-backend
APP_PORT=8080

# ============================================
# Spring Boot Application Configuration
# ============================================
APP_NAME=kaleidoscope-backend
APP_BASE_URL=http://165.232.179.167:8080
CONTEXT_PATH=/kaleidoscope
SPRING_PROFILES_ACTIVE=production

# ============================================
# PostgreSQL (Neon DB) - External Database
# ============================================
SPRING_DATASOURCE_URL=jdbc:postgresql://ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
DB_USERNAME=neondb_owner
DB_PASSWORD=npg_4mNWuybHc6sD

# ============================================
# Redis & Elasticsearch (for Docker containers)
# ============================================
# These are already set, but ensure they match:
REDIS_PASSWORD=kaleidoscope1-reddis
ELASTICSEARCH_PASSWORD=kaleidoscope1-elastic

# Note: Redis and Elasticsearch connection URLs are set in docker-compose.prod.yml
# to use internal Docker network names (redis, elasticsearch)

# ============================================
# Cloud Services
# ============================================
# Cloudinary
CLOUDINARY_CLOUD_NAME=dkadqnp9j
CLOUDINARY_API_KEY=811954137842469
CLOUDINARY_API_SECRET=Y1DhNdzKoTKbGO4IUIydZ4SQ-Hs

# JWT Secret
JWT_SECRET=fImhIPUqlt1lIahJa0C21NVAbUU/wBQgdcA8+1zXjJw=

# Mail (Gmail)
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=ajax81968@gmail.com
MAIL_PASSWORD=lujv lthr cfuu aibi

# ============================================
# Other Settings
# ============================================
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://165.232.179.167:8080
MAX_FILE_SIZE=10MB
MAX_REQUEST_SIZE=10MB
FILE_SIZE_THRESHOLD=2KB
```

---

## 📋 Complete .env File Structure

Your complete `.env` file should have:

1. **AI Services Variables** (already in your file):
   - `HF_API_TOKEN`
   - `HF_API_URL_*`
   - `REDIS_PASSWORD`
   - `ELASTICSEARCH_PASSWORD`
   - `DOCKER_USERNAME`
   - `SCENE_LABELS`

2. **Backend Variables** (add these):
   - Docker registry config
   - Spring Boot config
   - PostgreSQL (Neon DB) connection
   - Cloudinary config
   - JWT secret
   - Mail config
   - Other settings

---

## ⚠️ Important Notes

1. **PostgreSQL**: Using external Neon DB (not a Docker container)
2. **Redis/Elasticsearch**: Using internal Docker network names (`redis`, `elasticsearch`)
3. **APP_BASE_URL**: Update to your server IP: `http://165.232.179.167:8080`
4. **ALLOWED_ORIGINS**: Add your production frontend URL if needed

---

## 🚀 After Adding Variables

1. Restart the backend service:
   ```bash
   cd ~/Kaleidoscope/kaleidoscope-ai
   docker-compose -f docker-compose.prod.yml restart app
   ```

2. Check logs:
   ```bash
   docker-compose -f docker-compose.prod.yml logs app --tail=50
   ```

3. Test health endpoint:
   ```bash
   curl http://localhost:8080/kaleidoscope/actuator/health
   ```

---

**Last Updated**: 2025-01-15

