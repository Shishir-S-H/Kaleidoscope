"""Full pipeline check for post_id=17 (Test-10). Run inside es_sync container."""
import psycopg2, os, redis, json
from elasticsearch import Elasticsearch

DB_HOST = 'ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech'
DB_NAME = 'neondb'
DB_USER = 'neondb_owner'
DB_PASS = os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD')
REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
ES_URL = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
POST_ID = 17

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS, sslmode='require')
cur = conn.cursor()

# ─── media_ai_insights ───────────────────────────────────────────────────────
print("=== [DB] media_ai_insights ===")
cur.execute("""
    SELECT media_id, status, is_safe, caption,
           array_length(tags, 1) as tag_count,
           array_length(scenes, 1) as scene_count,
           vector_dims(image_embedding) as embed_dim,
           services_completed, tags, scenes
    FROM media_ai_insights WHERE media_id=17
""")
for r in cur.fetchall():
    print(f"  media_id={r[0]}  status={r[1]}  is_safe={r[2]}")
    print(f"  caption   = {r[3][:100] if r[3] else 'N/A'}")
    print(f"  tags      = {r[8]}")
    print(f"  scenes    = {r[9]}")
    print(f"  embed_dim = {r[6]}  tag_count={r[4]}  scene_count={r[5]}")
    print(f"  services_completed = {r[7]}")

# ─── media_detected_faces ────────────────────────────────────────────────────
print()
print("=== [DB] media_detected_faces ===")
cur.execute("""
    SELECT mdf.id, mdf.media_id, mdf.confidence_score,
           mdf.identified_user_id, vector_dims(mdf.embedding) as embed_dim,
           mdf.bbox, mdf.status
    FROM media_detected_faces mdf
    JOIN post_media pm ON pm.media_id = mdf.media_id
    WHERE pm.post_id = %s
    ORDER BY mdf.id
""", (POST_ID,))
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  id={r[0]}  media_id={r[1]}  status={r[6]}")
        print(f"    confidence_score={r[2]:.4f}  identified_user={r[3]}  embed_dim={r[4]}")
        print(f"    bbox={r[5]}")
else:
    print("  (no rows yet)")

# ─── read_model_face_search ──────────────────────────────────────────────────
print()
print("=== [DB] read_model_face_search ===")
cur.execute("SELECT id, face_id, media_id, post_id, identified_username FROM read_model_face_search WHERE post_id=%s ORDER BY id", (POST_ID,))
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  id={r[0]}  face_id={r[1]}  media_id={r[2]}  post_id={r[3]}  identified_username={r[4]}")
else:
    print("  (no rows yet)")

# ─── read_model_media_search ─────────────────────────────────────────────────
print()
print("=== [DB] read_model_media_search ===")
cur.execute("SELECT media_id, ai_caption FROM read_model_media_search WHERE media_id=17")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  media_id={r[0]}  ai_caption={r[1][:100] if r[1] else 'N/A'}")
else:
    print("  (no rows yet)")

# ─── read_model_recommendations_knn ─────────────────────────────────────────
print()
print("=== [DB] read_model_recommendations_knn ===")
cur.execute("SELECT media_id FROM read_model_recommendations_knn WHERE media_id=17")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  media_id={r[0]}  (embedding stored as vector)")
else:
    print("  (no rows yet)")

# ─── read_model_feed_personalized ───────────────────────────────────────────
print()
print("=== [DB] read_model_feed_personalized ===")
cur.execute("SELECT media_id, caption FROM read_model_feed_personalized WHERE media_id=17")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  media_id={r[0]}  caption={r[1][:100] if r[1] else 'N/A'}")
else:
    print("  (no rows yet)")

# ─── read_model_post_search ──────────────────────────────────────────────────
print()
print("=== [DB] read_model_post_search ===")
cur.execute("SELECT post_id, title FROM read_model_post_search WHERE post_id=%s", (POST_ID,))
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  post_id={r[0]}  title={r[1]}")
else:
    print("  (no rows yet)")

conn.close()

# ─── Redis PEL check ────────────────────────────────────────────────────────
print()
print("=== [Redis] face-detection-results PEL ===")
r = redis.from_url(REDIS_URL, decode_responses=True)
try:
    pending = r.xpending_range('face-detection-results', 'backend-group', '-', '+', 10)
    if pending:
        for p in pending:
            print(f"  STUCK: msg_id={p['message_id']} consumer={p['consumer']} deliveries={p['times_delivered']}")
    else:
        print("  (clean - no stuck messages)")
except Exception as e:
    print(f"  error: {e}")

# ─── Elasticsearch indexes ───────────────────────────────────────────────────
print()
print("=== [ES] Elasticsearch Indexes ===")
es = Elasticsearch(ES_URL)

indexes = {
    'media_search': {'term': {'mediaId': 17}},
    'post_search':  {'term': {'postId': POST_ID}},
    'recommendations_knn': {'term': {'mediaId': 17}},
    'feed_personalized': {'term': {'mediaId': 17}},
    'face_search': {'term': {'postId': POST_ID}},
}

for idx, query in indexes.items():
    try:
        res = es.search(index=idx, body={'query': query, 'size': 10})
        hits = res['hits']['hits']
        print(f"\n  [{idx}] {len(hits)} doc(s) found")
        for h in hits:
            s = h['_source']
            if idx == 'face_search':
                emb = s.get('faceEmbedding') or []
                print(f"    _id={h['_id']}  faceId={s.get('faceId')}  mediaId={s.get('mediaId')}  postId={s.get('postId')}")
                print(f"    identifiedUsername={s.get('identifiedUsername')}  embedding_dims={len(emb) if isinstance(emb, list) else 'N/A'}")
            elif idx == 'media_search':
                print(f"    _id={h['_id']}  mediaId={s.get('mediaId')}")
                print(f"    caption={str(s.get('caption',''))[:80]}")
                print(f"    tags={s.get('tags')}  scenes={s.get('scenes')}")
            elif idx == 'post_search':
                print(f"    _id={h['_id']}  postId={s.get('postId')}  title={s.get('title')}")
                print(f"    tags={s.get('tags')}  scenes={s.get('scenes')}")
            else:
                print(f"    _id={h['_id']}  mediaId={s.get('mediaId') or s.get('id')}")
    except Exception as e:
        print(f"\n  [{idx}] ERROR: {e}")
