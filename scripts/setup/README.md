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

### `clear_es_data.sh` / `clear_es_data.py`

Removes **all documents** from the 7 Elasticsearch indices. Indices and mappings are left unchanged (only data is cleared). Useful for resetting search state on SSH/production without recreating indices.

**Usage (on SSH server)**:

```bash
# Option 1: Shell script (only needs curl)
export ELASTICSEARCH_PASSWORD='your_elastic_password'
export ES_BASE_URL='http://localhost:9200'   # or http://127.0.0.1:9200
chmod +x scripts/setup/clear_es_data.sh
./scripts/setup/clear_es_data.sh
```

```bash
# Option 2: Python script (requires: pip install elasticsearch)
export ES_HOST="http://elastic:YOUR_PASSWORD@localhost:9200"
python scripts/setup/clear_es_data.py
```

**Environment Variables**:
- `ELASTICSEARCH_PASSWORD` - Required for auth (user: `elastic`)
- `ES_BASE_URL` - For shell script (default: `http://localhost:9200`)
- `ES_HOST` - For Python script; may include user: `http://elastic:PASSWORD@localhost:9200`

**Note**: If Elasticsearch is in Docker and only bound to `127.0.0.1:9200`, run the script on the same host (e.g. after `ssh` into the server).

**On the server (pull then clear in one go)**:

```bash
cd ~/Kaleidoscope/kaleidoscope-ai   # or your repo path
chmod +x scripts/setup/run_clear_es_data_on_server.sh
./scripts/setup/run_clear_es_data_on_server.sh
```

This pulls `origin/main` and runs `clear_es_data.sh`. Ensure `ELASTICSEARCH_PASSWORD` is in `.env` or exported before running.

---

## Related Documentation

- **Elasticsearch Setup**: [../../docs/ELASTICSEARCH.md](../../docs/ELASTICSEARCH.md)
- **Configuration**: [../../docs/CONFIGURATION.md](../../docs/CONFIGURATION.md)

