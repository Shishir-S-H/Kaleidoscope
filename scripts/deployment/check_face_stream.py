import redis as r, os, json

client = r.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True)
STREAM = 'face-detection-results'
MIN_ID = '1776291349000-0'

msgs = client.xrange(STREAM, min=MIN_ID, max='+', count=5)
print(f"Messages in {STREAM} after Test-7 trigger:")
for mid, data in msgs:
    print(f"\nID: {mid}")
    emb = data.get('embedding', '')
    print(f"  mediaId: {data.get('mediaId')}")
    print(f"  faces: {data.get('faces','')[:100]}")
    print(f"  embedding[:80]: {emb[:80]}")

# Also check backend-group pending
groups = client.xinfo_groups(STREAM)
for g in groups:
    name = g.get('name') or g.get(b'name', b'').decode()
    pending = g.get('pending') or g.get(b'pending', 0)
    last_id = g.get('last-delivered-id') or g.get(b'last-delivered-id', b'').decode()
    print(f"\nGroup: {name}  pending={pending}  last_id={last_id}")
