# 🏗️ Architecture Documentation

**System architecture and design documentation**

---

## 📚 Documentation Files

This directory contains architecture diagrams and detailed design documentation.

---

## 🔗 Related Documentation

- **Complete System Docs**: [../END_TO_END_PROJECT_DOCUMENTATION.md](../END_TO_END_PROJECT_DOCUMENTATION.md)
- **Project Structure**: [../PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md)
- **Stakeholder Overview**: [../stakeholders/PROJECT_OVERVIEW_FOR_STAKEHOLDERS.md](../stakeholders/PROJECT_OVERVIEW_FOR_STAKEHOLDERS.md)

---

## 📊 Architecture Overview

The Kaleidoscope AI system uses an event-driven microservices architecture:

- **5 AI Services**: Content moderation, image tagging, scene recognition, captioning, face recognition
- **Post Aggregator**: Combines insights from multiple images
- **ES Sync Service**: Syncs data from PostgreSQL to Elasticsearch
- **Redis Streams**: Message broker for inter-service communication
- **Elasticsearch**: Search engine with 7 specialized indices

---

## 🔍 Key Components

- Event-driven architecture
- Microservices pattern
- Redis Streams messaging
- Elasticsearch search
- PostgreSQL read models

