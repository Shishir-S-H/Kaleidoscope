# 🔗 Backend Integration Documentation

**Complete guide for integrating Kaleidoscope AI services with your Spring Boot backend**

---

## 📚 Documentation Guide

### 🎯 Which Document Should I Read?

| Document                                                                           | Purpose                        | When to Use                                           |
| ---------------------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------- |
| **[BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md)**                                   | High-level integration guide   | **Start here** - Overview and integration points     |
| **[BACKEND_INTEGRATION_COMPLETE_GUIDE.md](BACKEND_INTEGRATION_COMPLETE_GUIDE.md)** | Complete integration reference | Detailed guide with SQL and code examples            |
| **[BACKEND_TEAM_REQUIREMENTS.md](BACKEND_TEAM_REQUIREMENTS.md)**                   | Requirements specification     | Reference for exact requirements                      |
| **[MESSAGE_FORMATS.md](MESSAGE_FORMATS.md)**                                       | Message format specs           | Reference for Redis Stream messages                   |
| **[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)**                                       | Database schema                | Reference for PostgreSQL tables                       |
| **[READ_MODELS.md](READ_MODELS.md)**                                               | Read model tables              | Reference for read model design                       |
| **[POST_AGGREGATION_EXPLAINED.md](POST_AGGREGATION_EXPLAINED.md)**                 | Post aggregation logic         | Understanding post aggregation                        |
| **[CODE_EXAMPLES.md](CODE_EXAMPLES.md)**                                           | Code examples                  | Copy-paste code snippets                              |

---

## 🚀 Quick Start

1. **Read**: [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md) - High-level overview
2. **Follow**: [BACKEND_INTEGRATION_COMPLETE_GUIDE.md](BACKEND_INTEGRATION_COMPLETE_GUIDE.md) - Step-by-step implementation
3. **Reference**: Other documents as needed during implementation

---

## 📋 Integration Checklist

- [ ] Read complete integration guide
- [ ] Review message formats
- [ ] Create 7 PostgreSQL read model tables
- [ ] Implement Redis Stream publishers
- [ ] Implement Redis Stream consumers
- [ ] Test message flow
- [ ] Verify Elasticsearch sync

---

## 🔗 Related Documentation

- **Deployment**: [../deployment/BACKEND_DEPLOYMENT_GUIDE.md](../deployment/BACKEND_DEPLOYMENT_GUIDE.md)
- **Environment Variables**: [../deployment/BACKEND_ENV_VARIABLES.md](../deployment/BACKEND_ENV_VARIABLES.md)
