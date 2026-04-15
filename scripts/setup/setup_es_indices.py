#!/usr/bin/env python3
"""
Elasticsearch Index Setup Script
Creates all 7 indices for Kaleidoscope AI with proper mappings and settings.

Usage:
  python setup_es_indices.py                 # create missing indices only
  python setup_es_indices.py --recreate      # delete mapped + *_v2 indices, then create
  python setup_es_indices.py --wipe-cluster  # delete ALL non-system indices, upsert ILM,
                                               then create mapped indices (full reset)

Environment:
  ES_HOST  e.g. http://localhost:9200  or  http://elastic:PASSWORD@host:9200
  KALEIDOSCOPE_ILM_POLICY_NAME  (optional, default: kaleidoscope-ilm)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError, RequestError

# Configuration
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
MAPPINGS_DIR = Path(__file__).resolve().parents[2] / "es_mappings"

# Index names (each must have es_mappings/<name>.json)
INDICES = [
    "media_search",
    "post_search",
    "user_search",
    "face_search",
    "recommendations_knn",
    "feed_personalized",
    "known_faces_index",
]

# Shadow indices from earlier migration attempts — remove on --recreate
LEGACY_INDICES = [
    "media_search_v2",
    "recommendations_knn_v2",
]

# ILM policy file (optional upsert after --wipe-cluster)
ILM_POLICY_FILE = "ilm_policy.json"
DEFAULT_ILM_POLICY_NAME = "kaleidoscope-ilm"


def _redact_es_host(url: str) -> str:
    """Mask password in http(s)://user:pass@host URLs for logging."""
    try:
        p = urlsplit(url)
        if p.username or p.password:
            host = p.hostname or ""
            port = f":{p.port}" if p.port else ""
            user = p.username or ""
            netloc = f"{user}:***@{host}{port}"
            return urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))
    except Exception:
        pass
    return url


