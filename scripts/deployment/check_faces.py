"""
Check face detection and identification results for all posts.
Run inside es_sync: docker exec es_sync python3 /tmp/check_faces.py
"""
import psycopg2, os

conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
cur = conn.cursor()

print('=== Face Detection Pipeline Check ===\n')

# First check actual columns in media_detected_faces
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'media_detected_faces'
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print(f'[Schema] media_detected_faces columns: {cols}')

# media_detected_faces — use only confirmed columns
cur.execute("""
    SELECT mdf.id, mdf.media_id, mai.post_id,
           mdf.embedding IS NOT NULL as has_embedding,
           mdf.bbox
    FROM media_detected_faces mdf
    JOIN media_ai_insights mai ON mdf.media_id = mai.media_id
    ORDER BY mdf.media_id DESC
    LIMIT 20
""")
faces = cur.fetchall()
print(f'\n[DB] media_detected_faces (latest 20):')
if faces:
    for f in faces:
        print(f'  face_id={f[0]}, media_id={f[1]}, post_id={f[2]}, has_embedding={f[3]}, bbox={f[4]}')
else:
    print('  NO faces detected yet')

# Check read_model_face_search columns
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'read_model_face_search'
    ORDER BY ordinal_position
""")
face_cols = [r[0] for r in cur.fetchall()]
print(f'\n[Schema] read_model_face_search columns: {face_cols}')

if face_cols:
    cur.execute(f"SELECT * FROM read_model_face_search ORDER BY media_id DESC LIMIT 10")
    face_models = cur.fetchall()
    print(f'[DB] read_model_face_search ({len(face_models)} rows):')
    for i, row in enumerate(face_models):
        print(f'  {dict(zip(face_cols, row))}')

# Count face detections per post
cur.execute("""
    SELECT mai.post_id, p.title, COUNT(mdf.id) as face_count
    FROM posts p
    JOIN post_media pm ON p.post_id = pm.post_id
    JOIN media_ai_insights mai ON pm.media_id = mai.media_id
    LEFT JOIN media_detected_faces mdf ON mai.media_id = mdf.media_id
    WHERE p.post_id >= 8
    GROUP BY mai.post_id, p.title
    ORDER BY mai.post_id DESC
""")
print('\n[Summary] Face detections per post:')
for row in cur.fetchall():
    print(f'  post_id={row[0]} ({row[1]}): {row[2]} faces detected')

# Check face recognition service (face_recognition container logs via Redis stream)
import redis as redislib
REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redislib.from_url(REDIS_URL)

print('\n[Redis] Face-related stream lengths:')
for stream in ['face-detection-results', 'face-recognition-results', 'ai-processing-dlq']:
    try:
        print(f'  {stream}: {r.xlen(stream)}')
    except:
        print(f'  {stream}: not found')

# ES face_search
print('\n[ES] face_search index:')
try:
    from elasticsearch import Elasticsearch
    es = Elasticsearch(
        os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200'),
        basic_auth=('elastic', os.getenv('ELASTICSEARCH_PASSWORD', 'kaleidoscope1-elastic')),
        verify_certs=False
    )
    count = es.count(index='face_search')['count']
    print(f'  Total docs in face_search index: {count}')
    if count > 0:
        hits = es.search(index='face_search', body={'query': {'match_all': {}}, 'size': 5})
        for h in hits['hits']['hits']:
            src = h['_source']
            print(f'  doc: media_id={src.get("mediaId")}, post_id={src.get("postId")}, identified_user={src.get("identifiedUsername","<not identified>")}')
except Exception as e:
    print(f'  ES error: {e}')

conn.close()
