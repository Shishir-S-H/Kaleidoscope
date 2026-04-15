"""
ACK the stuck pending message in post-aggregation-trigger and show stream state.
Run: docker exec es_sync python3 /tmp/ack_and_reset.py
"""
import redis as redislib, os

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redislib.from_url(REDIS_URL)

STREAM = 'post-aggregation-trigger'
GROUP  = 'post-aggregator-group'

print("=== Current pending messages ===")
try:
    pending = r.xpending_range(STREAM, GROUP, '-', '+', 20)
    print(f"Pending count: {len(pending)}")
    for p in pending:
        msg_id  = p['message_id']
        idle_ms = p.get('time_since_delivered', 0)
        print(f"  id={msg_id}  idle={idle_ms//1000}s  deliveries={p.get('times_delivered',0)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== ACK all pending messages ===")
acked = 0
while True:
    pending = r.xpending_range(STREAM, GROUP, '-', '+', 100)
    if not pending:
        break
    ids = [p['message_id'] for p in pending]
    acked += r.xack(STREAM, GROUP, *ids)
    if len(ids) < 100:
        break
print(f"ACKed {acked} messages")

print("\n=== Verify consumer group state ===")
info = r.xinfo_groups(STREAM)
for g in info:
    name   = g.get('name', g.get(b'name', b'').decode())
    pend   = g.get('pending', g.get(b'pending', 0))
    lastid = g.get('last-delivered-id', g.get(b'last-delivered-id', b'0'))
    if isinstance(lastid, bytes):
        lastid = lastid.decode()
    print(f"  group={name}  pending={pend}  last-id={lastid}")

print("\n=== Our new messages in stream ===")
# Show messages after the SETID we applied
msgs = r.xrange(STREAM, '1776288359962-0', '+', count=20)
print(f"Found {len(msgs)} new message(s) for posts 8-13:")
for mid, data in msgs:
    if isinstance(mid, bytes):
        mid = mid.decode()
    post_id = data.get(b'postId', data.get('postId', b'?'))
    if isinstance(post_id, bytes):
        post_id = post_id.decode()
    print(f"  id={mid}  post_id={post_id}")

print("\nDone. Restart post_aggregator to consume these messages.")
