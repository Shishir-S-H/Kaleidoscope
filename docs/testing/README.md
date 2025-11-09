# 🧪 Testing Documentation

**Complete testing guide for Kaleidoscope AI services**

---

## 📚 Documentation Files

- **[README_TESTING_AND_DOCS.md](README_TESTING_AND_DOCS.md)** - Testing overview and documentation map
- **[TESTING_DOCUMENTATION_SUMMARY.md](TESTING_DOCUMENTATION_SUMMARY.md)** - Testing documentation summary
- **[TESTING_TOOLS_SUMMARY.md](TESTING_TOOLS_SUMMARY.md)** - Testing tools reference
- **[CURL_COMMANDS_REFERENCE.md](CURL_COMMANDS_REFERENCE.md)** - cURL command reference for testing

---

## 🛠️ Test Scripts

- **[../../scripts/test/comprehensive-test.sh](../../scripts/test/comprehensive-test.sh)** - Comprehensive test suite
- **[../../scripts/test/diagnose-services.sh](../../scripts/test/diagnose-services.sh)** - Service diagnostics

---

## 🚀 Quick Start

```bash
# Run comprehensive test suite
chmod +x ../../scripts/test/*.sh
../../scripts/test/comprehensive-test.sh

# Run service diagnostics
../../scripts/test/diagnose-services.sh
```

---

## 📋 Test Coverage

- ✅ Service health checks
- ✅ Redis Stream message processing
- ✅ Consumer group verification
- ✅ Elasticsearch indexing
- ✅ PostgreSQL read model integration
- ✅ Retry logic and DLQ
- ✅ Metrics and health checks
