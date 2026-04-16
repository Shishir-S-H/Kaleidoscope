"""Check face-detection-results stream and consumer group state."""
import redis, os

r = redis.from_url(
    os.environ.get('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379'),
    decode_responses=True
)

print("=== face-detection-results stream ===")
info = r.xinfo_stream('face-detection-results')
print(f"  length={info['length']}  last-entry-id={info['last-generated-id']}")

print("\n=== Consumer groups ===")
groups = r.xinfo_groups('face-detection-results')
for g in groups:
    name = g['name']
    pending = g['pending']
    last_id = g['last-delivered-id']
    print(f"  {name}: pending={pending}  last-delivered-id={last_id}")

print("\n=== Last 3 messages in stream ===")
msgs = r.xrevrange('face-detection-results', '+', '-', count=3)
for msg_id, data in msgs:
    print(f"  id={msg_id}  media_id={data.get('mediaId')}  faces={data.get('facesDetected') or data.get('faces_detected') or data.get('faceCount')}")

print("\n=== Pending for backend-group ===")
pending = r.xpending_range('face-detection-results', 'backend-group', '-', '+', 10)
if pending:
    for p in pending:
        print(f"  msg_id={p['message_id']} consumer={p['consumer']} deliveries={p['times_delivered']}")
else:
    print("  (clean)")
