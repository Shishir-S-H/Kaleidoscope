"""
Fix post_aggregator backlog by advancing the consumer group past all old messages,
then re-triggering aggregation only for post_ids 8-13.
Run inside es_sync: docker exec es_sync python3 /tmp/fix_aggregator_backlog.py
"""
import redis as redislib, os, psycopg2, time

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redislib.from_url(REDIS_URL)

STREAM = 'post-aggregation-trigger'
GROUP = 'post-aggregator-group'

print(f'=== Fix post-aggregation-trigger backlog ===\n')

# 1. Current state
total = r.xlen(STREAM)
print(f'Stream total messages: {total}')
try:
    info = r.xinfo_groups(STREAM)
    for g in info:
        if g.get('name') == GROUP or g.get(b'name', b'').decode() == GROUP:
            name = g.get('name', g.get(b'name', b'').decode())
            pending = g.get('pending', g.get(b'pending', 0))
            last_id = g.get('last-delivered-id', g.get(b'last-delivered-id', b'0').decode())
            print(f'Group: {name}, pending={pending}, last-delivered-id={last_id}')
except Exception as e:
    print(f'Could not get group info: {e}')

# 2. ACK all pending messages for this group
print(f'\nClearing pending messages for {GROUP}...')
acked = 0
while True:
    try:
        pending = r.xpending_range(STREAM, GROUP, '-', '+', 100)
    except Exception:
        break
    if not pending:
        break
    ids = [p['message_id'] for p in pending]
    if not ids:
        break
    acked += r.xack(STREAM, GROUP, *ids)
    if len(ids) < 100:
        break
print(f'ACKed {acked} pending messages')

# 3. Advance the consumer group's last-delivered-id to current end of stream
# This skips all old undelivered messages
latest_msg = r.xrevrange(STREAM, '+', '-', count=1)
if latest_msg:
    latest_id = latest_msg[0][0].decode() if isinstance(latest_msg[0][0], bytes) else latest_msg[0][0]
    r.execute_command('XGROUP', 'SETID', STREAM, GROUP, latest_id)
    print(f'\nAdvanced {GROUP} last-delivered-id to: {latest_id}')
    print('All old undelivered messages are now skipped.')
else:
    print('Stream is empty - nothing to advance')

# 4. Re-publish aggregation triggers for recent posts
print(f'\nRe-triggering aggregation for post_ids 8-13...')
conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
cur = conn.cursor()

cur.execute("""
    SELECT p.post_id, p.title,
           array_agg(pm.media_id::text ORDER BY pm.media_id) as media_ids,
           COUNT(pm.media_id) as total_media
    FROM posts p
    JOIN post_media pm ON p.post_id = pm.post_id
    WHERE p.post_id >= 8
    GROUP BY p.post_id, p.title
    ORDER BY p.post_id
""")
posts = cur.fetchall()
conn.close()

for post_id, title, media_ids, total_media in posts:
    msg_id = r.xadd(STREAM, {
        'postId': str(post_id),
        'allMediaIds': ','.join(media_ids),
        'totalMedia': str(total_media),
        'correlationId': f'fix-backlog-retrigger-{post_id}',
        'timestamp': str(int(time.time()))
    })
    print(f'  post_id={post_id} ({title}) -> {msg_id}')

print(f'\nDone. post_aggregator will now process only posts 8-13.')
print(f'Stream length after: {r.xlen(STREAM)}')
