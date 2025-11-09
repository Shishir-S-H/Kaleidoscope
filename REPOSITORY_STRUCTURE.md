# 📁 Kaleidoscope AI - Repository Structure

**Last Updated**: November 9, 2025

---

## 📂 Directory Structure

```
kaleidoscope-ai/
├── 📁 docs/                          # All documentation
│   ├── INDEX.md                      # Documentation index (start here)
│   ├── END_TO_END_PROJECT_DOCUMENTATION.md  # Complete system docs
│   ├── PROJECT_STRUCTURE.md          # Project structure details
│   │
│   ├── 📁 architecture/              # Architecture documentation
│   │   └── README.md                  # Architecture guide
│   │
│   ├── 📁 backend-integration/       # Backend integration guides
│   │   ├── README.md                 # Start here: Integration guide
│   │   ├── BACKEND_INTEGRATION_COMPLETE_GUIDE.md
│   │   ├── BACKEND_TEAM_REQUIREMENTS.md
│   │   ├── MESSAGE_FORMATS.md
│   │   ├── POST_AGGREGATION_EXPLAINED.md
│   │   ├── READ_MODELS.md
│   │   ├── DATABASE_SCHEMA.md
│   │   ├── CODE_EXAMPLES.md
│   │   ├── INTEGRATION_WALKTHROUGH.md
│   │   └── INTEGRATION_SUMMARY.md
│   │
│   ├── 📁 deployment/                # Deployment guides
│   │   ├── README.md                 # Start here: Deployment guide
│   │   ├── BACKEND_DEPLOYMENT_GUIDE.md
│   │   ├── DIGITALOCEAN_DEPLOYMENT_GUIDE.md
│   │   ├── BACKEND_INTEGRATION_GUIDE.md
│   │   └── BACKEND_ENV_VARIABLES.md
│   │
│   ├── 📁 testing/                    # Testing documentation
│   │   ├── README.md                 # Start here: Testing guide
│   │   ├── README_TESTING_AND_DOCS.md
│   │   ├── TESTING_DOCUMENTATION_SUMMARY.md
│   │   ├── TESTING_TOOLS_SUMMARY.md
│   │   └── CURL_COMMANDS_REFERENCE.md
│   │
│   ├── 📁 elasticsearch/              # Elasticsearch docs
│   │   ├── README.md                 # Elasticsearch guide
│   │   └── ELASTICSEARCH_COMPLETE_SUMMARY.md
│   │
│   ├── 📁 implementation/             # Implementation details
│   │   ├── README.md                 # Implementation guide
│   │   └── CORRELATION_ID_IMPLEMENTATION.md
│   │
│   ├── 📁 configuration/              # Configuration guides
│   │   ├── README.md                 # Configuration guide
│   │   ├── ENV_FILE_EXAMPLE.md
│   │   └── SECURITY_SETUP.md
│   │
│   ├── 📁 stakeholders/               # Stakeholder documentation
│   │   ├── README.md                 # Stakeholder guide
│   │   └── PROJECT_OVERVIEW_FOR_STAKEHOLDERS.md
│   │
│   ├── 📁 api/                        # API resources
│   │   ├── README.md                 # API guide
│   │   └── Kaleidoscope_AI_API_Tests.postman_collection.json
│   │
│   ├── CONTRIBUTING.md                # Contribution guidelines
│   └── CLEANUP_SUMMARY.md             # Cleanup history
│
├── 📁 services/                      # AI microservices
│   ├── content_moderation/
│   ├── image_tagger/
│   ├── scene_recognition/
│   ├── image_captioning/
│   ├── face_recognition/
│   ├── post_aggregator/
│   └── es_sync/
│
├── 📁 shared/                        # Shared utilities
│   ├── redis_streams/                 # Redis Streams utilities
│   ├── schemas/                       # Message schemas
│   ├── utils/                         # Common utilities
│   │   ├── logger.py
│   │   ├── retry.py
│   │   ├── metrics.py
│   │   └── health.py
│   ├── db/                            # Database models
│   └── env_templates/                 # Environment templates
│
├── 📁 scripts/                        # Utility scripts
│   ├── 📁 test/                       # Test scripts
│   │   ├── comprehensive-test.sh
│   │   └── diagnose-services.sh
│   ├── 📁 deployment/                 # Deployment scripts
│   │   ├── deploy.sh
│   │   ├── deploy_digitalocean.sh
│   │   └── start-backend.sh
│   ├── monitor_services.sh            # Service monitoring
│   └── setup_es_indices.py            # ES setup script
│
├── 📁 tests/                         # Test suites
│   ├── test_end_to_end.py
│   ├── test_es_sync.py
│   ├── test_post_aggregator.py
│   └── test_redis_streams.py
│
├── 📁 es_mappings/                    # Elasticsearch index mappings
│   ├── media_search.json
│   ├── post_search.json
│   ├── user_search.json
│   ├── face_search.json
│   ├── recommendations_knn.json
│   ├── feed_personalized.json
│   └── known_faces_index.json
│
├── 📁 migrations/                     # Database migrations
│   └── V1__create_ai_tables.sql
│
├── 📄 README.md                       # Main project documentation
├── 📄 START_HERE.md                   # Quick start guide
├── 📄 REPOSITORY_STRUCTURE.md         # This file
├── 📄 docker-compose.yml              # Development compose
├── 📄 docker-compose.prod.yml        # Production compose
├── 📄 requirements.txt                # Python dependencies
└── 📄 LICENSE                         # MIT License
```

