"""
Find the latest post and trace its pipeline status.
Run inside es_sync: docker exec es_sync python3 /tmp/find_latest_post.py
"""
import psycopg2, os

conn = psycopg2.connect(
    host='ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech',
    dbname='neondb', user='neondb_owner',
    password=os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD'),
    sslmode='require'
)
cur = conn.cursor()

# Find latest posts
cur.execute("""
    SELECT p.post_id, p.title, p.created_at, p.status,
           COUNT(pm.media_id) as media_count
    FROM posts p
    LEFT JOIN post_media pm ON p.post_id = pm.post_id
    GROUP BY p.post_id, p.title, p.created_at, p.status
    ORDER BY p.post_id DESC
    LIMIT 5
""")
posts = cur.fetchall()
print('=== Latest 5 posts ===')
for row in posts:
    print(f'  post_id={row[0]}, title={row[1]}, status={row[3]}, media={row[4]}, created={row[2]}')

if not posts:
    conn.close()
    exit()

# Focus on the latest post (Test-4 = post_id=12)
latest_post_id = posts[0][0]
print(f'\n=== Full pipeline trace for post_id={latest_post_id} ({posts[0][1]}) ===')

# media_ai_insights
cur.execute("""
    SELECT media_id, status, is_safe, caption,
           array_length(tags,1) as tags,
           array_length(scenes,1) as scenes,
           CASE WHEN image_embedding IS NOT NULL THEN vector_dims(image_embedding) ELSE 0 END as embed_dim,
           services_completed
    FROM media_ai_insights
    WHERE media_id IN (SELECT media_id FROM post_media WHERE post_id = %s)
""", (latest_post_id,))
insights = cur.fetchall()
print(f'\n[DB] media_ai_insights ({len(insights)} rows):')
for r in insights:
    media_id, status, is_safe, caption, tag_count, scene_count, embed_dim, services = r
    print(f'  media_id={media_id}')
    print(f'    status={status}, is_safe={is_safe}')
    print(f'    caption={caption[:80] if caption else None}')
    print(f'    tag_count={tag_count}, scene_count={scene_count}, embed_dim={embed_dim}')
    print(f'    services_completed={services}')

# read_model_media_search
cur.execute("SELECT media_id, ai_caption FROM read_model_media_search WHERE media_id IN (SELECT media_id FROM post_media WHERE post_id = %s)", (latest_post_id,))
rows = cur.fetchall()
print(f'\n[DB] read_model_media_search ({len(rows)} rows):')
for r in rows: print(f'  media_id={r[0]}, caption={r[1]}')

# read_model_recommendations_knn
cur.execute("SELECT media_id, length(image_embedding) FROM read_model_recommendations_knn WHERE media_id IN (SELECT media_id FROM post_media WHERE post_id = %s)", (latest_post_id,))
rows = cur.fetchall()
print(f'\n[DB] read_model_recommendations_knn ({len(rows)} rows):')
for r in rows: print(f'  media_id={r[0]}, embedding_chars={r[1]}')

# read_model_feed_personalized
cur.execute("SELECT media_id, caption FROM read_model_feed_personalized WHERE media_id IN (SELECT media_id FROM post_media WHERE post_id = %s)", (latest_post_id,))
rows = cur.fetchall()
print(f'\n[DB] read_model_feed_personalized ({len(rows)} rows):')
for r in rows: print(f'  media_id={r[0]}, caption={r[1]}')

# read_model_post_search
cur.execute("SELECT post_id, title, all_ai_tags, all_ai_scenes FROM read_model_post_search WHERE post_id = %s", (latest_post_id,))
row = cur.fetchone()
print(f'\n[DB] read_model_post_search:')
if row:
    print(f'  post_id={row[0]}, title={row[1]}')
    print(f'  tags={row[2]}, scenes={row[3]}')
else:
    print(f'  NOT YET - aggregation still pending')

# Get media_ids for ES check
cur.execute("SELECT media_id FROM post_media WHERE post_id = %s", (latest_post_id,))
media_ids = [str(r[0]) for r in cur.fetchall()]
conn.close()

# Elasticsearch
print(f'\n[ES] Elasticsearch index checks (media_ids={media_ids}):')
try:
    from elasticsearch import Elasticsearch
    es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
    es_pass = os.getenv('ELASTICSEARCH_PASSWORD', 'kaleidoscope1-elastic')
    es = Elasticsearch(es_url, basic_auth=('elastic', es_pass), verify_certs=False)
    checks = [
        ('media_search',        media_ids[0] if media_ids else '0', 'media_search'),
        ('post_search',         str(latest_post_id),                 'post_search'),
        ('recommendations_knn', media_ids[0] if media_ids else '0', 'recommendations_knn'),
        ('feed_personalized',   media_ids[0] if media_ids else '0', 'feed_personalized'),
    ]
    for index, doc_id, label in checks:
        try:
            doc = es.get(index=index, id=doc_id)
            src = doc['_source']
            extras = []
            if 'aiCaption' in src: extras.append(f'caption={str(src["aiCaption"])[:60]}')
            if 'aiTags'   in src: extras.append(f'tags={src["aiTags"]}')
            if 'scenes'   in src: extras.append(f'scenes={src["scenes"]}')
            print(f'  {label}: FOUND | {" | ".join(extras)}')
        except Exception as e:
            print(f'  {label}: NOT FOUND - {e}')
except Exception as e:
    print(f'  ES connection error: {e}')
