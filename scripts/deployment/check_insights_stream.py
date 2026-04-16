"""Check post-insights-enriched stream state and PEL."""
import redis, os, json

r = redis.from_url(
    os.environ.get('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379'),
    decode_responses=True
)

stream = 'post-insights-enriched'
print(f"=== {stream} ===")
info = r.xinfo_stream(stream)
print(f"  length={info['length']}  last-entry={info['last-generated-id']}")

groups = r.xinfo_groups(stream)
for g in groups:
    print(f"  group={g['name']}  pending={g['pending']}  last-delivered={g['last-delivered-id']}")

print("\n=== Last 3 messages ===")
msgs = r.xrevrange(stream, '+', '-', count=3)
for msg_id, data in msgs:
    print(f"  id={msg_id}")
    post_id = data.get('postId')
    event_type = data.get('eventType')
    insights_raw = data.get('mediaInsights') or data.get('insights') or data.get('enrichedData')
    print(f"    postId={post_id}  eventType={event_type}")
    if insights_raw:
        try:
            parsed = json.loads(insights_raw)
            if isinstance(parsed, dict):
                print(f"    tag_count={len(parsed.get('tags',[]))}  scene_count={len(parsed.get('scenes',[]))}")
                print(f"    caption={str(parsed.get('caption',''))[:80]}")
            elif isinstance(parsed, list):
                print(f"    insights_entries={len(parsed)}")
        except Exception:
            print(f"    insights_raw={insights_raw[:100]}")

print("\n=== PEL for backend-group ===")
pending = r.xpending_range(stream, 'backend-group', '-', '+', 10)
if pending:
    for p in pending:
        print(f"  STUCK: msg_id={p['message_id']} consumer={p['consumer']} deliveries={p['times_delivered']}")
else:
    print("  (clean)")

# Also check post-aggregation-trigger PEL
print("\n=== post-aggregation-trigger PEL ===")
pending2 = r.xpending_range('post-aggregation-trigger', 'post-aggregator-group', '-', '+', 10)
if pending2:
    for p in pending2:
        print(f"  STUCK: msg_id={p['message_id']} consumer={p['consumer']} deliveries={p['times_delivered']}")
else:
    print("  (clean)")
