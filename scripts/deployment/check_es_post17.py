"""Check Elasticsearch indexes for post_id=17 (Test-10)."""
from elasticsearch import Elasticsearch

ES_URL = "http://elasticsearch:9200"
ES_USER = "elastic"
ES_PASS = "kaleidoscope1-elastic"
POST_ID = 17

es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASS))

print("=== [ES] Elasticsearch Indexes for Test-10 (post_id=17) ===\n")

# media_search (by mediaId=17)
print("[media_search] (query: mediaId=17)")
try:
    res = es.search(index="media_search", body={"query": {"term": {"mediaId": 17}}, "size": 10})
    hits = res['hits']['hits']
    print(f"  docs_found: {len(hits)}")
    for h in hits:
        s = h['_source']
        print(f"  _id={h['_id']}  mediaId={s.get('mediaId')}  postId={s.get('postId')}")
        print(f"    caption={str(s.get('caption',''))[:100]}")
        print(f"    tags={s.get('tags')}")
        print(f"    scenes={s.get('scenes')}")
except Exception as e:
    print(f"  ERROR: {e}")

# post_search (by postId=17)
print("\n[post_search] (query: postId=17)")
try:
    res = es.search(index="post_search", body={"query": {"term": {"postId": POST_ID}}, "size": 10})
    hits = res['hits']['hits']
    print(f"  docs_found: {len(hits)}")
    for h in hits:
        s = h['_source']
        print(f"  _id={h['_id']}  postId={s.get('postId')}  title={s.get('title')}")
        print(f"    tags={s.get('tags')}  scenes={s.get('scenes')}")
        print(f"    face_count={s.get('faceCount') or s.get('face_count')}")
except Exception as e:
    print(f"  ERROR: {e}")

# recommendations_knn (by mediaId=17)
print("\n[recommendations_knn] (query: mediaId=17)")
try:
    res = es.search(index="recommendations_knn", body={"query": {"term": {"mediaId": 17}}, "size": 5})
    hits = res['hits']['hits']
    print(f"  docs_found: {len(hits)}")
    for h in hits:
        s = h['_source']
        emb = s.get('embedding') or s.get('imageEmbedding') or []
        print(f"  _id={h['_id']}  mediaId={s.get('mediaId')}  embedding_dims={len(emb) if isinstance(emb, list) else 'N/A'}")
except Exception as e:
    print(f"  ERROR: {e}")

# feed_personalized (by mediaId=17)
print("\n[feed_personalized] (query: mediaId=17)")
try:
    res = es.search(index="feed_personalized", body={"query": {"term": {"mediaId": 17}}, "size": 5})
    hits = res['hits']['hits']
    print(f"  docs_found: {len(hits)}")
    for h in hits:
        s = h['_source']
        print(f"  _id={h['_id']}  mediaId={s.get('mediaId')}  postId={s.get('postId')}")
        print(f"    caption={str(s.get('caption',''))[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")

# face_search (by postId=17)
print("\n[face_search] (query: postId=17)")
try:
    res = es.search(index="face_search", body={"query": {"term": {"postId": POST_ID}}, "size": 20})
    hits = res['hits']['hits']
    print(f"  docs_found: {len(hits)}")
    for h in hits:
        s = h['_source']
        emb = s.get('faceEmbedding') or s.get('face_embedding') or []
        print(f"  _id={h['_id']}  faceId={s.get('faceId')}  mediaId={s.get('mediaId')}  postId={s.get('postId')}")
        print(f"    identifiedUsername={s.get('identifiedUsername')}  embedding_dims={len(emb) if isinstance(emb, list) else 'N/A'}")
except Exception as e:
    print(f"  ERROR: {e}")
