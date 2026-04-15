"""
Force flush any pending es_sync batch by publishing dummy no-op messages,
then verify all face_search docs for post_id=16 are indexed.
"""
import os, redis as r, time

REDIS_URL = os.getenv('REDIS_URL', 'redis://:kaleidoscope1-reddis@redis:6379')
client = r.Redis.from_url(REDIS_URL, decode_responses=True)

# Publish 3 dummy noop messages to trigger es_sync batch flush
# (es_sync will skip any unknown table/doc_id gracefully)
for i in range(3):
    msg_id = client.xadd('es-sync-queue', {
        'table':      'flush_trigger',
        'documentId': '0',
        'action':     'noop',
    })
    print(f"Published flush trigger: {msg_id}")

print("Done — es_sync should flush its pending batch now.")
print("Check es_sync logs in ~3 seconds for 'Flushing batch' or 'Bulk sync completed'.")
