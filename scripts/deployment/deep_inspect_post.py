"""
Deep inspection of Test-5 (post_id=13) — all tables, correct columns, faces, ES.
Run: docker exec es_sync python3 /tmp/deep_inspect_post.py
"""
import os, psycopg2, json
from elasticsearch import Elasticsearch

POST_ID = 16
TITLE   = "Test-8"

DB = dict(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
conn = psycopg2.connect(**DB)
cur  = conn.cursor()
SEP  = "=" * 70

# ── 1. posts ──────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  POST: {TITLE}  (post_id={POST_ID})")
print(SEP)
cur.execute("SELECT post_id, user_id, title, status, created_at FROM posts WHERE post_id=%s", (POST_ID,))
r = cur.fetchone()
if r:
    print(f"  post_id={r[0]}  user_id={r[1]}  title={r[2]}")
    print(f"  status={r[3]}  created_at={r[4]}")

# ── 2. post_media ─────────────────────────────────────────────────────────
print(f"\n--- post_media ---")
cur.execute("SELECT media_id, media_type, media_url FROM post_media WHERE post_id=%s", (POST_ID,))
for r in cur.fetchall():
    print(f"  media_id={r[0]}  type={r[1]}")
    print(f"  url={r[2]}")

# ── 3. media_ai_insights ──────────────────────────────────────────────────
print(f"\n--- media_ai_insights ---")
cur.execute("""
    SELECT media_id, status, is_safe,
           tags, scenes, caption,
           services_completed,
           vector_dims(image_embedding) AS embed_dim,
           updated_at
    FROM media_ai_insights
    WHERE post_id = %s
""", (POST_ID,))
for r in cur.fetchall():
    print(f"  media_id={r[0]}")
    print(f"  status={r[1]}  is_safe={r[2]}")
    print(f"  tags={r[3]}")
    print(f"  scenes={r[4]}")
    print(f"  caption={r[5]}")
    print(f"  services_completed={r[6]}")
    print(f"  embedding_dim={r[7]}")
    print(f"  updated={r[8]}")

# ── 4. media_detected_faces ───────────────────────────────────────────────
print(f"\n--- media_detected_faces ---")
cur.execute("""
    SELECT mdf.id, mdf.media_id, mdf.bbox,
           mdf.confidence_score, mdf.identified_user_id,
           mdf.suggested_user_id, mdf.status,
           vector_dims(mdf.embedding) AS embed_dim
    FROM media_detected_faces mdf
    JOIN post_media pm ON pm.media_id = mdf.media_id
    WHERE pm.post_id = %s
""", (POST_ID,))
faces = cur.fetchall()
if not faces:
    print("  No faces detected for this post")
else:
    print(f"  {len(faces)} face(s) detected:")
    for f in faces:
        print(f"  id={f[0]}  media_id={f[1]}  confidence={f[3]:.4f}")
        print(f"    bbox={f[2]}")
        print(f"    identified_user_id={f[4]}  suggested_user_id={f[5]}")
        print(f"    status={f[6]}  embedding_dim={f[7]}")

# ── 5. read_model_media_search ────────────────────────────────────────────
print(f"\n--- read_model_media_search ---")
cur.execute("""
    SELECT rms.media_id, rms.post_id, rms.uploader_username,
           rms.ai_caption, rms.ai_tags, rms.ai_scenes,
           rms.is_safe, rms.media_url, rms.updated_at
    FROM read_model_media_search rms
    JOIN post_media pm ON pm.media_id = rms.media_id
    WHERE pm.post_id = %s
""", (POST_ID,))
for r in cur.fetchall():
    print(f"  media_id={r[0]}  post_id={r[1]}  uploader={r[2]}")
    print(f"  caption={r[3]}")
    print(f"  tags={r[4]}")
    print(f"  scenes={r[5]}")
    print(f"  is_safe={r[6]}")
    print(f"  media_url={r[7]}")
    print(f"  updated={r[8]}")

# ── 6. read_model_recommendations_knn ────────────────────────────────────
print(f"\n--- read_model_recommendations_knn ---")
cur.execute("""
    SELECT rknn.media_id, rknn.caption, rknn.is_safe,
           rknn.media_url, rknn.created_at,
           CASE WHEN rknn.image_embedding IS NOT NULL
                THEN 'PRESENT (' || length(rknn.image_embedding) || ' chars)'
                ELSE 'NULL' END AS embedding_status
    FROM read_model_recommendations_knn rknn
    WHERE rknn.media_id = %s
""", (POST_ID,))
for r in cur.fetchall():
    print(f"  media_id={r[0]}  is_safe={r[2]}")
    print(f"  caption={r[1]}")
    print(f"  media_url={r[3]}")
    print(f"  embedding={r[5]}")
    print(f"  created={r[4]}")

# ── 7. read_model_feed_personalized ──────────────────────────────────────
print(f"\n--- read_model_feed_personalized ---")
cur.execute("""
    SELECT rfp.media_id, rfp.post_id, rfp.uploader_username,
           rfp.caption, rfp.media_url,
           rfp.reaction_count, rfp.comment_count,
           rfp.created_at
    FROM read_model_feed_personalized rfp
    WHERE rfp.post_id = %s
""", (POST_ID,))
for r in cur.fetchall():
    print(f"  media_id={r[0]}  post_id={r[1]}  uploader={r[2]}")
    print(f"  caption={r[3]}")
    print(f"  media_url={r[4]}")
    print(f"  reactions={r[5]}  comments={r[6]}")
    print(f"  created={r[7]}")

# ── 8. read_model_post_search ─────────────────────────────────────────────
print(f"\n--- read_model_post_search ---")
cur.execute("""
    SELECT rps.post_id, rps.author_id, rps.author_username,
           rps.title, rps.body,
           rps.all_ai_tags, rps.all_ai_scenes,
           rps.all_detected_user_ids, rps.inferred_event_type,
           rps.inferred_tags, rps.categories,
           rps.total_reactions, rps.total_comments,
           rps.updated_at
    FROM read_model_post_search rps
    WHERE rps.post_id = %s
""", (POST_ID,))
row = cur.fetchone()
if not row:
    print("  NOT YET populated — post_aggregator still processing backlog")
else:
    print(f"  post_id={row[0]}  author_id={row[1]}  author={row[2]}")
    print(f"  title={row[3]}")
    print(f"  body={row[4]}")
    print(f"  all_ai_tags={row[5]}")
    print(f"  all_ai_scenes={row[6]}")
    print(f"  detected_users={row[7]}")
    print(f"  event_type={row[8]}")
    print(f"  inferred_tags={row[9]}")
    print(f"  categories={row[10]}")
    print(f"  reactions={row[11]}  comments={row[12]}")
    print(f"  updated={row[13]}")

# ── 9. read_model_face_search ─────────────────────────────────────────────
print(f"\n--- read_model_face_search (faces from this post) ---")
cur.execute("""
    SELECT rfs.id, rfs.face_id, rfs.media_id, rfs.post_id,
           rfs.identified_username, rfs.identified_user_id,
           rfs.match_confidence, rfs.bbox,
           CASE WHEN rfs.face_embedding IS NOT NULL
                THEN 'PRESENT (' || length(rfs.face_embedding) || ' chars)'
                ELSE 'NULL' END,
           rfs.created_at
    FROM read_model_face_search rfs
    WHERE rfs.post_id = %s
""", (POST_ID,))
rows = cur.fetchall()
if not rows:
    print("  No face search entries for this post")
else:
    print(f"  {len(rows)} face(s) in face search read model:")
    for r in rows:
        print(f"  id={r[0]}  face_id={r[1]}  media_id={r[2]}")
        print(f"    identified_username={r[4]}  identified_user_id={r[5]}")
        print(f"    confidence={r[6]}  bbox={r[7]}")
        print(f"    embedding={r[8]}  created={r[9]}")

conn.close()

# ── 10. Elasticsearch ─────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  ELASTICSEARCH")
print(SEP)
ES_HOST = os.getenv('ELASTICSEARCH_HOST', 'http://elasticsearch:9200')
ES_PASS = os.getenv('ELASTICSEARCH_PASSWORD', 'kaleidoscope1-elastic')
try:
    es = Elasticsearch(ES_HOST, basic_auth=('elastic', ES_PASS), verify_certs=False)
    MID = str(POST_ID)
    PID = str(POST_ID)

    checks = [
        ('media_search',        MID),
        ('post_search',         PID),
        ('recommendations_knn', MID),
        ('feed_personalized',   MID),
        ('face_search',         None),
    ]
    for index, doc_id in checks:
        if doc_id:
            try:
                doc = es.get(index=index, id=doc_id)['_source']
                print(f"\n[{index}] FOUND (id={doc_id})")
                for k, v in doc.items():
                    if k == 'image_embedding':
                        length = len(v) if isinstance(v, (list, str)) else '?'
                        print(f"  {k}: [{length} items/chars]")
                    elif isinstance(v, list) and len(v) > 6:
                        print(f"  {k}: {v[:6]} ... ({len(v)} total)")
                    else:
                        val = str(v)[:120] if v else v
                        print(f"  {k}: {val}")
            except Exception as e:
                print(f"\n[{index}] NOT FOUND — {e}")
        else:
            # Search face_search for this post
            try:
                res = es.search(index=index, body={'query': {'term': {'postId': POST_ID}}, 'size': 10})
                hits = res['hits']['hits']
                print(f"\n[{index}] {len(hits)} doc(s) for post_id={POST_ID}")
                for h in hits:
                    s = h['_source']
                    print(f"  _id={h['_id']}  faceId={s.get('faceId') or s.get('face_id')}  mediaId={s.get('mediaId') or s.get('media_id')}")
                    print(f"    identifiedUsername={s.get('identifiedUsername') or s.get('identified_username')}")
                    emb = s.get('faceEmbedding') or s.get('face_embedding') or []
                    print(f"    embedding_dims={len(emb) if isinstance(emb,list) else 'N/A'}")
            except Exception as e:
                print(f"\n[{index}] search error — {e}")
except Exception as ex:
    print(f"ES connection error: {ex}")

print(f"\n{SEP}")
print("  DONE")
print(SEP)
