"""
Re-trigger face recognition for recent posts by republishing to ml-inference-tasks.
Run: docker exec es_sync python3 /tmp/retrigger_face.py
"""
import os, redis as redislib, psycopg2, time, uuid

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB = dict(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD','npg_4mNWuybHc6sD'), sslmode='require'
)

r = redislib.from_url(REDIS_URL)

conn = psycopg2.connect(**DB)
cur  = conn.cursor()

# Get recent posts that have images in /tmp/kaleidoscope_media/
cur.execute("""
    SELECT pm.post_id, pm.media_id, pm.media_url
    FROM post_media pm
    WHERE pm.post_id = 15
    ORDER BY pm.post_id
""")
rows = cur.fetchall()
conn.close()

print("Re-triggering face recognition for recent posts:")
for post_id, media_id, media_url in rows:
    local_path = f"/tmp/kaleidoscope_media/{media_id}.jpg"
    corr_id = f"face-retrigger-{media_id}-{uuid.uuid4().hex[:8]}"
    msg_id = r.xadd('ml-inference-tasks', {
        'service':       'face_recognition',
        'mediaId':       str(media_id),
        'postId':        str(post_id),
        'localFilePath': local_path,
        'mediaUrl':      media_url or '',
        'correlationId': corr_id,
        'timestamp':     str(int(time.time()))
    })
    print(f"  post_id={post_id} media_id={media_id} -> {msg_id} (corr={corr_id})")

print("\nDone. Watch face_recognition logs for results.")
