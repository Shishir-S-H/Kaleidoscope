"""
Clear stale messages from face-detection-results stream PEL.
These are old messages with null embeddings that were published before the fix.
Run: docker exec es_sync python3 /tmp/clear_face_detection_pel.py
"""
import redis as redislib, os

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redislib.from_url(REDIS_URL)

STREAM = 'face-detection-results'

print(f"=== Stream info: {STREAM} ===")
print(f"Total messages: {r.xlen(STREAM)}")

# List all consumer groups on this stream
try:
    groups = r.xinfo_groups(STREAM)
    for g in groups:
        name   = g.get('name', g.get(b'name', b'?'))
        if isinstance(name, bytes): name = name.decode()
        pending = g.get('pending', g.get(b'pending', 0))
        last_id = g.get('last-delivered-id', g.get(b'last-delivered-id', b'0'))
        if isinstance(last_id, bytes): last_id = last_id.decode()
        print(f"\nGroup: {name}  pending={pending}  last-id={last_id}")

        if pending == 0:
            print("  No pending messages.")
            continue

        # ACK all pending messages for this group
        acked = 0
        while True:
            pending_msgs = r.xpending_range(STREAM, name, '-', '+', 100)
            if not pending_msgs:
                break
            ids = [p['message_id'] for p in pending_msgs]
            acked += r.xack(STREAM, name, *ids)
            if len(ids) < 100:
                break
        print(f"  ACKed {acked} stale pending messages.")

        # Advance last-delivered-id to current end of stream
        latest = r.xrevrange(STREAM, '+', '-', count=1)
        if latest:
            latest_id = latest[0][0].decode() if isinstance(latest[0][0], bytes) else latest[0][0]
            r.execute_command('XGROUP', 'SETID', STREAM, name, latest_id)
            print(f"  Advanced group last-delivered-id to: {latest_id}")

except Exception as e:
    print(f"Error: {e}")

print(f"\nDone. Stream length: {r.xlen(STREAM)}")
print("Old null-embedding messages cleared. New posts will produce proper embeddings.")
