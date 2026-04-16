"""Inspect actual ES document fields for post_id=17."""
from elasticsearch import Elasticsearch

ES_URL = "http://elasticsearch:9200"
ES_USER = "elastic"
ES_PASS = "kaleidoscope1-elastic"

es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASS))

for idx in ['media_search', 'post_search', 'face_search']:
    print(f"\n=== [{idx}] ===")
    try:
        # Get the document directly
        if idx == 'post_search':
            res = es.search(index=idx, body={"query": {"term": {"postId": 17}}, "size": 1})
        elif idx == 'face_search':
            res = es.search(index=idx, body={"query": {"term": {"postId": 17}}, "size": 1})
        else:
            res = es.search(index=idx, body={"query": {"term": {"mediaId": 17}}, "size": 1})
        
        hits = res['hits']['hits']
        if hits:
            src = hits[0]['_source']
            print(f"  _id={hits[0]['_id']}")
            for k, v in src.items():
                if isinstance(v, list) and len(v) > 5:
                    print(f"  {k}: [{len(v)} items] first3={v[:3]}")
                elif isinstance(v, (list, str)) and len(str(v)) > 120:
                    print(f"  {k}: {str(v)[:120]}...")
                else:
                    print(f"  {k}: {v}")
        else:
            print("  (no docs found)")
    except Exception as e:
        print(f"  ERROR: {e}")
