"""
Clear Redis stream backlogs by acknowledging all pending messages.
Run inside es_sync: docker exec es_sync python3 /tmp/clear_backlog.py
"""
import redis as redislib, os, psycopg2

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redislib.from_url(REDIS_URL)

# Streams and their consumer groups
STREAM_GROUPS = {
    'post-aggregation-trigger': 'post-aggregator-group',
    'ml-inference-tasks':       'image-tagger-group',
    'ml-insights-results':      'ml-insights-consumer-group',
    'post-insights-enriched':   'post-insights-consumer-group',
    'es-sync-queue':            'es-sync-consumer-group',
    'ai-processing-dlq':        'dlq-processor-group',
    'post-image-processing':    'media-preprocessor-group',
}

print('=== Redis Stream Backlog Status ===\n')
for stream, group in STREAM_GROUPS.items():
    try:
        total = r.xlen(stream)
        try:
            pending_info = r.xpending(stream, group)
            pending_count = pending_info.get('pending', 0) if isinstance(pending_info, dict) else 0
        except Exception:
            pending_count = '?'
        print(f'  {stream}: total={total}, pending={pending_count}')
    except Exception as e:
        print(f'  {stream}: ERROR - {e}')

print('\n=== Clearing backlogs (XACK all pending) ===\n')

for stream, group in STREAM_GROUPS.items():
    try:
        acked_total = 0
        while True:
            # Get up to 100 pending messages at a time
            try:
                pending = r.xpending_range(stream, group, '-', '+', 100)
            except Exception:
                break
            if not pending:
                break
            msg_ids = [p['message_id'] for p in pending]
            if not msg_ids:
                break
            count = r.xack(stream, group, *msg_ids)
            acked_total += count
            if len(msg_ids) < 100:
                break
        if acked_total > 0:
            print(f'  {stream}: ACKed {acked_total} pending messages')
        else:
            print(f'  {stream}: no pending messages (already clear)')
    except Exception as e:
        print(f'  {stream}: ERROR - {e}')

# Also trim very long streams that have too many old messages
print('\n=== Trimming large streams (keep last 500 messages) ===\n')
for stream in ['post-image-processing', 'ml-inference-tasks', 'post-aggregation-trigger']:
    try:
        before = r.xlen(stream)
        r.xtrim(stream, maxlen=500, approximate=False)
        after = r.xlen(stream)
        print(f'  {stream}: {before} -> {after} messages')
    except Exception as e:
        print(f'  {stream}: ERROR trimming - {e}')

print('\n=== Final stream lengths ===\n')
for stream in STREAM_GROUPS.keys():
    try:
        print(f'  {stream}: {r.xlen(stream)}')
    except Exception as e:
        print(f'  {stream}: {e}')

# Now re-trigger aggregation for recent posts
print('\n=== Re-triggering aggregation for recent posts ===\n')
conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
cur = conn.cursor()

# Get posts that have fully processed media but may not have aggregated
cur.execute("""
    SELECT DISTINCT p.post_id, p.title,
           array_agg(pm.media_id ORDER BY pm.media_id) as media_ids,
           COUNT(pm.media_id) as total_media,
           COUNT(mai.media_id) FILTER (WHERE mai.status = 'COMPLETED') as completed_media
    FROM posts p
    JOIN post_media pm ON p.post_id = pm.post_id
    LEFT JOIN media_ai_insights mai ON pm.media_id = mai.media_id
    WHERE p.post_id >= 8
    GROUP BY p.post_id, p.title
    HAVING COUNT(pm.media_id) = COUNT(mai.media_id) FILTER (WHERE mai.status = 'COMPLETED')
    ORDER BY p.post_id
""")
posts = cur.fetchall()
print(f'Posts with all media completed: {[(r[0], r[1]) for r in posts]}')

for post_id, title, media_ids, total, completed in posts:
    msg_id = r.xadd('post-aggregation-trigger', {
        'postId': str(post_id),
        'allMediaIds': ','.join(str(m) for m in media_ids),
        'totalMedia': str(total),
        'correlationId': f'backlog-clear-retrigger-{post_id}',
        'timestamp': 'backlog-clear'
    })
    print(f'  Re-triggered post_id={post_id} ({title}) -> msg {msg_id}')

conn.close()
print('\nDone! Backlog cleared and recent posts re-triggered for aggregation.')
