"""
Fix post_id=17 aggregation pipeline:
1. Clear post-aggregation-trigger PEL (stuck second trigger)
2. Clear post-insights-enriched PEL (27 stuck old messages)
3. Load actual insights from DB and re-publish trigger with mediaInsights pre-loaded
4. Aggregator will process it and publish fresh post-insights-enriched message
"""
import redis, psycopg2, json, time, os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB_HOST = 'ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech'

r = redis.from_url(REDIS_URL, decode_responses=True)
conn = psycopg2.connect(host=DB_HOST, dbname='neondb', user='neondb_owner',
                        password='npg_4mNWuybHc6sD', sslmode='require')
cur = conn.cursor()

# ─── 1. Clear post-aggregation-trigger PEL ───────────────────────────────────
print("=== 1. Clearing post-aggregation-trigger PEL ===")
pending = r.xpending_range('post-aggregation-trigger', 'post-aggregator-group', '-', '+', 50)
if pending:
    ids = [p['message_id'] for p in pending]
    r.xack('post-aggregation-trigger', 'post-aggregator-group', *ids)
    print(f"  ACKed {len(ids)} messages: {ids}")
    # Advance last-delivered-id
    last = r.xrevrange('post-aggregation-trigger', '+', '-', count=1)
    if last:
        last_id = last[0][0]
        r.xgroup_setid('post-aggregation-trigger', 'post-aggregator-group', last_id)
        print(f"  Advanced last-delivered-id to: {last_id}")
else:
    print("  (already clean)")

# ─── 2. Clear post-insights-enriched PEL ─────────────────────────────────────
print("\n=== 2. Clearing post-insights-enriched PEL ===")
total_acked = 0
while True:
    pending = r.xpending_range('post-insights-enriched', 'backend-group', '-', '+', 100)
    if not pending:
        break
    ids = [p['message_id'] for p in pending]
    r.xack('post-insights-enriched', 'backend-group', *ids)
    total_acked += len(ids)
print(f"  ACKed {total_acked} stale messages")

# ─── 3. Load actual insights for post_id=17 from DB ─────────────────────────
print("\n=== 3. Loading insights from DB for post_id=17 ===")
cur.execute("""
    SELECT pm.media_id, pm.media_url,
           ai.tags, ai.scenes, ai.caption, ai.image_embedding IS NOT NULL as has_embedding
    FROM post_media pm
    LEFT JOIN media_ai_insights ai ON pm.media_id = ai.media_id
    WHERE pm.post_id = 17
""")
rows = cur.fetchall()
conn.close()

all_insight_entries = []
media_ids = []
for media_id, media_url, tags, scenes, caption, has_embedding in rows:
    mid = str(media_id)
    media_ids.append(mid)
    all_insight_entries.append({'mediaId': mid, 'service': 'moderation', 'isSafe': True, 'mediaUrl': media_url or ''})
    all_insight_entries.append({'mediaId': mid, 'service': 'tagging', 'tags': tags or []})
    all_insight_entries.append({'mediaId': mid, 'service': 'scene_recognition', 'scenes': scenes or []})
    all_insight_entries.append({'mediaId': mid, 'service': 'image_captioning', 'caption': caption or ''})
    print(f"  media_id={media_id}: tags={len(tags or [])} scenes={len(scenes or [])} caption_len={len(caption or '')} embed={has_embedding}")

# ─── 4. Publish fresh trigger with pre-loaded insights ───────────────────────
print("\n=== 4. Publishing fresh aggregation trigger for post_id=17 ===")
corr_id = f'fix-agg-17-{int(time.time())}'
msg = {
    'postId':        '17',
    'totalMedia':    str(len(media_ids)),
    'allMediaIds':   ','.join(media_ids),
    'correlationId': corr_id,
    'timestamp':     str(int(time.time())),
    'mediaInsights': json.dumps(all_insight_entries),
}
new_id = r.xadd('post-aggregation-trigger', msg)
print(f"  Published: {new_id}")
print(f"  correlationId: {corr_id}")
print(f"  mediaInsights entries: {len(all_insight_entries)}")
print("\nDone. Restart post_aggregator then wait ~5s for it to process and publish to post-insights-enriched.")
