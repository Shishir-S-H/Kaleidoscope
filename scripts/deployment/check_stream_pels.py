import redis, os

r = redis.from_url(os.environ['REDIS_URL'], decode_responses=True)
streams = ['post-aggregation-trigger', 'ml-inference-tasks', 'es-sync-queue', 'post-image-processing']
for stream in streams:
    try:
        info = r.xinfo_groups(stream)
        for g in info:
            name = g.get('name', '')
            pending = g.get('pending', 0)
            status = 'WARN' if pending > 0 else 'OK  '
            print(f'{status}: {stream} / {name}: {pending} pending')
    except Exception as e:
        print(f'SKIP: {stream}: {e}')
