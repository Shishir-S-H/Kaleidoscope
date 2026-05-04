"""
Migrate face-related pgvector columns from vector(1024) to vector(1408)
to match Vertex AI multimodalembedding@001 (face crops + profile enrollment).

Tables: media_detected_faces.embedding, read_model_face_search.face_embedding,
read_model_known_faces.face_embedding.

Prefer Flyway migration ``migrations/V4__face_embeddings_vector_1408.sql`` for
new environments; this script is a manual fallback / one-off repair.
"""
import os

import psycopg2

DB_HOST = os.getenv("DB_HOST", "ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "neondb")
DB_USER = os.getenv("DB_USERNAME", "neondb_owner")
DB_PASS = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

FACE_TABLES = (
    ("media_detected_faces", "embedding"),
    ("read_model_face_search", "face_embedding"),
    ("read_model_known_faces", "face_embedding"),
)

print("=== Current state ===")
for table, col in FACE_TABLES:
    cur.execute(
        "SELECT column_name, data_type, udt_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table, col),
    )
    rows = cur.fetchall()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table}.{col}: {rows} | rows={count}")

print("\n=== Clearing rows and migrating columns to vector(1408) ===")

for table, col in FACE_TABLES:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    n = cur.fetchone()[0]
    if n > 0:
        print(f"  Deleting {n} row(s) from {table}")
        cur.execute(f"DELETE FROM {table}")

print("  ALTER media_detected_faces.embedding → vector(1408)")
cur.execute(
    "ALTER TABLE media_detected_faces ALTER COLUMN embedding TYPE vector(1408) "
    "USING embedding::text::vector(1408)"
)

print("  ALTER read_model_face_search.face_embedding → vector(1408)")
cur.execute(
    "ALTER TABLE read_model_face_search ALTER COLUMN face_embedding TYPE vector(1408) "
    "USING face_embedding::text::vector(1408)"
)

print("  ALTER read_model_known_faces.face_embedding → vector(1408)")
cur.execute(
    "ALTER TABLE read_model_known_faces ALTER COLUMN face_embedding TYPE vector(1408) "
    "USING face_embedding::text::vector(1408)"
)

print("\n=== Verifying columns ===")
for table, col in FACE_TABLES:
    cur.execute(
        "SELECT column_name, udt_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s AND column_name = %s",
        (table, col),
    )
    rows = cur.fetchall()
    print(f"  {table}.{col}: {rows}")

cur.close()
conn.close()
print("\nDone. Face embedding columns now accept vector(1408).")
