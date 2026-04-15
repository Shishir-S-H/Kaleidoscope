"""
Clear the post_aggregator backlog of post_id=15 retrigger messages
and send a clean trigger for post_id=16 (Test-8) with preloaded mediaInsights.
"""
import os, redis as redislib, psycopg2, json, time

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB = dict(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'), sslmode='require'
)

STREAM = 'post-aggregation-trigger'
GROUP  = 'post-aggregator-group'

r = redislib.from_url(REDIS_URL)

# --- 1. Show current stream state ---
info = r.xinfo_groups(STREAM)
for g in info:
    name    = g.get('name') or g.get(b'name', b'').decode()
    pending = g.get('pending') or g.get(b'pending', 0)
    last_id = g.get('last-delivered-id') or g.get(b'last-delivered-id', b'').decode()
    print(f"Group: {name}  pending={pending}  last_id={last_id}")

# --- 2. ACK all pending in post-aggregator-group ---
pending_info = r.xpending(STREAM, GROUP)
total_pending = pending_info.get('pending', 0) if isinstance(pending_info, dict) else pending_info[0]
print(f"\nTotal pending in {GROUP}: {total_pending}")
if total_pending > 0:
    entries = r.xpending_range(STREAM, GROUP, min='-', max='+', count=100)
    for e in entries:
        mid = e.get('message_id') or e.get(b'message_id', b'').decode()
        r.xack(STREAM, GROUP, mid)
        print(f"  ACKed: {mid}")

# --- 3. Advance group past all current messages ---
stream_info = r.xinfo_stream(STREAM)
last_entry  = stream_info.get('last-generated-id') or stream_info.get(b'last-generated-id', b'').decode()
r.xgroup_setid(STREAM, GROUP, last_entry)
print(f"\nAdvanced {GROUP} last-id to: {last_entry}")

# --- 4. Load post_id=16 insights from DB ---
conn = psycopg2.connect(**DB)
cur  = conn.cursor()
cur.execute("""
    SELECT pm.media_id, pm.media_url,
           ai.tags, ai.scenes, ai.caption, ai.image_embedding IS NOT NULL
    FROM post_media pm
    LEFT JOIN media_ai_insights ai ON pm.media_id = ai.media_id
    WHERE pm.post_id = 16
""")
rows = cur.fetchall()
conn.close()

if not rows:
    print("ERROR: No media found for post_id=16")
    exit(1)

all_insight_entries = []
media_ids = []
for media_id, media_url, tags, scenes, caption, has_embedding in rows:
    mid = str(media_id)
    media_ids.append(mid)
    # One flat entry per service — matches _merge_media_entry expectations
    all_insight_entries.append({'mediaId': mid, 'service': 'moderation', 'isSafe': True, 'mediaUrl': media_url or ''})
    all_insight_entries.append({'mediaId': mid, 'service': 'tagging', 'tags': tags or []})
    all_insight_entries.append({'mediaId': mid, 'service': 'scene_recognition', 'scenes': scenes or []})
    all_insight_entries.append({'mediaId': mid, 'service': 'image_captioning', 'caption': caption or ''})
    print(f"  Loaded media_id={media_id}: tags={len(tags or [])}, caption_len={len(caption or '')}, {len(all_insight_entries)} entries total")

# --- 5. Publish fresh trigger for post_id=16 ---
corr_id  = f'fix-agg-16-{int(time.time())}'
msg = {
    'postId':        '16',
    'totalMedia':    str(len(media_ids)),
    'allMediaIds':   ','.join(media_ids),
    'correlationId': corr_id,
    'timestamp':     str(int(time.time())),
    'mediaInsights': json.dumps(all_insight_entries),
}
new_id = r.xadd(STREAM, msg)
print(f"\nPublished fresh trigger for post_id=16: {new_id} (corr={corr_id})")
print("Watch post_aggregator logs for completion...")
