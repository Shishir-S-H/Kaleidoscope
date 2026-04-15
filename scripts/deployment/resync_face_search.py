"""
Check es-sync-queue format and republish face_search docs 15 and 16
that are stuck in the es_sync batch without being flushed.
"""
import os, redis as r, json, psycopg2

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB = dict(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'), sslmode='require'
)

client = r.Redis.from_url(REDIS_URL, decode_responses=True)

# Check format of existing es-sync-queue messages
print("=== Sample es-sync-queue messages ===")
msgs = client.xrange('es-sync-queue', count=3)
for mid, data in msgs:
    print(f"  ID: {mid}")
    for k, v in data.items():
        print(f"    {k}: {v[:80] if isinstance(v, str) else v}")
    break

# Check face_search ES count
print("\n=== Current face_search state ===")
import urllib.request
req = urllib.request.Request(
    'http://elasticsearch:9200/face_search/_count',
    headers={'Authorization': 'Basic ZWxhc3RpYzprYWxlaWRvc2NvcGUxLWVsYXN0aWM='}
)
try:
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    print(f"  Total face_search docs: {data.get('count', '?')}")
except Exception as e:
    print(f"  ES query failed: {e}")

# Get the face_search docs from read_model_face_search that may not be indexed
conn = psycopg2.connect(**DB)
cur = conn.cursor()
cur.execute("SELECT id, face_id, media_id, post_id FROM read_model_face_search WHERE post_id = 16 ORDER BY id")
rows = cur.fetchall()
conn.close()
print(f"\nread_model_face_search for post_id=16: {len(rows)} rows")
for id, face_id, media_id, post_id in rows:
    print(f"  id={id}  face_id={face_id}  media_id={media_id}  post_id={post_id}")

# Republish sync messages with correct format
# Based on the es_sync worker which expects indexType and documentId
print("\n=== Publishing resync messages ===")
import time as _time
for id, face_id, media_id, post_id in rows:
    msg = {
        'indexType':     'face_search',
        'documentId':    str(id),
        'operation':     'index',
        'correlationId': f'resync-face-{id}',
        'timestamp':     _time.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
    }
    mid = client.xadd('es-sync-queue', msg)
    print(f"  Published face_search sync for id={id}: {mid}")

print("\nDone. Watch es_sync logs for indexing activity.")
