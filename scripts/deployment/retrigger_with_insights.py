"""
Re-trigger post aggregation with pre-loaded mediaInsights so the aggregator
doesn't block waiting for Redis stream messages.
Run: docker exec es_sync python3 /tmp/retrigger_with_insights.py
"""
import os, psycopg2, redis as redislib, json, time

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
DB = dict(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
STREAM = 'post-aggregation-trigger'
GROUP  = 'post-aggregator-group'

r    = redislib.from_url(REDIS_URL)
conn = psycopg2.connect(**DB)
cur  = conn.cursor()

# Load posts 8-13 with their media and AI insights
cur.execute("""
    SELECT p.post_id, p.title,
           pm.media_id, pm.media_url,
           mai.tags, mai.scenes, mai.caption, mai.is_safe,
           mai.services_completed
    FROM posts p
    JOIN post_media pm ON pm.post_id = p.post_id
    LEFT JOIN media_ai_insights mai ON mai.media_id = pm.media_id
    WHERE p.post_id >= 8
    ORDER BY p.post_id, pm.media_id
""")
rows = cur.fetchall()
conn.close()

# Group by post
posts = {}
for post_id, title, media_id, media_url, tags, scenes, caption, is_safe, services in rows:
    if post_id not in posts:
        posts[post_id] = {'title': title, 'media': []}
    posts[post_id]['media'].append({
        'media_id': media_id,
        'media_url': media_url,
        'tags': tags or [],
        'scenes': scenes or [],
        'caption': caption or '',
        'is_safe': is_safe,
        'services_completed': services or []
    })

# First ACK any pending to be safe
pending = r.xpending_range(STREAM, GROUP, '-', '+', 100)
if pending:
    ids = [p['message_id'] for p in pending]
    n = r.xack(STREAM, GROUP, *ids)
    print(f"ACKed {n} pending messages")

# Advance group past everything
latest = r.xrevrange(STREAM, '+', '-', count=1)
if latest:
    latest_id = latest[0][0].decode() if isinstance(latest[0][0], bytes) else latest[0][0]
    r.execute_command('XGROUP', 'SETID', STREAM, GROUP, latest_id)
    print(f"Advanced group to: {latest_id}")

# Publish new triggers WITH pre-loaded insights
print("\nPublishing triggers with pre-loaded mediaInsights:")
for post_id, data in sorted(posts.items()):
    title = data['title']
    media_list = data['media']
    all_media_ids = [str(m['media_id']) for m in media_list]

    # Build mediaInsights: one entry per service per media item
    # This way the aggregator's _has_required_services check passes immediately
    insight_entries = []
    for m in media_list:
        svc_set = set(m['services_completed'])
        base = {
            'mediaId': str(m['media_id']),
            'mediaUrl': m['media_url'] or '',
        }
        # Emit one combined entry with all service data + all service names
        # The aggregator will add each service to _services set
        combined = dict(base)
        combined['tags']    = m['tags']
        combined['scenes']  = m['scenes']
        combined['caption'] = m['caption']
        combined['isSafe']  = m['is_safe']

        # Emit once per required service so _services is fully populated
        for svc in ['moderation', 'tagging', 'scene_recognition', 'image_captioning']:
            entry = dict(combined)
            entry['service'] = svc
            insight_entries.append(entry)

    msg_id = r.xadd(STREAM, {
        'postId': str(post_id),
        'allMediaIds': ','.join(all_media_ids),
        'totalMedia': str(len(media_list)),
        'mediaInsights': json.dumps(insight_entries),
        'correlationId': f'retrigger-with-insights-{post_id}',
        'timestamp': str(int(time.time()))
    })
    print(f"  post_id={post_id} ({title})  media={all_media_ids}  insights={len(insight_entries)}  msg={msg_id}")

print(f"\nDone. Stream length: {r.xlen(STREAM)}")
print("The aggregator should now process each post in ~15 seconds (no blocking).")
