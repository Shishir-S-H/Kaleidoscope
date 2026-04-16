"""Force-flush remaining face_search docs 22-24 for post_id=17."""
import redis, os, time

REDIS_URL = os.environ.get('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
r = redis.from_url(REDIS_URL, decode_responses=True)

print("Resending es-sync-queue messages for face_search docs 22, 23, 24...")
for doc_id in [22, 23, 24]:
    msg = {
        'indexType':     'face_search',
        'documentId':    str(doc_id),
        'operation':     'index',
        'correlationId': f'flush-face17-{doc_id}',
        'timestamp':     time.strftime('%Y-%m-%dT%H:%M:%S.000000000Z'),
    }
    mid = r.xadd('es-sync-queue', msg)
    print(f"  Published documentId={doc_id}: {mid}")

print("Done. es_sync will flush the batch on the next iteration.")
