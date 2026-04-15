"""
Run this script INSIDE the es_sync container:
  docker exec es_sync python3 /tmp/retrigger_post8.py
"""
import os, sys, psycopg2, redis as redislib

# Neon DB connection (external cloud DB)
db_host = 'ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech'
db_name = 'neondb'
db_user = 'neondb_owner'
db_pass = os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD')
db_port = 5432

redis_url = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')

print(f'Connecting to DB: {db_user}@{db_host}/{db_name}')
print(f'Redis URL: {redis_url}')

conn = psycopg2.connect(
    host=db_host, port=db_port, dbname=db_name,
    user=db_user, password=db_pass,
    sslmode='require'
)
cur = conn.cursor()

# Get media for post_id=8
cur.execute("""
    SELECT pm.media_id, pm.media_url, pm.media_type
    FROM post_media pm
    WHERE pm.post_id = 8
""")
rows = cur.fetchall()
print(f'\nFound {len(rows)} media item(s) for post_id=8:')
for r in rows:
    print(f'  media_id={r[0]}, media_type={r[2]}, url={r[1]}')

if not rows:
    print('ERROR: No media found for post_id=8')
    conn.close()
    sys.exit(1)

# Connect to Redis
r = redislib.from_url(redis_url)
print(f'\nRedis ping: {r.ping()}')
print(f'Current post-image-processing length: {r.xlen("post-image-processing")}')
print(f'Current ai-processing-dlq length:     {r.xlen("ai-processing-dlq")}')

# Re-publish each media item to post-image-processing
print('\nPublishing to post-image-processing:')
for media_id, media_url, media_type in rows:
    msg_id = r.xadd('post-image-processing', {
        'postId': '8',
        'mediaId': str(media_id),
        'mediaUrl': media_url or '',
        'mediaType': media_type or 'IMAGE',
        'correlationId': f'retrigger-post8-media{media_id}-v3'
    })
    print(f'  media_id={media_id} -> stream message id: {msg_id}')

conn.close()
print(f'\nDone! post_id=8 re-triggered.')
print(f'New post-image-processing length: {r.xlen("post-image-processing")}')
