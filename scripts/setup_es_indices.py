#!/usr/bin/env python3
"""
Elasticsearch Index Setup Script
Creates all 7 indices for Kaleidoscope AI with proper mappings and settings.
"""

import json
import os
import sys
from pathlib import Path
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError

# Configuration
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
MAPPINGS_DIR = Path(__file__).parent.parent / "es_mappings"

# Index names
INDICES = [
    "media_search",
    "post_search",
    "user_search",
    "face_search",
    "recommendations_knn",
    "feed_personalized",
    "known_faces_index"
]


def load_mapping(index_name: str) -> dict:
    """Load mapping JSON file for an index."""
    mapping_file = MAPPINGS_DIR / f"{index_name}.json"
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")
    
    with open(mapping_file, 'r') as f:
        return json.load(f)


def create_index(es: Elasticsearch, index_name: str) -> bool:
    """Create a single index with its mapping."""
    try:
        # Load mapping
        mapping = load_mapping(index_name)
        
        # Check if index already exists
        if es.indices.exists(index=index_name):
            print(f"[SKIP] Index '{index_name}' already exists. Skipping...")
            return True
        
        # Create index
        es.indices.create(index=index_name, body=mapping)
        print(f"[OK] Successfully created index: {index_name}")
        return True
        
    except RequestError as e:
        print(f"[ERROR] Error creating index '{index_name}': {e.info}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error creating index '{index_name}': {str(e)}")
        return False


def verify_index(es: Elasticsearch, index_name: str) -> bool:
    """Verify index was created successfully."""
    try:
        if not es.indices.exists(index=index_name):
            print(f"[ERROR] Verification failed: Index '{index_name}' does not exist")
            return False
        
        # Get index stats
        stats = es.indices.stats(index=index_name)
        total_docs = stats['indices'][index_name]['total']['docs']['count']
        
        print(f"   Documents: {total_docs}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error verifying index '{index_name}': {str(e)}")
        return False


def main():
    """Main setup function."""
    print("=" * 60)
    print("Kaleidoscope AI - Elasticsearch Index Setup")
    print("=" * 60)
    print(f"Elasticsearch Host: {ES_HOST}")
    print(f"Mappings Directory: {MAPPINGS_DIR}")
    print()
    
    # Connect to Elasticsearch
    try:
        es = Elasticsearch(
            [ES_HOST],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=30
        )
        print(f"[INFO] Attempting to connect to {ES_HOST}...")
        if not es.ping():
            print(f"[ERROR] Cannot connect to Elasticsearch at {ES_HOST}")
            print("   Please ensure Elasticsearch is running.")
            sys.exit(1)
        print(f"[OK] Connected to Elasticsearch")
        print()
    except Exception as e:
        print(f"[ERROR] Error connecting to Elasticsearch: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create indices
    success_count = 0
    failed_indices = []
    
    for index_name in INDICES:
        print(f"[INFO] Processing: {index_name}")
        if create_index(es, index_name):
            if verify_index(es, index_name):
                success_count += 1
            else:
                failed_indices.append(index_name)
        else:
            failed_indices.append(index_name)
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total indices: {len(INDICES)}")
    print(f"[OK] Successfully created: {success_count}")
    print(f"[ERROR] Failed: {len(failed_indices)}")
    
    if failed_indices:
        print(f"\nFailed indices: {', '.join(failed_indices)}")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All indices created successfully!")
        print("\n Next steps:")
        print("   1. Verify indices: curl -X GET 'localhost:9200/_cat/indices?v'")
        print("   2. Check mappings: curl -X GET 'localhost:9200/<index_name>/_mapping'")
        sys.exit(0)


if __name__ == "__main__":
    main()

