# Getting Started with Kaleidoscope AI

**Quick start guide for new users**

---

## Prerequisites

- **Docker Desktop** (running)
- **Python 3.8+** (for test scripts)
- **Internet connection** (for HuggingFace API)
- **4GB RAM** (minimum)
- **2GB disk space** (minimum)

---

## Quick Start (5 Minutes)

### 1. Clone and Navigate

```bash
cd kaleidoscope-ai
```

### 2. Start Services

```bash
# Start all services
docker compose up -d

# Wait 30 seconds for services to initialize
sleep 30

# Verify services are running
docker compose ps
```

### 3. Verify System

```bash
# Check Elasticsearch
curl http://localhost:9200

# Check indices
curl http://localhost:9200/_cat/indices?v
```

---

## What's Running?

After starting, you should have:

- **Redis** (port 6379) - Message broker
- **Elasticsearch** (port 9200) - Search engine
- **5 AI Services** - Content moderation, tagging, scene recognition, captioning, face recognition
- **Post Aggregator** - Multi-image insights
- **ES Sync** - Elasticsearch synchronization

---

## Next Steps

### For Development

1. Read **[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)** to understand the system
2. Check **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** if you encounter issues

### For Backend Integration

1. Read **[../backend-integration/BACKEND_INTEGRATION.md](../backend-integration/BACKEND_INTEGRATION.md)** - Complete integration guide
2. Review **[../api/API.md](../api/API.md)** - Message formats and APIs

### For Deployment

1. Read **[../deployment/DEPLOYMENT.md](../deployment/DEPLOYMENT.md)** - Deployment guide

---

## Common Commands

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f [service_name]

# Check service status
docker compose ps

# Restart a service
docker compose restart [service_name]

```

---

## Troubleshooting

### Services Won't Start?

1. Ensure Docker Desktop is running
2. Check ports 6379 and 9200 are available
3. Check disk space: `df -h`
4. Check memory: `free -h`

### Need More Help?

- Check **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** for common issues
- Review service logs for specific errors
- Check **[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)** for system understanding

---

## System Requirements

### Development

- Docker Desktop
- Python 3.8+
- 4GB RAM minimum
- 2GB disk space

### Production

- Docker and Docker Compose
- 8GB RAM recommended
- 10GB disk space
- Internet connection for HuggingFace API

---

**🎉 You're ready to go! Check out [../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md) to learn more about the system.**
