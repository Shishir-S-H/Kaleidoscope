"""
Verify full pipeline for post_id=8 after re-trigger.
Run inside es_sync: docker exec es_sync python3 /tmp/verify_post8.py
"""
import os, psycopg2, json
from elasticsearch import Elasticsearch

db_host = 'ep-spring-flower-a100y0kt-pooler.ap-southeast-1.aws.neon.tech'
db_name = 'neondb'
db_user = 'neondb_owner'
db_pass = os.getenv('DB_PASSWORD', 'npg_4mNWuybHc6sD')

es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
es_pass = os.getenv('ELASTICSEARCH_PASSWORD', 'kaleidoscope1-elastic')

conn = psycopg2.connect(host=db_host, dbname=db_name, user=db_user, password=db_pass, sslmode='require')
cur = conn.cursor()

print('=' * 60)
print('POST_ID=8 PIPELINE VERIFICATION')
print('=' * 60)

# 1. media_ai_insights
cur.execute("""
    SELECT media_id, status, is_safe, caption,
           array_length(tags, 1) as tag_count,
           array_length(scenes, 1) as scene_count,
           CASE WHEN image_embedding IS NOT NULL THEN vector_dims(image_embedding) ELSE 0 END as embedding_dim,
           services_completed
    FROM media_ai_insights WHERE media_id = 8
""")
row = cur.fetchone()
print('\n[1] media_ai_insights (media_id=8):')
if row:
    print(f'  status:          {row[1]}')
    print(f'  is_safe:         {row[2]}')
    print(f'  caption:         {row[3]}')
    print(f'  tag_count:       {row[4]}')
    print(f'  scene_count:     {row[5]}')
    print(f'  embedding_dim:   {row[6]}')
    print(f'  services_done:   {row[7]}')
else:
    print('  NOT FOUND')

# 2. read_model_media_search
cur.execute("""
    SELECT media_id, post_id, ai_caption,
           length(ai_tags) as tag_len,
           length(image_embedding) as embed_len,
           is_safe
    FROM read_model_media_search WHERE media_id = 8
""")
row = cur.fetchone()
print('\n[2] read_model_media_search (media_id=8):')
if row:
    print(f'  post_id:         {row[1]}')
    print(f'  ai_caption:      {row[2]}')
    print(f'  ai_tags_length:  {row[3]}')
    print(f'  embedding_chars: {row[4]}')
    print(f'  is_safe:         {row[5]}')
else:
    print('  NOT FOUND')

# 3. read_model_recommendations_knn
cur.execute("""
    SELECT media_id, length(image_embedding) as embed_len, caption, is_safe
    FROM read_model_recommendations_knn WHERE media_id = 8
""")
row = cur.fetchone()
print('\n[3] read_model_recommendations_knn (media_id=8):')
if row:
    print(f'  embedding_chars: {row[1]}')
    print(f'  caption:         {row[2]}')
    print(f'  is_safe:         {row[3]}')
else:
    print('  NOT FOUND')

# 4. read_model_feed_personalized
cur.execute("""
    SELECT media_id, post_id, uploader_username, caption
    FROM read_model_feed_personalized WHERE media_id = 8
""")
row = cur.fetchone()
print('\n[4] read_model_feed_personalized (media_id=8):')
if row:
    print(f'  post_id:         {row[1]}')
    print(f'  uploader:        {row[2]}')
    print(f'  caption:         {row[3]}')
else:
    print('  NOT FOUND')

# 5. read_model_post_search
cur.execute("""
    SELECT post_id, title, all_tags_combined, caption_combined
    FROM read_model_post_search WHERE post_id = 8
""")
row = cur.fetchone()
print('\n[5] read_model_post_search (post_id=8):')
if row:
    print(f'  title:                {row[1]}')
    print(f'  all_tags_combined:    {row[2]}')
    print(f'  caption_combined:     {row[3]}')
else:
    print('  NOT FOUND (aggregation may still be processing)')

conn.close()

# 6. Elasticsearch indexes
print('\n[6] Elasticsearch indexes:')
try:
    es = Elasticsearch(es_url, basic_auth=('elastic', es_pass), verify_certs=False)
    for index, doc_id, label in [
        ('media_search', '8', 'media_search media_id=8'),
        ('post_search', '8', 'post_search post_id=8'),
        ('recommendations_knn', '8', 'recommendations_knn media_id=8'),
        ('feed_personalized', '8', 'feed_personalized media_id=8'),
    ]:
        try:
            doc = es.get(index=index, id=doc_id)
            src = doc['_source']
            print(f'  {label}: FOUND')
            if 'aiCaption' in src:
                print(f'    caption: {src.get("aiCaption","")[:60]}')
            if 'aiTags' in src:
                print(f'    tags: {src.get("aiTags",[])}')
        except Exception as e:
            print(f'  {label}: NOT FOUND ({e})')
except Exception as e:
    print(f'  ES connection failed: {e}')

print('\n' + '=' * 60)
