# Setup Scripts

**Scripts for initial setup and configuration of Kaleidoscope AI services**

---

## Scripts

### `setup_es_indices.py`

Creates all 7 Elasticsearch indices with proper mappings and settings.

**Usage**:
```bash
python scripts/setup/setup_es_indices.py
```

**What it does**:
- Creates 7 Elasticsearch indices:
  - `media_search`
  - `post_search`
  - `user_search`
  - `face_search`
  - `recommendations_knn`
  - `feed_personalized`
  - `known_faces_index`
- Applies mappings from `es_mappings/` directory
- Configures index settings

**Environment Variables**:
- `ES_HOST` - Elasticsearch host (default: `http://localhost:9200`)
- `ELASTICSEARCH_PASSWORD` - Elasticsearch password (if security enabled)

---

## Related Documentation

- **Elasticsearch Setup**: [../../docs/ELASTICSEARCH.md](../../docs/ELASTICSEARCH.md)
- **Configuration**: [../../docs/CONFIGURATION.md](../../docs/CONFIGURATION.md)

