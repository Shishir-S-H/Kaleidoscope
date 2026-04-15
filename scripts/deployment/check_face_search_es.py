"""Check face_search ES index status and mapping."""
import os, requests, json

ES_URL = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')

# Check index mapping
r = requests.get(f'{ES_URL}/face_search/_mapping', timeout=10)
print("=== face_search mapping ===")
try:
    mapping = r.json()
    props = mapping.get('face_search', {}).get('mappings', {}).get('properties', {})
    for field, config in props.items():
        print(f"  {field}: {config.get('type','?')} {config.get('dims','')}")
except Exception as e:
    print(f"  Error: {e}")

# Count docs
r2 = requests.get(f'{ES_URL}/face_search/_count', timeout=10)
count_data = r2.json()
print(f"\n=== face_search document count: {count_data.get('count', '?')} ===")

# Get all docs
r3 = requests.get(f'{ES_URL}/face_search/_search?size=20', timeout=10)
hits = r3.json().get('hits', {}).get('hits', [])
print(f"\n=== All face_search documents ({len(hits)}) ===")
for h in hits:
    src = h.get('_source', {})
    emb = src.get('faceEmbedding') or src.get('face_embedding') or []
    print(f"  id={h['_id']}  mediaId={src.get('mediaId')}  postId={src.get('postId')}  embedding_len={len(emb) if isinstance(emb,list) else 'str:'+str(len(str(emb)))}")

# Check for errors in the sync queue
r4 = requests.get(f'{ES_URL}/es-sync-queue/_count', timeout=10)
if r4.status_code == 200:
    print(f"\nES sync queue: {r4.json().get('count', '?')} msgs")
