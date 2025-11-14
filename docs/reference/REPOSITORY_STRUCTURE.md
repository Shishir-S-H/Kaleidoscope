# Repository Structure

**Last Updated**: January 2025

---

## Directory Structure

```
kaleidoscope-ai/
├── 📁 docs/                          # All documentation
│   ├── README.md                     # Documentation index
│   │
│   ├── 📁 guides/                    # User guides
│   │   ├── START_HERE.md            # Quick start (5-minute)
│   │   ├── GETTING_STARTED.md       # Detailed getting started
│   │   └── TROUBLESHOOTING.md       # Troubleshooting
│   │
│   ├── 📁 architecture/              # Architecture documentation
│   │   └── ARCHITECTURE.md          # System architecture
│   │
│   ├── 📁 backend-integration/       # Backend integration
│   │   ├── README.md                # Integration guide index
│   │   ├── BACKEND_INTEGRATION.md   # Integration guide
│   │   ├── BACKEND_INTEGRATION_COMPLETE_GUIDE.md
│   │   ├── DATABASE_SCHEMA.md
│   │   ├── READ_MODELS.md
│   │   ├── MESSAGE_FORMATS.md
│   │   ├── CODE_EXAMPLES.md
│   │   └── ...
│   │
│   ├── 📁 api/                       # API documentation
│   │   ├── README.md
│   │   ├── API.md                   # API reference
│   │   └── Kaleidoscope_AI_API_Tests.postman_collection.json
│   │
│   ├── 📁 deployment/               # Deployment guides
│   │   ├── README.md
│   │   ├── DEPLOYMENT.md            # Deployment guide
│   │   ├── BACKEND_DEPLOYMENT_GUIDE.md
│   │   ├── DIGITALOCEAN_DEPLOYMENT_GUIDE.md
│   │   └── ...
│   │
│   ├── 📁 configuration/            # Configuration
│   │   ├── README.md
│   │   ├── CONFIGURATION.md         # Configuration guide
│   │   ├── ENV_FILE_EXAMPLE.md
│   │   └── SECURITY_SETUP.md
│   │
│   ├── 📁 elasticsearch/            # Elasticsearch
│   │   ├── README.md
│   │   ├── ELASTICSEARCH.md         # Elasticsearch guide
│   │   └── ELASTICSEARCH_COMPLETE_SUMMARY.md
│   │
│   ├── 📁 reference/                # Reference materials
│   │   ├── README.md
│   │   ├── CONTRIBUTING.md          # Contribution guidelines
│   │   └── REPOSITORY_STRUCTURE.md  # Repository structure (this file)
│   │
│   └── 📁 ...                       # Other documentation folders
│
├── 📁 services/                     # AI microservices (7 services)
│   ├── content_moderation/
│   ├── image_tagger/
│   ├── scene_recognition/
│   ├── image_captioning/
│   ├── face_recognition/
│   ├── post_aggregator/
│   └── es_sync/
│
├── 📁 shared/                       # Shared utilities
│   ├── redis_streams/               # Redis Streams utilities
│   ├── schemas/                    # Message schemas
│   ├── utils/                      # Common utilities
│   ├── db/                         # Database models
│   └── env_templates/              # Environment templates
│
├── 📁 scripts/                      # Utility scripts
│   ├── deployment/                 # Deployment scripts
│   ├── monitoring/                 # Monitoring and health check scripts
│   └── setup/                      # Setup and configuration scripts
│
├── 📁 es_mappings/                  # Elasticsearch index mappings
│   ├── media_search.json
│   ├── post_search.json
│   ├── user_search.json
│   ├── face_search.json
│   ├── recommendations_knn.json
│   ├── feed_personalized.json
│   └── known_faces_index.json
│
├── 📁 migrations/                   # Database migrations
│   └── V1__create_ai_tables.sql
│
├── 📄 README.md                    # Main project documentation
├── 📄 docker-compose.yml           # Development compose
├── 📄 docker-compose.prod.yml     # Production compose
├── 📄 requirements.txt             # Python dependencies
└── 📄 LICENSE                      # MIT License
```

---

## Documentation Structure

### Core Documentation (docs/)

**Essential Reading**:

- `GETTING_STARTED.md` - Quick start guide
- `ARCHITECTURE.md` - System architecture
- `BACKEND_INTEGRATION.md` - Backend integration
- `DEPLOYMENT.md` - Deployment guide
- `TROUBLESHOOTING.md` - Troubleshooting

**Reference**:

- `API.md` - API reference
- `CONFIGURATION.md` - Configuration guide
- `ELASTICSEARCH.md` - Elasticsearch guide
- `CONTRIBUTING.md` - Contribution guidelines

### Detailed Documentation (docs/subdirectories/)

**backend-integration/**: Detailed backend integration docs with SQL and code examples  
**deployment/**: Detailed deployment guides  
**elasticsearch/**: Elasticsearch detailed documentation

---

## Key Files

### Root Level

- `README.md` - Main project documentation
- `docker-compose.yml` - Development Docker Compose
- `docker-compose.prod.yml` - Production Docker Compose

### Documentation

- `docs/README.md` - Documentation index
- `docs/guides/START_HERE.md` - Quick start guide
- `docs/guides/GETTING_STARTED.md` - Getting started guide
- `docs/architecture/ARCHITECTURE.md` - Architecture overview
- `docs/backend-integration/BACKEND_INTEGRATION.md` - Integration guide
- `docs/reference/REPOSITORY_STRUCTURE.md` - Repository structure (this file)

---

## Navigation

1. **New to the project?** → Start with `docs/guides/START_HERE.md`
2. **Need architecture details?** → See `docs/architecture/ARCHITECTURE.md`
3. **Backend integration?** → See `docs/backend-integration/BACKEND_INTEGRATION.md`
4. **Deployment help?** → See `docs/deployment/DEPLOYMENT.md`
5. **Looking for something?** → Check `docs/README.md`

---

**Repository is organized and ready for development!** 🚀
