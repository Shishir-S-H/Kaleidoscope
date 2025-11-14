# Troubleshooting Guide

**Common issues and solutions for Kaleidoscope AI**

---

## Quick Diagnostics

### Check Service Status

```bash
# Check all services
docker compose ps

# Check specific service
docker compose ps [service_name]

# Check service logs
docker compose logs -f [service_name]
```

### Check Infrastructure

```bash
# Redis
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Elasticsearch
curl http://localhost:9200

# Check indices
curl http://localhost:9200/_cat/indices?v
```

---

## Common Issues

### Services Won't Start

**Symptoms**: Services fail to start or exit immediately

**Solutions**:

1. **Check Docker is running**:

   ```bash
   docker ps
   ```

2. **Check ports are available**:

   ```bash
   # Check port 6379 (Redis)
   lsof -i :6379

   # Check port 9200 (Elasticsearch)
   lsof -i :9200
   ```

3. **Check disk space**:

   ```bash
   df -h
   ```

4. **Check memory**:

   ```bash
   free -h
   ```

5. **Check logs for specific errors**:
   ```bash
   docker compose logs [service_name]
   ```

---

### Redis Connection Errors

**Symptoms**: Services can't connect to Redis

**Solutions**:

1. **Check Redis is running**:

   ```bash
   docker compose ps redis
   ```

2. **Check Redis password**:

   ```bash
   # Verify password in .env file
   cat .env | grep REDIS_PASSWORD

   # Test connection
   docker exec redis redis-cli -a ${REDIS_PASSWORD} ping
   ```

3. **Check Redis logs**:

   ```bash
   docker compose logs redis
   ```

4. **Restart Redis**:
   ```bash
   docker compose restart redis
   ```

---

### Elasticsearch Connection Errors

**Symptoms**: ES Sync can't connect to Elasticsearch

**Solutions**:

1. **Check Elasticsearch is running**:

   ```bash
   docker compose ps elasticsearch
   ```

2. **Check Elasticsearch password**:

   ```bash
   # Verify password in .env file
   cat .env | grep ELASTICSEARCH_PASSWORD

   # Test connection
   curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200
   ```

3. **Check Elasticsearch logs**:

   ```bash
   docker compose logs elasticsearch
   ```

4. **Check Elasticsearch health**:

   ```bash
   curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health
   ```

5. **Restart Elasticsearch**:
   ```bash
   docker compose restart elasticsearch
   ```

---

### AI Services Not Processing Images

**Symptoms**: Images published but no results in streams

**Solutions**:

1. **Check consumer groups exist**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-image-processing
   ```

2. **Create consumer groups if missing**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing content-moderation-group 0 MKSTREAM
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-tagger-group 0 MKSTREAM
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing scene-recognition-group 0 MKSTREAM
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing image-captioning-group 0 MKSTREAM
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE post-image-processing face-recognition-group 0 MKSTREAM
   ```

3. **Check HuggingFace API configuration**:

   ```bash
   # Check environment variables
   docker compose exec content_moderation env | grep HF_API
   ```

4. **Check service logs for errors**:

   ```bash
   docker compose logs content_moderation | grep ERROR
   docker compose logs image_tagger | grep ERROR
   ```

5. **Restart AI services**:
   ```bash
   docker compose restart content_moderation image_tagger scene_recognition image_captioning face_recognition
   ```

---

### Post Aggregator Not Working

**Symptoms**: ML insights exist but no enriched results

**Solutions**:

1. **Check aggregator consumer group**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS ml-insights-results
   ```

2. **Create consumer group if missing**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE ml-insights-results post-aggregator-group 0 MKSTREAM
   ```

3. **Check aggregator logs**:

   ```bash
   docker compose logs post_aggregator | tail -50
   ```

4. **Check trigger stream**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN post-aggregation-trigger
   ```

5. **Restart post aggregator**:
   ```bash
   docker compose restart post_aggregator
   ```

---

### ES Sync Not Working

**Symptoms**: Data in PostgreSQL but not in Elasticsearch

**Solutions**:

1. **Check ES Sync consumer group**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS es-sync-queue
   ```

