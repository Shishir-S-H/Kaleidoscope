# 🚀 Quick Start - Kaleidoscope AI

**Welcome!** This is your quick entry point to the Kaleidoscope AI system.

---

## ⚡ 5-Minute Quick Test

### 1. Start the System

```bash
# Navigate to project
cd kaleidoscope-ai

# Start all services
docker compose up -d

# Wait 30 seconds for services to initialize
sleep 30
```

### 2. Verify Search

```bash
# Check Elasticsearch is running
curl http://localhost:9200

# Test search functionality
curl "http://localhost:9200/media_search/_search?q=beach"
```

---

## 📚 Documentation

### Essential Reading

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Detailed getting started guide
- **[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)** - System architecture
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues

### For Backend Integration

- **[../backend-integration/BACKEND_INTEGRATION.md](../backend-integration/BACKEND_INTEGRATION.md)** - Complete integration guide
- **[../api/API.md](../api/API.md)** - Message formats and APIs

### For Deployment

- **[../deployment/DEPLOYMENT.md](../deployment/DEPLOYMENT.md)** - Deployment guide
- **[../configuration/CONFIGURATION.md](../configuration/CONFIGURATION.md)** - Configuration reference

### Complete Documentation

See **[../README.md](../README.md)** for the complete documentation index.

---

## 🎯 What This System Does

**Kaleidoscope AI** is an event-driven microservices platform that:

1. **Processes Images**: 5 AI services analyze images for content, objects, scenes, faces, and safety
2. **Aggregates Insights**: Combines insights from multiple images in a post
3. **Enables Search**: Provides powerful text and vector search across 7 specialized indices
4. **Supports Recognition**: Face detection and user tagging capabilities

**Current Status**: 70% complete, production-ready core system

---

## 🔧 System Requirements

- **Docker Desktop** (running)
- **Python 3.8+** (for test scripts)
- **Internet connection** (for HuggingFace API)
- **4GB RAM** (minimum)
- **2GB disk space** (minimum)

---

## 🚨 Troubleshooting

### Services Won't Start?

1. Ensure Docker is running
2. Check ports 6379 and 9200 are available
3. Check disk space and memory

### Need Help?

1. Read the documentation in `docs/`
2. Check **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**
3. Review service logs for specific errors

---

## 📊 Quick Status Check

```bash
# Check all services
docker compose ps

# Check Redis
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Check Elasticsearch
curl http://localhost:9200/_cat/indices?v

```

---

**🎉 Ready to dive deeper? Check out the documentation in `docs/`!**

**Next Steps**:

1. ✅ Start the system above
2. 📖 Read [GETTING_STARTED.md](GETTING_STARTED.md)
3. 🏗️ Review [../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)
4. 🔗 Share [../backend-integration/BACKEND_INTEGRATION.md](../backend-integration/BACKEND_INTEGRATION.md) with your backend team
