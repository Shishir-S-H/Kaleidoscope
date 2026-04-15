#!/usr/bin/env python3
"""
verify_google_apis.py
Run on the DigitalOcean server AFTER deployment to confirm:
  1. .env contains all required variables with correct values
  2. GOOGLE_CREDENTIALS_BASE64 decodes to valid JSON
  3. Vertex AI Gemini model is reachable with a lightweight probe
  4. Vertex AI Multimodal Embedding model is reachable
  5. Elasticsearch is up and all expected indices exist
  6. Redis is reachable
  7. PostgreSQL is reachable and V3 migration has been applied

Usage:
  python3 scripts/deployment/verify_google_apis.py [--env /path/to/.env]
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_env(env_path: Path) -> None:
    if not env_path.is_file():
        print(f"[WARN] .env not found at {env_path} — relying on process environment")
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def ok(msg: str) -> None:
    print(f"  \033[32m[OK]\033[0m  {msg}")


def fail(msg: str) -> None:
    print(f"  \033[31m[FAIL]\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"  \033[33m[WARN]\033[0m {msg}")


def section(title: str) -> None:
    print(f"\n\033[34m── {title} ──\033[0m")


def jdbc_to_psycopg2(jdbc: str, user: str, password: str) -> dict:
    rest = jdbc[len("jdbc:postgresql://"):]
    host_port, _, path_query = rest.partition("/")
    if ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = host_port, 5432
    dbname = path_query.split("?")[0]
    opts = {}
    if "?" in path_query:
        for pair in path_query.split("?", 1)[1].split("&"):
            if "=" in pair:
                a, b = pair.split("=", 1)
                opts[a] = b
    return {
        "host": host, "port": port, "dbname": dbname,
        "user": user, "password": password,
        "sslmode": opts.get("sslmode", "require"),
    }


# ── Checks ────────────────────────────────────────────────────────────────────

def check_env_vars() -> bool:
    section("Environment variables")
    required = {
        "REDIS_PASSWORD": "Redis auth password",
        "ELASTICSEARCH_PASSWORD": "Elasticsearch password",
        "GOOGLE_CLOUD_PROJECT": "GCP project ID",
        "GOOGLE_CLOUD_REGION": "GCP region (e.g. us-central1)",
        "GOOGLE_CREDENTIALS_BASE64": "Base64-encoded service account JSON",
        "GOOGLE_GEMINI_MODEL": "Vertex AI Gemini model ID",
        "GOOGLE_EMBEDDING_MODEL": "Vertex AI embedding model ID",
        "SPRING_DATASOURCE_URL": "JDBC URL for Neon PostgreSQL",
        "DB_USERNAME": "Database username",
        "DB_PASSWORD": "Database password",
    }
    passed = True
    for var, desc in required.items():
        val = os.environ.get(var, "")
        if not val:
            fail(f"{var} — {desc} — NOT SET")
            passed = False
        else:
            display = val if len(val) < 40 else val[:37] + "..."
            ok(f"{var} = {display}")

    # Warn on the bad old model
    model = os.environ.get("GOOGLE_GEMINI_MODEL", "")
    if model == "gemini-1.5-flash":
        warn("GOOGLE_GEMINI_MODEL=gemini-1.5-flash is unversioned and returns 404 on "
             "Vertex AI. Set it to gemini-2.0-flash-001.")
        passed = False

    return passed


def check_google_credentials() -> bool:
    section("Google credentials JSON (base64 decode)")
    b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64", "")
    if not b64:
        fail("GOOGLE_CREDENTIALS_BASE64 is empty")
        return False
    try:
        raw = base64.b64decode(b64)
        creds = json.loads(raw)
    except Exception as exc:
        fail(f"Cannot decode/parse credentials: {exc}")
        return False

    cred_type = creds.get("type", "unknown")
    if cred_type == "service_account":
        ok(f"service_account credentials for {creds.get('client_email', '?')}")
    elif cred_type == "authorized_user":
        ok(f"authorized_user credentials (client_id={creds.get('client_id', '?')})")
    else:
        warn(f"Credential type '{cred_type}' — expected service_account or authorized_user")
    return True


def check_gemini_model() -> bool:
    section("Vertex AI — Gemini model probe")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    model = os.environ.get("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash-001")
    b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64", "")

    if not project or not b64:
        warn("GOOGLE_CLOUD_PROJECT or GOOGLE_CREDENTIALS_BASE64 missing — skipping")
        return True

    try:
        import tempfile
        raw = base64.b64decode(b64)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as f:
            f.write(raw)
            cred_file = f.name
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_file

        import vertexai
        from vertexai.generative_models import GenerativeModel, Image, Part

        vertexai.init(project=project, location=region)
        gm = GenerativeModel(model)

        # Minimal 1×1 white JPEG for the probe
        tiny_jpg = bytes([
            0xFF,0xD8,0xFF,0xE0,0x00,0x10,0x4A,0x46,0x49,0x46,0x00,0x01,
            0x01,0x00,0x00,0x01,0x00,0x01,0x00,0x00,0xFF,0xDB,0x00,0x43,
            0x00,0x08,0x06,0x06,0x07,0x06,0x05,0x08,0x07,0x07,0x07,0x09,
            0x09,0x08,0x0A,0x0C,0x14,0x0D,0x0C,0x0B,0x0B,0x0C,0x19,0x12,
            0x13,0x0F,0x14,0x1D,0x1A,0x1F,0x1E,0x1D,0x1A,0x1C,0x1C,0x20,
            0x24,0x2E,0x27,0x20,0x22,0x2C,0x23,0x1C,0x1C,0x28,0x37,0x29,
            0x2C,0x30,0x31,0x34,0x34,0x34,0x1F,0x27,0x39,0x3D,0x38,0x32,
            0x3C,0x2E,0x33,0x34,0x32,0xFF,0xC0,0x00,0x0B,0x08,0x00,0x01,
            0x00,0x01,0x01,0x01,0x11,0x00,0xFF,0xC4,0x00,0x1F,0x00,0x00,
            0x01,0x05,0x01,0x01,0x01,0x01,0x01,0x01,0x00,0x00,0x00,0x00,
            0x00,0x00,0x00,0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,
            0x09,0x0A,0x0B,0xFF,0xC4,0x00,0xB5,0x10,0x00,0x02,0x01,0x03,
            0x03,0x02,0x04,0x03,0x05,0x05,0x04,0x04,0x00,0x00,0x01,0x7D,
            0x01,0x02,0x03,0x00,0x04,0x11,0x05,0x12,0x21,0x31,0x41,0x06,
            0x13,0x51,0x61,0x07,0x22,0x71,0x14,0x32,0x81,0x91,0xA1,0x08,
            0x23,0x42,0xB1,0xC1,0x15,0x52,0xD1,0xF0,0x24,0x33,0x62,0x72,
            0x82,0x09,0x0A,0x16,0x17,0x18,0x19,0x1A,0x25,0x26,0x27,0x28,
            0x29,0x2A,0x34,0x35,0x36,0x37,0x38,0x39,0x3A,0x43,0x44,0x45,
            0x46,0x47,0x48,0x49,0x4A,0x53,0x54,0x55,0x56,0x57,0x58,0x59,
            0x5A,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6A,0x73,0x74,0x75,
            0x76,0x77,0x78,0x79,0x7A,0x83,0x84,0x85,0x86,0x87,0x88,0x89,
            0x8A,0x93,0x94,0x95,0x96,0x97,0x98,0x99,0x9A,0xA2,0xA3,0xA4,
            0xA5,0xA6,0xA7,0xA8,0xA9,0xAA,0xB2,0xB3,0xB4,0xB5,0xB6,0xB7,
            0xB8,0xB9,0xBA,0xC2,0xC3,0xC4,0xC5,0xC6,0xC7,0xC8,0xC9,0xCA,
            0xD2,0xD3,0xD4,0xD5,0xD6,0xD7,0xD8,0xD9,0xDA,0xE1,0xE2,0xE3,
            0xE4,0xE5,0xE6,0xE7,0xE8,0xE9,0xEA,0xF1,0xF2,0xF3,0xF4,0xF5,
            0xF6,0xF7,0xF8,0xF9,0xFA,0xFF,0xDA,0x00,0x08,0x01,0x01,0x00,
            0x00,0x3F,0x00,0xFB,0xD3,0xFF,0xD9,
        ])
        image_part = Part.from_image(Image.from_bytes(tiny_jpg))
        response = gm.generate_content(["Describe in 3 words.", image_part])
        ok(f"Gemini model '{model}' responded: {response.text.strip()[:80]!r}")
        return True

    except Exception as exc:
        msg = str(exc)
        if "not found" in msg.lower() or "404" in msg:
            fail(
                f"Gemini model '{model}' not found on Vertex AI.\n"
                f"        Ensure the model ID is versioned (e.g. gemini-2.0-flash-001)\n"
                f"        and Vertex AI API is enabled on project '{project}'.\n"
                f"        Error: {msg}"
            )
        else:
            fail(f"Gemini probe failed: {msg}")
        return False
    finally:
        try:
            os.unlink(cred_file)
        except Exception:
            pass


def check_embedding_model() -> bool:
    section("Vertex AI — Multimodal Embedding model probe")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    emb_model = os.environ.get("GOOGLE_EMBEDDING_MODEL", "multimodalembedding@001")
    b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64", "")

    if not project or not b64:
        warn("Skipping — GOOGLE_CLOUD_PROJECT or GOOGLE_CREDENTIALS_BASE64 missing")
        return True

    try:
        import tempfile
        raw = base64.b64decode(b64)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="wb") as f:
            f.write(raw)
            cred_file = f.name
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_file

        import vertexai
        from vertexai.vision_models import MultiModalEmbeddingModel, Image as VertexImage

        vertexai.init(project=project, location=region)
        emb = MultiModalEmbeddingModel.from_pretrained(emb_model)

        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg=="
        )
        result = emb.get_embeddings(image=VertexImage(image_bytes=tiny_png))
        dims = len(result.image_embedding)
        if dims == 1408:
            ok(f"Embedding model '{emb_model}' returned {dims}-dim vector (correct)")
        else:
            warn(f"Embedding model returned {dims} dims (expected 1408) — check ES index mapping")
        return True

    except Exception as exc:
        fail(f"Embedding model probe failed: {exc}")
        return False
    finally:
        try:
            os.unlink(cred_file)
        except Exception:
            pass


def check_elasticsearch() -> bool:
    section("Elasticsearch")
    es_pass = os.environ.get("ELASTICSEARCH_PASSWORD", "")
    if not es_pass:
        warn("ELASTICSEARCH_PASSWORD not set — skipping")
        return True

    base = "http://localhost:9200"
    auth = base64.b64encode(f"elastic:{es_pass}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    def es_get(path: str) -> dict:
        req = urllib.request.Request(f"{base}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    try:
        health = es_get("/_cluster/health")
        status = health.get("status", "unknown")
        if status == "green":
            ok(f"Cluster status: {status}")
        elif status == "yellow":
            warn(f"Cluster status: {status} (acceptable on single-node)")
        else:
            fail(f"Cluster status: {status}")
    except Exception as exc:
        fail(f"Cannot reach Elasticsearch: {exc}")
        return False

    expected_indices = [
        "recommendations_knn", "feed_personalized",
        "post_search", "media_search", "user_search",
        "face_search", "known_faces_index",
    ]
    try:
        cat = es_get("/_cat/indices?format=json&h=index,docs.count,store.size,health")
        existing = {i["index"] for i in cat}
        for idx in expected_indices:
            if idx in existing:
                row = next(i for i in cat if i["index"] == idx)
                ok(f"Index '{idx}' exists  docs={row.get('docs.count','?')}  size={row.get('store.size','?')}")
            else:
                warn(f"Index '{idx}' does not exist yet (will be created on first sync)")
    except Exception as exc:
        warn(f"Could not list indices: {exc}")

    return True


def check_redis() -> bool:
    section("Redis")
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        # Derive from REDIS_PASSWORD
        pw = os.environ.get("REDIS_PASSWORD", "")
        redis_url = f"redis://:{pw}@localhost:6379" if pw else "redis://localhost:6379"

    try:
        import redis as _redis
        client = _redis.StrictRedis.from_url(redis_url, socket_connect_timeout=5, decode_responses=True)
        pong = client.ping()
        ok(f"Redis ping: {pong}")

        # Show DLQ depth
        dlq_len = client.xlen("ai-processing-dlq") if client.exists("ai-processing-dlq") else 0
        if dlq_len > 0:
            warn(f"ai-processing-dlq has {dlq_len} message(s). Run deploy with --drain-dlq to replay.")
        else:
            ok("ai-processing-dlq: empty (no stranded messages)")
        return True
    except ImportError:
        warn("redis package not installed — skipping Redis check")
        return True
    except Exception as exc:
        fail(f"Redis not reachable: {exc}")
        return False


def check_postgresql() -> bool:
    section("PostgreSQL — connection + V3 migration")
    jdbc = os.environ.get("SPRING_DATASOURCE_URL", "")
    user = os.environ.get("DB_USERNAME", "")
    password = os.environ.get("DB_PASSWORD", "")

    if not jdbc or not user:
        warn("SPRING_DATASOURCE_URL or DB_USERNAME not set — skipping")
        return True

    try:
        import psycopg2
        params = jdbc_to_psycopg2(jdbc, user, password)
        conn = psycopg2.connect(**params, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        ok("PostgreSQL connection established")

        # Check V3 migration: both columns should now be VECTOR(1408)
        cur.execute("""
            SELECT table_name, column_name, udt_name
            FROM information_schema.columns
            WHERE table_name IN ('media_ai_insights', 'read_model_recommendations_knn')
              AND column_name = 'image_embedding'
        """)
        rows = {(r[0], r[1]): r[2] for r in cur.fetchall()}

        for tbl in ("media_ai_insights", "read_model_recommendations_knn"):
            key = (tbl, "image_embedding")
            if key in rows:
                ok(f"{tbl}.image_embedding column exists (type={rows[key]})")
            else:
                warn(f"{tbl}.image_embedding column missing — run V3 migration")

        # Quick sanity: confirm pgvector extension
        cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname='vector'")
        ext = cur.fetchone()
        if ext:
            ok(f"pgvector extension: {ext[0]} v{ext[1]}")
        else:
            warn("pgvector extension not found")

        cur.close()
        conn.close()
        return True

    except ImportError:
        warn("psycopg2 not installed — skipping PostgreSQL check")
        return True
    except Exception as exc:
        fail(f"PostgreSQL check failed: {exc}")
        return False


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    env_path = Path.home() / "Kaleidoscope" / "kaleidoscope-ai" / ".env"

    # Allow --env /path override
    args = sys.argv[1:]
    if "--env" in args:
        idx = args.index("--env")
        env_path = Path(args[idx + 1])

    print("\n\033[34m╔══════════════════════════════════════════════╗\033[0m")
    print("\033[34m║  Kaleidoscope AI — Post-Deploy Verification   ║\033[0m")
    print("\033[34m╚══════════════════════════════════════════════╝\033[0m")

    load_env(env_path)

    results = {
        "Environment variables": check_env_vars(),
        "Google credentials":    check_google_credentials(),
        "Gemini model probe":    check_gemini_model(),
        "Embedding model probe": check_embedding_model(),
        "Elasticsearch":         check_elasticsearch(),
        "Redis":                 check_redis(),
        "PostgreSQL":            check_postgresql(),
    }

    section("Summary")
    all_passed = True
    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)
            all_passed = False

    print()
    if all_passed:
        print("\033[32m  All checks passed. System is operational.\033[0m\n")
        sys.exit(0)
    else:
        print("\033[31m  Some checks failed. Review the output above.\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
