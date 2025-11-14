# DigitalOcean Deployment Guide

## Prerequisites

- ✅ GitHub Student Pack credits claimed
- ✅ DigitalOcean account created
- ✅ Docker images built and pushed to Docker Hub
- ✅ SSH access to your droplet

## Step 1: Claim GitHub Student Pack Credits

1. Visit: https://education.github.com/pack
2. Sign in with your GitHub account
3. Find DigitalOcean and click "Get your pack"
4. Follow instructions to claim $200 credit

## Step 2: Create DigitalOcean Droplet

### Recommended Configuration (tested):

- **Image:** Ubuntu 22.04 LTS
- **Size:** Basic plan, $24/month (4GB RAM, 2 CPU, 80GB SSD)
- **Region:** Choose closest to your users
- **Authentication:** SSH Key (recommended)
- **Hostname:** `kaleidoscope-ai`

### Steps:

1. Go to: https://cloud.digitalocean.com/droplets/new
2. Select Ubuntu 22.04 LTS
3. Choose Basic plan, $12/month option
4. Add SSH Key or use password
5. Set hostname: `kaleidoscope-ai`
6. Click "Create Droplet"

## Step 3: Connect to Your Droplet

### Using SSH:

```bash
ssh root@YOUR_DROPLET_IP
```

### Using Password:

```bash
ssh root@YOUR_DROPLET_IP
# Enter password when prompted
```

## Step 4: Install Required Software

### Update System:

```bash
apt update && apt upgrade -y
```

### Install Docker:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
systemctl start docker
systemctl enable docker
```

### Install Docker Compose:

```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### Install Git:

```bash
apt install git -y
```

## Step 5: Deploy Kaleidoscope AI

### Clone Repository:

```bash
git clone https://github.com/Shishir-S-H/Kaleidoscope.git
cd Kaleidoscope
cd kaleidoscope-ai
```

### Create Environment File:

```bash
cp .env.example .env
nano .env
```

### Edit Environment Variables:

```bash
# HuggingFace API Configuration
HF_API_TOKEN=your_huggingface_token_here

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Elasticsearch Configuration
ES_HOST=http://localhost:9200

# Service Configuration
LOG_LEVEL=INFO
```

### Deploy Services (tested paths):

```bash
# Option A: build and run locally on droplet (recommended)
docker-compose -f docker-compose.yml up -d

# Option B: use prebuilt images (requires pushing to Docker Hub and setting DOCKER_USERNAME)
# docker-compose -f docker-compose.prod.yml up -d
```

## Step 6: Verify Deployment

### Check Service Status:

```bash
docker-compose -f docker-compose.yml ps
```

### Check Logs:

```bash
docker-compose -f docker-compose.yml logs -f
```

### Test Services:

```bash
# Test Redis
docker exec kaleidoscope-redis-1 redis-cli ping

# Test Elasticsearch
curl http://localhost:9200

# Optional health endpoints vary by service; prefer stream tests below
```

### Verify Services

```bash
# Check all services are running
docker compose ps

# Check service logs
docker compose logs [service_name]
```

## Step 7: Configure Firewall

### Allow Required Ports:

```bash
ufw allow 22    # SSH
ufw allow 9200  # Elasticsearch
ufw enable
```

## Step 8: Set Up Monitoring

### Install htop for monitoring:

```bash
apt install htop -y
```

### Monitor Resources:

```bash
htop
```

## Troubleshooting

### If services fail to start:

```bash
docker-compose -f docker-compose.yml logs [service-name]
```

### Elasticsearch OOM (exit code 137):

- Use a 4GB droplet (recommended) or add swap
- Cap heap: `ES_JAVA_OPTS=-Xms1g -Xmx1g` and restart only `elasticsearch`

### Redis Streams consumer group missing (NOGROUP):

```bash
docker exec kaleidoscope-redis-1 redis-cli XGROUP CREATE es-sync-queue es-sync-group $ MKSTREAM
```

### BLOCK $ returns (nil) when testing streams:

- You started blocking after publication. Use `XRANGE`/`XREVRANGE` to read existing entries or start blocking before the trigger.

### Image downloads fail (HTTP 521/403):

- Use reliable URLs (GitHub asset, Wikimedia). Avoid flaky sources during outages.

### If ports are blocked:

```bash
ufw status
ufw allow [port]
```

## Next Steps

1. **Test all services** are running
2. **Configure domain name** (optional)
3. **Set up SSL certificates** (optional)
4. **Configure monitoring** and alerts
5. **Share connection details** with backend team

## Cost Estimation

- **Droplet:** $12/month
- **Total with credits:** Free for ~16 months
- **After credits:** $12/month

## Support

If you encounter issues:

1. Check service logs
2. Verify environment variables
3. Check firewall settings
4. Ensure sufficient resources
