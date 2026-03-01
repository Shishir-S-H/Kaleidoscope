#!/usr/bin/env python3
"""
Clear all documents from Kaleidoscope Elasticsearch indices.
Keeps indices and mappings intact — only data (documents) are removed.

Usage:
  export ES_HOST="http://elastic:YOUR_PASSWORD@localhost:9200"
  python clear_es_data.py

  Or with inline env:
  ES_HOST="http://elastic:secret@localhost:9200" python clear_es_data.py
"""

import os
import sys

# Same index list as setup_es_indices.py
INDICES = [
    "media_search",
    "post_search",
    "user_search",
    "face_search",
    "recommendations_knn",
    "feed_personalized",
    "known_faces_index",
]


def main():
    try:
        from elasticsearch import Elasticsearch
        from elasticsearch.exceptions import NotFoundError
    except ImportError:
        print("Error: elasticsearch package not installed. Run: pip install elasticsearch")
        sys.exit(1)

    ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

    print("=" * 60)
    print("Kaleidoscope - Clear Elasticsearch data only")
    print("=" * 60)
    print(f"ES Host: {ES_HOST.replace(os.getenv('ELASTICSEARCH_PASSWORD', ''), '***')}")
    print()

    try:
        es = Elasticsearch(
            [ES_HOST],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=60,
        )
        if not es.ping():
            print("ERROR: Cannot connect to Elasticsearch.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Connection failed: {e}")
        sys.exit(1)

    total_deleted = 0
    for index_name in INDICES:
        try:
            if not es.indices.exists(index=index_name):
                print(f"[SKIP] {index_name} (index does not exist)")
                continue
            result = es.delete_by_query(
                index=index_name,
                body={"query": {"match_all": {}}},
                refresh=True,
                wait_for_completion=True,
            )
            deleted = result.get("deleted", 0)
            total_deleted += deleted
            print(f"[OK] {index_name} — deleted {deleted} documents")
        except NotFoundError:
            print(f"[SKIP] {index_name} (not found)")
        except Exception as e:
            print(f"[ERROR] {index_name}: {e}")

    print()
    print(f"Done. Total documents removed: {total_deleted}")
    print("Indices and mappings are unchanged.")


if __name__ == "__main__":
    main()
