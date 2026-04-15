#!/usr/bin/env python3
"""Verify a post by title: PostgreSQL read models + Elasticsearch. Run on server with ~/Kaleidoscope/.env."""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor


def load_env(path: Path) -> None:
    if not path.is_file():
        print(f"Missing {path}", file=sys.stderr)
        sys.exit(1)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def jdbc_to_conn_params(jdbc: str):
    if not jdbc.startswith("jdbc:postgresql://"):
        raise ValueError("Expected jdbc:postgresql:// URL")
    rest = jdbc[len("jdbc:postgresql://") :]
    host_port, _, path_query = rest.partition("/")
    if ":" in host_port:
        host, port_s = host_port.rsplit(":", 1)
        port = int(port_s)
    else:
        host, port = host_port, 5432
    dbname, _, query = path_query.partition("?")
    opts = {}
    if query:
        for pair in query.split("&"):
            if "=" in pair:
                a, b = pair.split("=", 1)
                opts[a] = b
    sslmode = opts.get("sslmode", "prefer")
    return {
        "host": host,
        "port": port,
        "dbname": dbname.split("?")[0],
        "user": os.environ["DB_USERNAME"],
        "password": os.environ["DB_PASSWORD"],
        "sslmode": sslmode,
    }


def es_req(es_pw: str, path: str, body: dict | None = None):
    import base64
    import urllib.request

    auth = base64.b64encode(f"elastic:{es_pw}".encode()).decode()
    url = f"http://127.0.0.1:9200{path}"
    headers = {"Authorization": f"Basic {auth}"}
    if body is None:
        req = urllib.request.Request(url, headers=headers, method="GET")
    else:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def dump_query(cur, label: str, sql: str, args=None):
    try:
        cur.execute(sql, args or ())
        rows = cur.fetchall()
    except Exception as exc:
        print(f"--- {label} (ERROR) ---\n{exc}\n")
        return
    print(f"--- {label} ({len(rows)} rows) ---")
    print(json.dumps([dict(r) for r in rows], indent=2, default=str))
    print()


def main():
    title_needle = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("POST_TITLE", "Test-2")).strip()
    load_env(Path.home() / "Kaleidoscope" / ".env")
    jdbc = os.environ.get("SPRING_DATASOURCE_URL", "")
    es_pw = os.environ.get("ELASTICSEARCH_PASSWORD", "")
    params = jdbc_to_conn_params(jdbc)

    print(f"=== PostgreSQL: posts WHERE title ILIKE % {title_needle} % ===\n")
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT post_id, user_id, title, body, visibility, status, created_at, updated_at
        FROM posts
        WHERE title ILIKE %s
        ORDER BY post_id DESC
        LIMIT 20
        """,
        (f"%{title_needle}%",),
    )
    posts = cur.fetchall()
    if not posts:
        cur.execute(
            "SELECT post_id, user_id, title, body, created_at FROM posts ORDER BY post_id DESC LIMIT 8"
        )
        recent = cur.fetchall()
        print(f"(No post matching {title_needle!r}; recent posts:)\n")
        print(json.dumps([dict(r) for r in recent], indent=2, default=str))
        cur.close()
        conn.close()
        return

    print(json.dumps([dict(r) for r in posts], indent=2, default=str))

    pid = posts[0]["post_id"]
    print(f"\n=== Using post_id={pid} for related rows ===\n")

    mid_sub = "(SELECT media_id FROM post_media WHERE post_id = %s)"

    dump_query(
        cur,
        "post_media",
        "SELECT * FROM post_media WHERE post_id = %s ORDER BY media_id",
        (pid,),
    )
    dump_query(
        cur,
        "media_ai_insights",
        """SELECT media_id, post_id, status, is_safe,
                  LEFT(caption, 200) AS caption_preview,
                  tags, scenes, updated_at
           FROM media_ai_insights WHERE post_id = %s ORDER BY media_id""",
        (pid,),
    )
    dump_query(
        cur,
        "media_detected_faces",
        f"""SELECT id, media_id, bbox, identified_user_id, suggested_user_id,
                  confidence_score, status
           FROM media_detected_faces WHERE media_id IN {mid_sub} ORDER BY id""",
        (pid,),
    )
    dump_query(
        cur,
        "read_model_media_search",
        """SELECT media_id, post_id, media_url, post_title,
                  LEFT(ai_caption, 120) AS ai_caption_preview,
                  ai_tags, ai_scenes, is_safe, updated_at
           FROM read_model_media_search WHERE post_id = %s ORDER BY media_id""",
        (pid,),
    )
    dump_query(
        cur,
        "read_model_recommendations_knn",
        f"""SELECT media_id, LEFT(caption, 80) AS cap, is_safe, created_at
           FROM read_model_recommendations_knn
           WHERE media_id IN {mid_sub}""",
        (pid,),
    )
    dump_query(
        cur,
        "read_model_feed_personalized",
        f"SELECT * FROM read_model_feed_personalized WHERE media_id IN {mid_sub}",
        (pid,),
    )
    dump_query(
        cur,
        "read_model_post_search",
        "SELECT * FROM read_model_post_search WHERE post_id = %s",
        (pid,),
    )
    dump_query(
        cur,
        "post_categories (+ category name)",
        """
        SELECT pc.post_category_id, pc.post_id, pc.category_id, pc.is_primary, c.name AS category_name
        FROM post_categories pc
        LEFT JOIN categories c ON c.category_id = pc.category_id
        WHERE pc.post_id = %s
        """,
        (pid,),
    )
    dump_query(
        cur,
        "read_model_face_search",
        """SELECT face_id, media_id, post_id, identified_user_id,
                  identified_username, match_confidence, post_title, created_at
           FROM read_model_face_search WHERE post_id = %s ORDER BY face_id""",
        (pid,),
    )

    cur.execute("SELECT media_id FROM post_media WHERE post_id = %s", (pid,))
    mids = [r["media_id"] for r in cur.fetchall()]
    cur.close()
    conn.close()

    if not es_pw:
        print("=== Elasticsearch skipped (no ELASTICSEARCH_PASSWORD) ===\n")
        print("POST_ID", pid, "MEDIA_IDS", mids)
        return

    print("=== Elasticsearch: post_search (title) ===\n")
    try:
        r = es_req(
            es_pw,
            "/post_search/_search",
            {
                "size": 5,
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"title": title_needle}},
                            {"term": {"title.keyword": title_needle}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            },
        )
        print(json.dumps(r, indent=2)[:12000])
    except Exception as e:
        print(f"post_search error: {e}")

    print("\n=== Elasticsearch: media_search (post_title or post_id) ===\n")
    try:
        r2 = es_req(
            es_pw,
            "/media_search/_search",
            {
                "size": 10,
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"post_title": title_needle}},
                            {"term": {"post_id": int(pid)}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
            },
        )
        print(json.dumps(r2, indent=2)[:12000])
    except Exception as e:
        print(f"media_search error: {e}")

    for mid in mids:
        print(f"\n=== Elasticsearch: recommendations_knn _doc/{mid} ===\n")
        try:
            r3 = es_req(es_pw, f"/recommendations_knn/_doc/{mid}", None)
            print(json.dumps(r3, indent=2)[:8000])
        except Exception as e:
            print(f"recommendations_knn: {e}")

    print("\n=== Summary keys ===")
    print(json.dumps({"post_id": pid, "media_ids": mids, "title": title_needle}))


if __name__ == "__main__":
    main()
