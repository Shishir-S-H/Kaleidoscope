"""Retrigger face recognition for post_id=17 (Test-10), media_id=17."""
import redis, psycopg2, json, uuid, os

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB_HOST = 'ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech'

conn = psycopg2.connect(host=DB_HOST, dbname='neondb', user='neondb_owner',
                        password='npg_4mNWuybHc6sD', sslmode='require')
cur = conn.cursor()
cur.execute("SELECT media_id, media_url FROM post_media WHERE post_id = 17")
rows = cur.fetchall()
conn.close()

r = redis.from_url(REDIS_URL, decode_responses=True)

print(f"Retriggering face recognition for {len(rows)} media items in post_id=17...")
for media_id, media_url in rows:
    corr_id = str(uuid.uuid4())
    msg = {
        'mediaId':       str(media_id),
        'mediaUrl':      media_url or '',
        'postId':        '17',
        'correlationId': corr_id,
        'service':       'face_recognition',
    }
    msg_id = r.xadd('post-image-processing', msg)
    print(f"  Published to post-image-processing: media_id={media_id}, msg_id={msg_id}")

print("Done. Face recognition will re-detect and publish to face-detection-results.")
