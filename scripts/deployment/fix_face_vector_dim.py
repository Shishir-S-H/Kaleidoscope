"""
Migrate media_detected_faces and read_model_face_search embedding columns
from vector(1024) to vector(1408) to match Vertex AI multimodalembedding@001 output.
"""
import os, psycopg2

DB_HOST = os.getenv("DB_HOST", "ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "neondb")
DB_USER = os.getenv("DB_USERNAME", "neondb_owner")
DB_PASS = os.getenv("DB_PASSWORD", "")

conn = psycopg2.connect(
    host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
    user=DB_USER, password=DB_PASS, sslmode='require'
)
conn.autocommit = True
cur = conn.cursor()

# Check current dimensions and row counts
print("=== Current state ===")
for table in ('media_detected_faces', 'read_model_face_search'):
    cur.execute(
        "SELECT column_name, data_type, udt_name "
        "FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'embedding'",
        (table,)
    )
    rows = cur.fetchall()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table}: {rows} | rows={count}")

print("\n=== Migrating embedding columns to vector(1408) ===")

# Drop existing rows to avoid dimension mismatch on existing data
cur.execute("SELECT COUNT(*) FROM media_detected_faces")
face_count = cur.fetchone()[0]
if face_count > 0:
    print(f"  Deleting {face_count} existing rows from media_detected_faces (old 1024-dim data)")
    cur.execute("DELETE FROM media_detected_faces")

cur.execute("SELECT COUNT(*) FROM read_model_face_search")
fs_count = cur.fetchone()[0]
if fs_count > 0:
    print(f"  Deleting {fs_count} existing rows from read_model_face_search (old 1024-dim data)")
    cur.execute("DELETE FROM read_model_face_search")

# Alter columns
print("  ALTER TABLE media_detected_faces ALTER COLUMN embedding TYPE vector(1408)")
cur.execute("ALTER TABLE media_detected_faces ALTER COLUMN embedding TYPE vector(1408) USING embedding::text::vector(1408)")

print("  ALTER TABLE read_model_face_search ALTER COLUMN embedding TYPE vector(1408)")
cur.execute("ALTER TABLE read_model_face_search ALTER COLUMN embedding TYPE vector(1408) USING embedding::text::vector(1408)")

# Verify
print("\n=== Verifying new dimensions ===")
for table in ('media_detected_faces', 'read_model_face_search'):
    cur.execute(
        "SELECT column_name, udt_name "
        "FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'embedding'",
        (table,)
    )
    rows = cur.fetchall()
    print(f"  {table}: {rows}")

cur.close()
conn.close()
print("\nDone. Both tables now accept vector(1408) embeddings.")
