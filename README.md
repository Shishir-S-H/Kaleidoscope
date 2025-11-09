# Kaleidoscope AI - AI-Powered Image Analysis Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.10.2-005571?style=flat&logo=elasticsearch)](https://www.elastic.co/elasticsearch/)
[![Redis](https://img.shields.io/badge/Redis-Streams-DC382D?style=flat&logo=redis)](https://redis.io/)

**Status**: Production-Ready Core  
**Last Updated**: November 9, 2025

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Quick Start](#-quick-start)
- [Architecture](#️-architecture)
- [Features](#-features)
- [Documentation](#-documentation)
- [Testing](#-testing)
- [Current Status](#-current-status)
- [Development](#-development)
- [Contributing](#-contributing)
- [License](#-license)

## 🎯 Project Overview

Kaleidoscope AI is an event-driven microservices platform that provides AI-powered image analysis for internal organizational use. The system processes images through multiple AI services, aggregates insights, and provides powerful search capabilities.

### Key Features

- **5 AI Services**: Content moderation, image tagging, scene recognition, captioning, face recognition
- **Post Aggregation**: Combines insights from multiple images in a post
- **Elasticsearch Search**: 7 specialized indices for different search patterns
- **Redis Streams**: Event-driven architecture with reliable message processing
- **HuggingFace Integration**: All AI models hosted on HuggingFace Inference API

---

## 🚀 Quick Start

### Prerequisites

- Docker Desktop
- Python 3.8+
- Internet connection (for HuggingFace API)

### 1. Start the System

```bash
# Navigate to project
cd kaleidoscope-ai

# Start all services
docker compose up -d

# Verify services are running
docker compose ps
```

### 2. Run Tests

```bash
# Automated smoke test
python tests/test_end_to_end.py

# Operational test scripts (runs on servers)
./scripts/test/comprehensive-test.sh
./scripts/test/diagnose-services.sh
```

### 3. Verify System

```bash
# Check Elasticsearch
curl http://localhost:9200

# Check indices
curl http://localhost:9200/_cat/indices?v

# Test search
curl "http://localhost:9200/media_search/_search?q=beach"
```

---

## 📚 Documentation

### Documentation Index

📚 **[Complete Documentation Index](docs/INDEX.md)** - All documentation organized by category

### Essential Reading

| Document                                                                                 | Purpose                             | When to Use                                 |
| ---------------------------------------------------------------------------------------- | ----------------------------------- | ------------------------------------------- |
| **[docs/END_TO_END_PROJECT_DOCUMENTATION.md](docs/END_TO_END_PROJECT_DOCUMENTATION.md)** | Complete system documentation       | First time, architecture review, onboarding |
| **[docs/deployment/DIGITALOCEAN_DEPLOYMENT_GUIDE.md](docs/deployment/DIGITALOCEAN_DEPLOYMENT_GUIDE.md)** | Deploy to DigitalOcean              | Cloud deployment                            |
| **[docs/deployment/BACKEND_INTEGRATION_GUIDE.md](docs/deployment/BACKEND_INTEGRATION_GUIDE.md)** | Integration with backend            | Backend teams                               |
| **[docs/testing/TESTING_DOCUMENTATION_SUMMARY.md](docs/testing/TESTING_DOCUMENTATION_SUMMARY.md)** | Testing doc map                     | Finding specific information                |
| **[docs/ELASTICSEARCH_COMPLETE_SUMMARY.md](docs/ELASTICSEARCH_COMPLETE_SUMMARY.md)**     | Elasticsearch setup & configuration | ES setup, index management                  |

### Backend Integration

| Document                                                                                     | Purpose                 | Audience     |
| -------------------------------------------------------------------------------------------- | ----------------------- | ------------ |
| **[docs/backend-integration/DATABASE_SCHEMA.md](docs/backend-integration/DATABASE_SCHEMA.md)** | Full database schema    | Backend team |
| **[docs/backend-integration/READ_MODELS.md](docs/backend-integration/READ_MODELS.md)** | Read model tables       | Backend team |
| **[docs/BACKEND_TEAM_REQUIREMENTS.md](docs/BACKEND_TEAM_REQUIREMENTS.md)**                   | Redis integration specs | Backend team |

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND (Spring Boot + PostgreSQL)                │
│  - User Management                                                   │
│  - Post/Media Management                                             │
│  - Core Business Logic                                               │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   │ (1) Publishes image job
                   ↓
        ┌──────────────────────┐
        │ post-image-processing│ (Redis Stream)
        └──────────┬───────────┘
                   │
                   │ (2) AI workers consume
                   ↓
    ┌──────────────┴──────────────┐
    ↓              ↓               ↓
┌────────┐    ┌────────┐    ┌──────────┐
│Content │    │ Image  │    │  Scene   │
│  Mod   │    │ Tagger │    │  Recog   │
└────┬───┘    └───┬────┘    └────┬─────┘
     │            │              │
     ↓            ↓              ↓
┌────────┐    ┌──────────┐
│ Image  │    │   Face   │
│Caption │    │   Recog  │
└────┬───┘    └────┬─────┘
     │             │
     │             │ (3) Publish results
     ↓             ↓
┌──────────────────────────┐    ┌───────────────────────┐
│ ml-insights-results      │    │face-detection-results │
└──────────┬───────────────┘    └───────┬───────────────┘
           │                             │
           │ (4) Post Aggregator         │ (5) Backend stores
           │     consumes                │     face data
           ↓                             ↓
    ┌──────────────┐              ┌──────────┐
    │     Post     │              │ Backend  │
    │  Aggregator  │              │PostgreSQL│
    └──────┬───────┘              └────┬─────┘
           │                           │
           │ (6) Publish enriched      │
           ↓                           │
    ┌───────────────────┐              │
    │post-insights-     │              │
    │enriched           │              │
    └────────┬──────────┘              │
             │                         │
             │ (7) Backend stores      │
             │     to PostgreSQL       │
             ↓                         │
      ┌─────────────┐                 │
      │  Backend    │◄────────────────┘
      │ PostgreSQL  │
      │ (7 Read     │
      │  Models)    │
      └──────┬──────┘
             │
             │ (8) Publishes sync message
             ↓
      ┌──────────────┐
      │ es-sync-queue│ (Redis Stream)
      └──────┬───────┘
             │
             │ (9) ES Sync consumes
             ↓
      ┌──────────────┐
      │   ES Sync    │
      │   Service    │
      └──────┬───────┘
             │
             │ (10) Indexes documents
             ↓
      ┌──────────────────┐
      │  Elasticsearch   │
      │  (7 Indices)     │
      │                  │
      │  - media_search  │
      │  - post_search   │
      │  - user_search   │
      │  - face_search   │
      │  - recs_knn      │
      │  - feed_perso    │
      │  - known_faces   │
      └──────┬───────────┘
             │
             │ (11) Users search
             ↓
      ┌──────────────┐
      │  Search API  │
      │  (Future)    │
      └──────────────┘
```

### Services

| Service                | Purpose                       | Technology                |
| ---------------------- | ----------------------------- | ------------------------- |
| **Content Moderation** | NSFW detection                | HuggingFace API           |
| **Image Tagger**       | Object/scene tagging          | HuggingFace API           |
| **Scene Recognition**  | Environment detection         | HuggingFace API           |
| **Image Captioning**   | Natural language descriptions | HuggingFace API           |
| **Face Recognition**   | Face detection & embeddings   | HuggingFace API (AdaFace) |
| **Post Aggregator**    | Multi-image insights          | Python + Redis            |
| **ES Sync**            | PostgreSQL → Elasticsearch    | Python + Elasticsearch    |

---

## 🧪 Testing

### Automated Testing

```bash
# Run complete test suite
python tests/test_end_to_end.py
```

Note: See `tests/` for unit/integration tests and `scripts/test/` for operational test scripts.

### Manual Testing

Follow the comprehensive guide in `docs/MANUAL_TESTING_GUIDE.md` for:

- Step-by-step testing procedures
- Debugging instructions
- Performance testing
- Troubleshooting

---

## 📊 Current Status

### ✅ What's Working (70% Complete)

**Infrastructure**:

- Redis Streams message broker
- Elasticsearch search engine (7 indices)
- Docker containerization

**AI Pipeline**:

- All 5 AI services operational
- HuggingFace API integration
- Error handling and retries

**Data Processing**:

- Post aggregation service
- ES Sync service
- Multi-image context preservation

**Search**:

- Text search
- Vector search (KNN)
- Filtered search
- Aggregations

**Testing**:

- Automated test suite
- Manual testing procedures
- Performance benchmarks

### ⏳ What's Pending (30%)

**Backend Integration**:

- 7 read model tables in PostgreSQL
- Redis Stream consumers/publishers
- Sync triggers
- API endpoints

**Production Features**:

- Multi-node Elasticsearch cluster
- Security implementation
- Monitoring and alerting
- CI/CD pipeline

---

## 🔧 Development

### Project Structure

```
kaleidoscope-ai/
├── 📁 services/                    # Core AI microservices (7 services)
│   ├── content_moderation/         # NSFW detection
│   ├── image_tagger/              # Object/scene tagging
│   ├── scene_recognition/         # Environment detection
│   ├── image_captioning/          # Image descriptions
│   ├── face_recognition/          # Face detection
│   ├── post_aggregator/           # Multi-image aggregation
│   └── es_sync/                   # Elasticsearch sync
├── 📁 shared/                     # Shared utilities and libraries
│   ├── redis_streams/             # Redis Streams utilities
│   ├── schemas/                   # Message schemas (Pydantic)
│   ├── utils/                     # Common utilities
│   ├── db/                        # Database models
│   └── env_templates/             # Environment templates
├── 📁 es_mappings/                # Elasticsearch index mappings (7 indices)
├── 📁 tests/                      # Test suites (4 test files)
├── 📁 scripts/                    # Utility scripts
│   ├── test/                      # Test scripts
│   └── setup_es_indices.py       # ES setup script
├── 📁 migrations/                 # Database migrations
└── 📄 docker-compose.yml          # Service orchestration
```

**For detailed structure**: See [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)

### Key Technologies

- **Python 3.10**: All microservices
- **Redis Streams**: Message broker
- **Elasticsearch 8.10.2**: Search engine
- **Docker**: Containerization
- **HuggingFace API**: AI model inference
- **PostgreSQL**: Database (backend integration)

---

## 🚀 Next Steps

### Immediate

1. **Share with Backend Team**:

   - Database schema documentation
   - Redis integration requirements
   - Message format specifications

2. **Complete Backend Integration**:
   - Create 7 read model tables
   - Implement sync triggers
   - Add Redis Stream consumers

### Short Term

1. **Integration Testing**:

   - End-to-end testing
   - Performance optimization
   - Bug fixes

2. **Production Preparation**:
   - Security review
   - Monitoring setup
   - Deployment planning

### Long Term

1. **Advanced Features**:

   - Personalized recommendations
   - Real-time updates
   - Video analysis

2. **Scaling**:
   - Multi-node Elasticsearch
   - Load balancing
   - Auto-scaling

---

## 📞 Support

### Getting Help

1. **Documentation**: Start with `docs/END_TO_END_PROJECT_DOCUMENTATION.md`
2. **Testing**: Follow `docs/MANUAL_TESTING_GUIDE.md`
3. **Debugging**: Check service logs with `docker compose logs [service]`
4. **Integration**: Review backend docs in `docs/` folder

### Common Commands

```bash
# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f [service_name]

# Run tests
python tests/test_end_to_end.py

# Check Elasticsearch
curl http://localhost:9200/_cat/indices?v
```

---

## 📈 Performance

### Benchmarks

| Component        | Metric          | Value   | Status       |
| ---------------- | --------------- | ------- | ------------ |
| AI Processing    | Time per image  | 10-30s  | ✅ Good      |
| Post Aggregation | Processing time | < 100ms | ✅ Excellent |
| ES Sync          | Index time      | < 100ms | ✅ Excellent |
| Search           | Query time      | ~44ms   | ✅ Excellent |
| Redis            | Latency         | < 1ms   | ✅ Excellent |

---

**🎉 Ready to get started? Run `python tests/test_end_to_end.py` to see everything in action!**

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](docs/CONTRIBUTING.md) for details on how to:

- Report bugs
- Suggest new features
- Submit pull requests
- Set up the development environment

### Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/kaleidoscope-ai.git`
3. Create a feature branch: `git checkout -b feature/amazing-feature`
4. Make your changes and test them
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [HuggingFace](https://huggingface.co/) for providing the AI models
- [Elasticsearch](https://www.elastic.co/elasticsearch/) for powerful search capabilities
- [Redis](https://redis.io/) for reliable message streaming
- [Docker](https://www.docker.com/) for containerization
