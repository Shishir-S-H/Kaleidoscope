# kaleidoscope-ai

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

**Event-driven Python AI microservices for the Kaleidoscope platform.**

Processes images through six concurrent AI workers (content moderation, tagging, scene recognition, captioning, face recognition, face matching), aggregates multi-image insights, and syncs enriched data into Elasticsearch — all via Redis Streams.

> **Edition:** Phase C (April 2026) — all Python/Java schema contracts verified and deployed.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [documentation/system_architecture.md](documentation/system_architecture.md) | Full-stack architecture, service topology, Redis streams, Elasticsearch indices (+ domain ownership), shared library, provider abstraction, security model, five-phase build history |
| [documentation/integration_contracts.md](documentation/integration_contracts.md) | Every Redis stream field contract (Java ↔ Python), REST API surface, Pydantic DTO registry |
| [documentation/developer_setup.md](documentation/developer_setup.md) | Local setup, environment variables, common commands, troubleshooting |
| [documentation/deployment_and_operations.md](documentation/deployment_and_operations.md) | Production deployment (DigitalOcean), Nginx + SSL, backup/restore, CI/CD |
| [documentation/user_journeys.md](documentation/user_journeys.md) | End-to-end sequence diagrams for registration, post creation, and search |
| [documentation/audit_report_and_tech_debt.md](documentation/audit_report_and_tech_debt.md) | Full GAP audit (18 items), Phase C resolutions, remaining tech debt sprint plan |

---

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env — at minimum set REDIS_PASSWORD, ELASTICSEARCH_PASSWORD, HF_API_TOKEN

# 2. Start all services
docker compose up -d

# 3. Verify
docker compose ps
curl http://localhost:9200/_cluster/health
```

For the full setup walkthrough see [documentation/developer_setup.md](documentation/developer_setup.md).

---

## Repository Layout

```
kaleidoscope-ai/
├── documentation/          # Single source of truth — all docs live here
├── services/               # Python microservices (one folder per worker)
│   ├── content_moderation/
│   ├── image_tagger/
│   ├── scene_recognition/
│   ├── image_captioning/
│   ├── face_recognition/
│   ├── face_matcher/
│   ├── profile_enrollment/
│   ├── post_aggregator/
│   ├── es_sync/
│   ├── dlq_processor/
│   └── federated_aggregator/
├── shared/                 # Shared library (redis_streams, schemas, providers, utils)
├── es_mappings/            # Elasticsearch index mapping JSON files (7 indices)
├── migrations/             # PostgreSQL migration scripts
├── scripts/                # Deployment, setup, and monitoring scripts
├── tests/                  # Pytest suite
├── docker-compose.yml      # Development stack
├── docker-compose.prod.yml # Production stack (Nginx + Certbot + pre-built images)
└── .env.example            # Environment variable template
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Message broker | Redis 7 (Alpine) — Redis Streams |
| Search engine | Elasticsearch 8.10.2 |
| AI inference | HuggingFace `InferenceClient` |
| Data validation | Pydantic v2 (strict `BaseModel`) |
| Containerisation | Docker Compose |
| CI/CD | GitHub Actions → Docker Hub |

---

## License

MIT — see [LICENSE](LICENSE).
