# Deployment Documentation

**Complete deployment documentation for Kaleidoscope AI**

---

## 📚 Documentation Index

### Core Guides

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - General deployment guide (development and production)
- **[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)** - Complete production deployment guide ⭐

### Detailed Guides

- **[DIGITALOCEAN_DEPLOYMENT_GUIDE.md](DIGITALOCEAN_DEPLOYMENT_GUIDE.md)** - DigitalOcean-specific deployment
- **[BACKEND_DEPLOYMENT_GUIDE.md](BACKEND_DEPLOYMENT_GUIDE.md)** - Backend deployment details
- **[BACKEND_ENV_VARIABLES.md](BACKEND_ENV_VARIABLES.md)** - Backend environment variables

---

## 🚀 Quick Start

### Development

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps
```

### Production

```bash
# Initial setup
./scripts/deployment/setup-production.sh

# Regular deployment
./scripts/deployment/deploy-production.sh
```

**For complete production setup, see [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)**

---

## 📋 Production Server Details

- **Server**: `165.232.179.167`
- **Domain**: `project-kaleidoscope.tech`
- **Directory**: `~/Kaleidoscope/kaleidoscope-ai`
- **Services**: 11 containers (Redis, Elasticsearch, Backend, 7 AI Services, Nginx, Certbot)

---

## 🔧 Deployment Scripts

**Location**: `scripts/deployment/`

- `backup-production-configs.sh` - Backup production configuration
- `deploy-production.sh` - Deploy latest images to production
- `setup-production.sh` - Initial setup or restore from backup
- `deploy.sh` - Simple deployment script (run on server)
- `deploy_digitalocean.sh` - DigitalOcean initial setup script
- `start-backend.sh` - Start backend service only

**See [scripts/deployment/README.md](../../scripts/deployment/README.md)** for detailed script documentation.

---

## 📖 Documentation by Use Case

### For First-Time Production Setup

1. Read **[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)** - Complete guide
2. Follow **[DIGITALOCEAN_DEPLOYMENT_GUIDE.md](DIGITALOCEAN_DEPLOYMENT_GUIDE.md)** if using DigitalOcean

### For Regular Deployments

1. Use **[DEPLOYMENT.md](DEPLOYMENT.md)** - Quick reference
2. Run `./scripts/deployment/deploy-production.sh`

### For Backend Team

1. Read **[BACKEND_DEPLOYMENT_GUIDE.md](BACKEND_DEPLOYMENT_GUIDE.md)**
2. Review **[BACKEND_ENV_VARIABLES.md](BACKEND_ENV_VARIABLES.md)**

---

## 🔗 Related Documentation

- **[../configuration/CONFIGURATION.md](../configuration/CONFIGURATION.md)** - Configuration guide
- **[../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)** - Troubleshooting
- **[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)** - System architecture

---

**Last Updated**: January 2025