2. **Create consumer group if missing**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XGROUP CREATE es-sync-queue es-sync-group 0 MKSTREAM
   ```

3. **Check PostgreSQL connection**:

   ```bash
   # Check environment variables
   docker compose exec es_sync env | grep DB_
   ```

4. **Check ES Sync logs**:

   ```bash
   docker compose logs es_sync | tail -50
   ```

5. **Check Elasticsearch connection**:

   ```bash
   docker compose exec es_sync curl -u elastic:${ELASTICSEARCH_PASSWORD} http://elasticsearch:9200
   ```

6. **Restart ES Sync**:
   ```bash
   docker compose restart es_sync
   ```

---

### Messages in Dead Letter Queue

**Symptoms**: Messages accumulating in `ai-processing-dlq`

**Solutions**:

1. **Check DLQ messages**:

   ```bash
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN ai-processing-dlq
   docker exec redis redis-cli -a ${REDIS_PASSWORD} XREVRANGE ai-processing-dlq + - COUNT 5
   ```

2. **Identify failure reason**:

   - Check error messages in DLQ
   - Review service logs for that time period
   - Check HuggingFace API status

3. **Common causes**:

   - HuggingFace API timeout
   - Invalid image URL
   - Network connectivity issues
   - Image download failures

4. **Reprocess messages**:
   - Extract original message from DLQ
   - Republish to original stream
   - Monitor for success

---

### Slow Processing

**Symptoms**: Images taking too long to process

**Solutions**:

1. **Check HuggingFace API status**:

   - Visit HuggingFace status page
   - Check API rate limits
   - Verify API token is valid

2. **Check network connectivity**:

   ```bash
   # Test image download
   docker exec content_moderation curl -I https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png
   ```

3. **Check resource usage**:

   ```bash
   docker stats
   ```

4. **Check service logs for timeouts**:

   ```bash
   docker compose logs content_moderation | grep timeout
   ```

5. **Expected performance**:
   - AI processing: 10-30s per image (normal)
   - Post aggregation: < 100ms
   - ES Sync: < 100ms

---

### Elasticsearch Index Not Found

**Symptoms**: ES Sync errors about missing indices

**Solutions**:

1. **Check indices exist**:

   ```bash
   curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cat/indices?v
   ```

2. **Create missing indices**:

   ```bash
   python scripts/setup/setup_es_indices.py
   ```

3. **Check index mappings**:
   ```bash
   curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/media_search/_mapping
   ```

---

### PostgreSQL Connection Errors (ES Sync)

**Symptoms**: ES Sync can't connect to PostgreSQL

**Solutions**:

1. **Check environment variables**:

   ```bash
   docker compose exec es_sync env | grep -E "DB_|SPRING_DATASOURCE"
   ```

2. **Verify PostgreSQL is accessible**:

   ```bash
   # From ES Sync container
   docker compose exec es_sync python -c "
   import psycopg2
   conn = psycopg2.connect(
       host='${DB_HOST}',
       port=${DB_PORT},
       database='${DB_NAME}',
       user='${DB_USER}',
       password='${DB_PASSWORD}'
   )
   print('Connected successfully')
   conn.close()
   "
   ```

3. **Check PostgreSQL connection string format**:

   - If using `SPRING_DATASOURCE_URL`, ensure format: `jdbc:postgresql://host:port/database`
   - If using individual variables, ensure all are set

4. **Check PostgreSQL logs** (if accessible)

---

## Diagnostic Commands

### Service Health Check

```bash
# Check service status
docker compose ps

# Check service logs
docker compose logs [service_name]
```

### Check All Streams

```bash
# List all streams
docker exec redis redis-cli -a ${REDIS_PASSWORD} KEYS "*"

# Check stream lengths
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN post-image-processing
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN ml-insights-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN face-detection-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN post-insights-enriched
docker exec redis redis-cli -a ${REDIS_PASSWORD} XLEN es-sync-queue
```

### Check Consumer Groups

```bash
# List all consumer groups
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS post-image-processing
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS ml-insights-results
docker exec redis redis-cli -a ${REDIS_PASSWORD} XINFO GROUPS es-sync-queue
```

### Check Pending Messages

```bash
# Check pending messages for a consumer group
docker exec redis redis-cli -a ${REDIS_PASSWORD} XPENDING post-image-processing content-moderation-group
```

---

## Getting Help

### Check Documentation

1. **[GETTING_STARTED.md](GETTING_STARTED.md)** - Getting started guide
2. **[../architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)** - System architecture

### Check Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs [service_name]

# Follow logs
docker compose logs -f [service_name]

# Last 100 lines
docker compose logs --tail=100 [service_name]
```

### Run Diagnostics

```bash
# Check all services
docker compose ps

# Check service logs
docker compose logs [service_name]

# Check Redis
docker exec redis redis-cli -a ${REDIS_PASSWORD} ping

# Check Elasticsearch
curl -u elastic:${ELASTICSEARCH_PASSWORD} http://localhost:9200/_cluster/health
```

---

**Still having issues? Check service logs and review the architecture documentation.**