---

## 📚 Documentation Organization

### Quick Access

- **Start Here**: [`START_HERE.md`](START_HERE.md)
- **Main README**: [`README.md`](README.md)
- **Documentation Index**: [`docs/INDEX.md`](docs/INDEX.md)

### By Category

#### 🏗️ Architecture & Design

- `docs/END_TO_END_PROJECT_DOCUMENTATION.md` - Complete system documentation
- `docs/PROJECT_STRUCTURE.md` - Project structure details
- `docs/stakeholders/PROJECT_OVERVIEW_FOR_STAKEHOLDERS.md` - High-level overview

#### 🔗 Backend Integration

- `docs/backend-integration/BACKEND_INTEGRATION_COMPLETE_GUIDE.md` - Complete guide
- `docs/backend-integration/BACKEND_TEAM_REQUIREMENTS.md` - Requirements
- `docs/backend-integration/MESSAGE_FORMATS.md` - Message formats
- `docs/backend-integration/DATABASE_SCHEMA.md` - Database schema
- `docs/backend-integration/READ_MODELS.md` - Read models
- `docs/backend-integration/CODE_EXAMPLES.md` - Code examples

#### 🚀 Deployment

- `docs/deployment/BACKEND_DEPLOYMENT_GUIDE.md` - Backend deployment
- `docs/deployment/DIGITALOCEAN_DEPLOYMENT_GUIDE.md` - DigitalOcean setup
- `docs/deployment/BACKEND_INTEGRATION_GUIDE.md` - Integration guide
- `docs/deployment/BACKEND_ENV_VARIABLES.md` - Environment variables

#### 🧪 Testing

- `docs/testing/README_TESTING_AND_DOCS.md` - Testing overview
- `docs/testing/TESTING_DOCUMENTATION_SUMMARY.md` - Testing summary
- `docs/testing/TESTING_TOOLS_SUMMARY.md` - Testing tools
- `docs/testing/CURL_COMMANDS_REFERENCE.md` - cURL reference

#### ⚙️ Configuration

- `docs/configuration/ENV_FILE_EXAMPLE.md` - Environment variables example
- `docs/configuration/SECURITY_SETUP.md` - Security configuration

#### 🔍 Elasticsearch

- `docs/elasticsearch/ELASTICSEARCH_COMPLETE_SUMMARY.md` - ES setup and config

#### 💻 Implementation

- `docs/implementation/CORRELATION_ID_IMPLEMENTATION.md` - Correlation ID

---

## 🗂️ Scripts Organization

### Test Scripts (`scripts/test/`)

- `comprehensive-test.sh` - Comprehensive test suite
- `diagnose-services.sh` - Service diagnostics

### Deployment Scripts (`scripts/deployment/`)

- `deploy.sh` - General deployment script
- `deploy_digitalocean.sh` - DigitalOcean deployment
- `start-backend.sh` - Backend startup script

### Utility Scripts (`scripts/`)

- `monitor_services.sh` - Service monitoring
- `setup_es_indices.py` - Elasticsearch index setup

---

## 📝 Key Files

### Root Level

- `README.md` - Main project documentation
- `START_HERE.md` - Quick start guide
- `REPOSITORY_STRUCTURE.md` - This file
- `docker-compose.yml` - Development Docker Compose
- `docker-compose.prod.yml` - Production Docker Compose
- `requirements.txt` - Python dependencies

### Documentation

- `docs/INDEX.md` - Complete documentation index
- `docs/END_TO_END_PROJECT_DOCUMENTATION.md` - Full system docs

---

## 🎯 Navigation Tips

1. **New to the project?** → Start with [`START_HERE.md`](START_HERE.md)
2. **Need architecture details?** → See [`docs/END_TO_END_PROJECT_DOCUMENTATION.md`](docs/END_TO_END_PROJECT_DOCUMENTATION.md)
3. **Backend integration?** → See [`docs/backend-integration/`](docs/backend-integration/)
4. **Deployment help?** → See [`docs/deployment/`](docs/deployment/)
5. **Testing?** → See [`docs/testing/`](docs/testing/)
6. **Looking for something?** → Check [`docs/INDEX.md`](docs/INDEX.md)

---

**Repository is organized and ready for development!** 🚀
