from elasticsearch import Elasticsearch
es = Elasticsearch("http://elasticsearch:9200", basic_auth=("elastic", "kaleidoscope1-elastic"))

checks = [
    ("face_search",        {"term": {"postId": 17}}),
    ("media_search",       {"term": {"mediaId": 17}}),
    ("post_search",        {"term": {"postId": 17}}),
    ("recommendations_knn",{"term": {"mediaId": 17}}),
    ("feed_personalized",  {"term": {"mediaId": 17}}),
]
for idx, q in checks:
    r = es.count(index=idx, body={"query": q})
    print(f"  {idx}: {r['count']} doc(s)")
