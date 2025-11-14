# Kaleidoscope AI - AI-Powered Image Analysis Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

**Status**: Production-Ready Core (70% Complete)  
**Last Updated**: January 2025

---

## 🎯 Overview

Kaleidoscope AI is an event-driven microservices platform that provides AI-powered image analysis. The system processes images through multiple AI services, aggregates insights, and provides powerful search capabilities via Elasticsearch.

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

### Start the System

```bash
# Navigate to project
cd kaleidoscope-ai

# Start all services
docker compose up -d

# Verify services are running
docker compose ps
```

### Verify System

```bash
# Check Elasticsearch
curl http://localhost:9200

# Check indices
curl http://localhost:9200/_cat/indices?v
```

---

## 📚 Documentation

### Essential Reading

| Document                                                                                               | Purpose                   | Audience               |
| ------------------------------------------------------------------------------------------------------ | ------------------------- | ---------------------- |
| **[docs/guides/START_HERE.md](docs/guides/START_HERE.md)**                                             | Quick start guide         | New users              |
| **[docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md)**                                   | Getting started guide     | New users              |
| **[docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)**                             | System architecture       | Developers, architects |
| **[docs/backend-integration/BACKEND_INTEGRATION.md](docs/backend-integration/BACKEND_INTEGRATION.md)** | Backend integration guide | Backend team           |
| **[docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md)**                                     | Deployment guide          | DevOps, deployment     |
| **[docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md)**                                   | Troubleshooting           | All users              |

### Complete Documentation Index

See **[docs/README.md](docs/README.md)** for the complete documentation index.

---

## 🏗️ Architecture

### System Overview

```
Backend (Spring Boot)
    │
    │ Publishes image job
    ▼
Redis Stream: post-image-processing
    │
    │ Consumed by 5 AI services
    ▼
┌─────────────┬─────────────┬─────────────┐
│ Content Mod │ Image Tagger│ Scene Recog │
└──────┬──────┴──────┬──────┴──────┬──────┘
       │             │              │
       ▼             ▼              ▼
Redis Stream: ml-insights-results
    │
    │ Consumed by Post Aggregator
    ▼
Redis Stream: post-insights-enriched
    │
    │ Consumed by Backend
    ▼
PostgreSQL Read Models
    │
    │ Triggers ES sync
    ▼
Redis Stream: es-sync-queue
    │
    │ Consumed by ES Sync
    ▼
Elasticsearch (7 Indices)
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
├── services/              # Core AI microservices (7 services)
├── shared/               # Shared utilities and libraries
├── es_mappings/          # Elasticsearch index mappings (7 indices)
├── tests/                # Test suites
├── scripts/              # Utility scripts
│   ├── test/            # Test scripts
│   └── deployment/      # Deployment scripts
├── migrations/          # Database migrations
└── docs/                # Documentation
```

### Key Technologies

- **Python 3.10**: All microservices
- **Redis Streams**: Message broker
- **Elasticsearch 8.10.2**: Search engine
- **Docker**: Containerization
- **HuggingFace API**: AI model inference
- **PostgreSQL**: Database (backend integration)

---

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

## 🤝 Contributing

See **[docs/reference/CONTRIBUTING.md](docs/reference/CONTRIBUTING.md)** for contribution guidelines.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 📞 Support

### Getting Help

1. **Documentation**: Start with [docs/guides/START_HERE.md](docs/guides/START_HERE.md)
2. **Debugging**: Check [docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md)
3. **Integration**: Review [docs/backend-integration/BACKEND_INTEGRATION.md](docs/backend-integration/BACKEND_INTEGRATION.md)

### Common Commands

```bash
# Start services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f [service_name]


# Check Elasticsearch
curl http://localhost:9200/_cat/indices?v
```

---

**🎉 Ready to get started? Check out [docs/guides/START_HERE.md](docs/guides/START_HERE.md) or [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md)!**
