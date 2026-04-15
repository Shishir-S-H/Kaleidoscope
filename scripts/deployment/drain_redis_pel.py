#!/usr/bin/env python3
"""Ack all pending entries for Redis Streams consumer groups (drain PEL)."""
import os
import sys
from pathlib import Path


def load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def drain(r, stream: str, group: str) -> int:
    total = 0
    while True:
        batch = r.xpending_range(stream, group, min="-", max="+", count=1000)
        if not batch:
            break
        for msg in batch:
            mid = msg["message_id"]
            r.xack(stream, group, mid)
            total += 1
    return total


def main():
    load_env(Path.home() / "Kaleidoscope" / ".env")
    pw = os.environ.get("REDIS_PASSWORD", "")
    if not pw:
        print("REDIS_PASSWORD not set", file=sys.stderr)
        sys.exit(1)
    import redis

    r = redis.Redis(host="127.0.0.1", port=6379, password=pw, decode_responses=True)
    group = "backend-group"
    streams = [
        "ml-insights-results",
        "face-detection-results",
        "face-recognition-results",
        "post-insights-enriched",
        "user-profile-face-embedding-results",
    ]
    for stream in streams:
        try:
            info = r.xpending(stream, group)
        except redis.ResponseError as e:
            if "NOGROUP" in str(e) or "no such key" in str(e).lower():
                print(f"[skip] {stream}: {e}")
                continue
            raise
        pending_count = info["pending"] if isinstance(info, dict) else info[0]
        if pending_count == 0:
            print(f"[ok] {stream}: 0 pending")
            continue
        print(f"[drain] {stream}: {pending_count} pending — XACKing…")
        n = drain(r, stream, group)
        print(f"[ok] {stream}: XACKed {n} messages")

    print("Done.")


if __name__ == "__main__":
    main()
