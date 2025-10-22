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

### Recommended Configuration:
- **Image:** Ubuntu 22.04 LTS
- **Size:** Basic plan, $12/month (2GB RAM, 1 CPU, 50GB SSD)
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
cd Kaleidoscope/kaleidoscope-ai
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

### Deploy Services:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Step 6: Verify Deployment

### Check Service Status:
```bash
docker-compose -f docker-compose.prod.yml ps
```

### Check Logs:
```bash
docker-compose -f docker-compose.prod.yml logs -f
```

### Test Services:
```bash
# Test Redis
docker exec -it kaleidoscope-ai-redis-1 redis-cli ping

# Test Elasticsearch
curl http://localhost:9200

# Test AI Services
curl http://localhost:8001/health  # Content Moderation
curl http://localhost:8002/health  # Image Tagger
curl http://localhost:8003/health  # Scene Recognition
curl http://localhost:8004/health  # Image Captioning
curl http://localhost:8005/health  # Face Recognition
curl http://localhost:8006/health  # Post Aggregator
curl http://localhost:8007/health  # ES Sync
```

## Step 7: Configure Firewall

### Allow Required Ports:
```bash
ufw allow 22    # SSH
ufw allow 8001  # Content Moderation
ufw allow 8002  # Image Tagger
ufw allow 8003  # Scene Recognition
ufw allow 8004  # Image Captioning
ufw allow 8005  # Face Recognition
ufw allow 8006  # Post Aggregator
ufw allow 8007  # ES Sync
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
docker-compose -f docker-compose.prod.yml logs [service-name]
```

### If out of memory:
- Upgrade to larger droplet
- Or reduce resource limits in docker-compose.prod.yml

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
