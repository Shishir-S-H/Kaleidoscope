# Deployment Scripts

This directory contains scripts for managing the production deployment of Kaleidoscope AI services.

## Scripts Overview

### 1. `backup-production-configs.sh`

Backs up all production configuration files from the server.

**Usage:**

```bash
./backup-production-configs.sh
```

**What it backs up:**

- `.env` file (environment variables)
- `nginx/nginx.conf` (Nginx configuration)
- Certbot SSL certificates (from Docker volumes or `/etc/letsencrypt`)
- `docker-compose.prod.yml` (if exists)
- File listing for reference

**Output:** Creates a timestamped backup in `../../production-configs/{timestamp}/`

---

### 2. `deploy-production.sh`

Pulls latest Docker images and restarts services on production.

**Usage:**

```bash
./deploy-production.sh
```

**What it does:**

1. Pulls latest backend image from `ajayprabhu2004/kaleidoscope:backend-latest`
2. Pulls latest AI service images from `shishir01/kaleidoscope-{service}:latest`
3. Stops existing services gracefully
4. Starts services with new images
5. Performs health checks
6. Displays service status

**Prerequisites:**

- `docker-compose.prod.yml` must exist on server
- `.env` file must be configured on server
- SSH access to `root@project-kaleidoscope.tech`

---

### 3. `setup-production.sh`

Sets up a fresh production environment or restores from a backup.

**Usage:**

**Restore from backup:**

```bash
./setup-production.sh {timestamp}
```

Example:

```bash
./setup-production.sh 20250115_143022
```

**Fresh setup:**

```bash
./setup-production.sh
```

**What it does:**

1. Creates remote directory structure
2. Copies configuration files (from backup or local)
3. Pulls latest Docker images
4. Starts all services
5. Verifies service status

**Prerequisites:**

- For restore: Backup must exist in `../../production-configs/{timestamp}/`
- For fresh setup: `docker-compose.prod.yml` must exist locally

---

## Workflow

### Initial Setup

1. **Backup existing configs** (if any):

   ```bash
   ./backup-production-configs.sh
   ```

2. **Set up production environment**:
   ```bash
   ./setup-production.sh
   ```
   Or restore from backup:
   ```bash
   ./setup-production.sh {timestamp}
   ```

### Regular Deployment

1. **Backup current configs** (safety first):

   ```bash
   ./backup-production-configs.sh
   ```

2. **Deploy latest changes**:
   ```bash
   ./deploy-production.sh
   ```

### After Code Changes

1. **Push code to repository** - CI/CD will build and push images to Docker Hub
2. **Wait for CI/CD to complete** - Check GitHub Actions
3. **Deploy to production**:
   ```bash
   ./deploy-production.sh
   ```

---

## Configuration

All scripts use these default values (can be modified in scripts):

- **SSH Host**: `root@project-kaleidoscope.tech`
- **Remote Directory**: `~/kaleidoscope`
- **Backend Registry**: `ajayprabhu2004`
- **AI Services Registry**: `shishir01`

---

## Troubleshooting

### SSH Connection Issues

If SSH key authentication fails:

- Ensure SSH key is added to `~/.ssh/authorized_keys` on server
- Or use password authentication (you'll be prompted)

### Docker Images Not Found

If image pull fails:

- Verify images exist on Docker Hub
- Check CI/CD workflow completed successfully
- Verify Docker Hub credentials in GitHub secrets

### Services Won't Start

1. Check logs:

   ```bash
   ssh root@project-kaleidoscope.tech 'cd ~/kaleidoscope && docker-compose -f docker-compose.prod.yml logs'
   ```

2. Verify `.env` file exists and is correct
3. Check disk space: `df -h`
4. Check Docker: `docker ps -a`

### Health Checks Fail

- Services may need more time to start (especially Elasticsearch)
- Check individual service logs
- Verify environment variables are correct

---

## Security Notes

- All scripts connect to production server - use with caution
- `.env` files contain sensitive credentials - never commit them
- Backup directory contains sensitive data - keep secure
- Use SSH keys for authentication when possible

---

## Server Requirements

- Docker and Docker Compose installed
- SSH access configured
- Sufficient disk space for images
- Network access to Docker Hub

---

## Related Files

- `../../docker-compose.prod.yml` - Unified production compose file
- `../../production-configs/` - Backup storage directory
- `../../.github/workflows/build-and-push.yml` - CI/CD workflow
