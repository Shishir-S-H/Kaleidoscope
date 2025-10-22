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
```

### 2. Run Automated Tests

```bash
# Run complete test suite
python tests/test_end_to_end.py
```

**Expected**: All tests should pass ✅

### 3. Verify Search

```bash
# Check Elasticsearch is running
curl http://localhost:9200

# Test search functionality
curl "http://localhost:9200/media_search/_search?q=beach"
```

---

## 📚 Need More Details?

### For Complete Understanding

👉 **Read**: [`docs/END_TO_END_PROJECT_DOCUMENTATION.md`](docs/END_TO_END_PROJECT_DOCUMENTATION.md)

- Complete system architecture
- All components explained
- Data flow diagrams
- Technology decisions

### For Testing & Debugging

👉 **Follow**: [`docs/MANUAL_TESTING_GUIDE.md`](docs/MANUAL_TESTING_GUIDE.md)

- Step-by-step testing procedures
- Troubleshooting guide
- Performance testing
- Debugging tips

### For Backend Integration

👉 **START HERE**: [`docs/BACKEND_INTEGRATION_COMPLETE_GUIDE.md`](docs/BACKEND_INTEGRATION_COMPLETE_GUIDE.md)

- Complete integration guide with code examples
- SQL scripts and JPA entities
- Step-by-step implementation plan
- All message formats and APIs

### For Quick Reference

👉 **Check**: [`README.md`](README.md)

- Project overview
- Architecture summary
- Common commands
- Performance benchmarks

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

### Tests Fail?

1. Check all services are running: `docker compose ps`
2. Check service logs: `docker compose logs [service_name]`
3. Follow troubleshooting in `MANUAL_TESTING_GUIDE.md`

### Services Won't Start?

1. Ensure Docker is running
2. Check ports 6379 and 9200 are available
3. Check disk space and memory

### Need Help?

1. Read the comprehensive documentation
2. Check the troubleshooting sections
3. Review service logs for specific errors

---

## 📊 Quick Status Check

```bash
# Check all services
docker compose ps

# Check Redis
docker exec -it kaleidoscope-ai-redis-1 redis-cli ping

# Check Elasticsearch
curl http://localhost:9200/_cat/indices?v

# Run tests
python tests/test_end_to_end.py
```

---

**🎉 Ready to dive deeper? Check out the main documentation!**

**Next Steps**:

1. ✅ Run the quick test above
2. 📖 Read `docs/END_TO_END_PROJECT_DOCUMENTATION.md`
3. 🧪 Follow `docs/MANUAL_TESTING_GUIDE.md`
4. 🔗 Share `docs/BACKEND_INTEGRATION_COMPLETE_GUIDE.md` with your backend team