def load_mapping(index_name: str) -> dict:
    """Load mapping JSON file for an index."""
    mapping_file = MAPPINGS_DIR / f"{index_name}.json"
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")

    with open(mapping_file, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_index(es: Elasticsearch, index_name: str) -> None:
    """Drop an index if it exists."""
    try:
        es.indices.delete(index=index_name)
        print(f"[DEL] Dropped index: {index_name}")
    except NotFoundError:
        print(f"[DEL] Index '{index_name}' did not exist (skip)")


def list_non_system_index_names(es: Elasticsearch) -> list[str]:
    """Return all open index names except Elasticsearch system indices (`.` prefix)."""
    try:
        info = es.indices.get(index="*", expand_wildcards="all")
        return sorted(k for k in info.keys() if not str(k).startswith("."))
    except NotFoundError:
        return []


def wipe_all_non_system_indices(es: Elasticsearch) -> int:
    """Delete every user-visible index. Returns count deleted."""
    names = list_non_system_index_names(es)
    if not names:
        print("[WIPE] No non-system indices found (cluster already empty).")
        return 0
    print(f"[WIPE] Deleting {len(names)} non-system indices...")
    deleted = 0
    for name in names:
        try:
            es.indices.delete(index=name)
            print(f"[DEL] {name}")
            deleted += 1
        except NotFoundError:
            pass
        except Exception as exc:
            print(f"[WARN] Could not delete '{name}': {exc}")
    return deleted


def upsert_ilm_policy(es: Elasticsearch, policy_name: str) -> bool:
    """Create or replace the ILM policy from es_mappings/ilm_policy.json."""
    path = MAPPINGS_DIR / ILM_POLICY_FILE
    if not path.exists():
        print(f"[SKIP] ILM file not found: {path}")
        return True
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    try:
        # elasticsearch-py 8.x: policy= inner object with phases
        policy_inner = body.get("policy")
        if policy_inner is None:
            print("[WARN] ilm_policy.json missing top-level 'policy' key; skipping ILM.")
            return False
        es.ilm.put_lifecycle(name=policy_name, policy=policy_inner)
        print(f"[OK] ILM policy upserted: {policy_name}")
        return True
    except Exception as exc:
        print(f"[WARN] ILM policy upsert failed (non-fatal): {exc}")
        return False


def create_index(es: Elasticsearch, index_name: str, *, skip_if_exists: bool) -> bool:
    """Create a single index with its mapping (Elasticsearch 8.x API)."""
    try:
        mapping = load_mapping(index_name)

        if skip_if_exists and es.indices.exists(index=index_name):
            print(f"[SKIP] Index '{index_name}' already exists. Skipping...")
            return True

        kwargs: dict = {"index": index_name}
        if "settings" in mapping:
            kwargs["settings"] = mapping["settings"]
        if "mappings" in mapping:
            kwargs["mappings"] = mapping["mappings"]

        es.indices.create(**kwargs)
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


def main() -> None:
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="Create Kaleidoscope Elasticsearch indices from es_mappings/*.json",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete mapped indices + *_v2 shadows, then recreate from es_mappings. "
        "DESTRUCTIVE for those indices only.",
    )
    parser.add_argument(
        "--wipe-cluster",
        action="store_true",
        help="Delete ALL non-system indices (posts, users, blogs, …), upsert ILM policy, "
        "then recreate the 7 mapped indices. FULL CLUSTER DATA RESET for this node.",
    )
    parser.add_argument(
        "--no-ilm",
        action="store_true",
        help="With --wipe-cluster, skip ILM policy upsert.",
    )
    args = parser.parse_args()

    if args.recreate and args.wipe_cluster:
        print("[ERROR] Use only one of --recreate or --wipe-cluster.")
        sys.exit(2)

    es_host = os.getenv("ES_HOST", "http://localhost:9200")
    ilm_name = os.getenv("KALEIDOSCOPE_ILM_POLICY_NAME", DEFAULT_ILM_POLICY_NAME)

    if args.wipe_cluster:
        mode = "WIPE-CLUSTER (all non-system indices + ILM + mapped indices)"
    elif args.recreate:
        mode = "RECREATE (mapped indices + *_v2 only)"
    else:
        mode = "create-if-missing"

    print("=" * 60)
    print("Kaleidoscope AI - Elasticsearch Index Setup")
    print("=" * 60)
    print(f"Elasticsearch Host: {_redact_es_host(es_host)}")
    print(f"Mappings Directory: {MAPPINGS_DIR}")
    print(f"Mode: {mode}")
    print()

    try:
        es = Elasticsearch(
            [es_host],
            verify_certs=False,
            ssl_show_warn=False,
            request_timeout=120,
        )
        print(f"[INFO] Attempting to connect to {_redact_es_host(es_host)}...")
        if not es.ping():
            print(f"[ERROR] Cannot connect to Elasticsearch at {_redact_es_host(es_host)}")
            print("   Please ensure Elasticsearch is running.")
            sys.exit(1)
        print("[OK] Connected to Elasticsearch")
        print()
    except Exception as e:
        print(f"[ERROR] Error connecting to Elasticsearch: {str(e)}")
        print(f"[DEBUG] Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    force_create = False
    if args.wipe_cluster:
        print(
            "[WARN] --wipe-cluster: removing every index that does not start with '.' "
            "(Java + Python + legacy)."
        )
        wipe_all_non_system_indices(es)
        print()
        if not args.no_ilm:
            upsert_ilm_policy(es, ilm_name)
            print()
        force_create = True
    elif args.recreate:
        print("[WARN] --recreate: dropping legacy shadow indices and all mapped indices...")
        for index_name in LEGACY_INDICES:
            delete_index(es, index_name)
        for index_name in INDICES:
            delete_index(es, index_name)
        print()
        force_create = True

    success_count = 0
    failed_indices: list[str] = []

    for index_name in INDICES:
        print(f"[INFO] Processing: {index_name}")
        if create_index(es, index_name, skip_if_exists=not force_create):
            if verify_index(es, index_name):
                success_count += 1
            else:
                failed_indices.append(index_name)
        else:
            failed_indices.append(index_name)
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total indices: {len(INDICES)}")
    print(f"[OK] Successfully created / verified: {success_count}")
    print(f"[ERROR] Failed: {len(failed_indices)}")

    if failed_indices:
        print(f"\nFailed indices: {', '.join(failed_indices)}")
        sys.exit(1)

    print("\n[SUCCESS] All indices created successfully!")
    print("\n Next steps:")
    print("   1. Verify indices: curl -X GET 'localhost:9200/_cat/indices?v'")
    print("   2. Check mappings: curl -X GET 'localhost:9200/<index_name>/_mapping'")
    if force_create:
        print("   3. media_search / recommendations_knn image_embedding dims should be 1408 (Vertex AI).")
    if args.wipe_cluster:
        print(
            "   4. Restart the Spring Boot backend so it recreates Java-owned indices "
            "(posts, users, blogs, …) from PostgreSQL on the next startup sync."
        )
    sys.exit(0)


if __name__ == "__main__":
    main()

