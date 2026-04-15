#!/usr/bin/env python3
"""Smoke-test all six Google Cloud AI providers for Kaleidoscope.

Run from inside the container or locally (with env vars loaded):

    python scripts/deployment/verify_google_apis.py

Exit code 0 means all providers passed; non-zero means at least one failed.
Prints a human-readable summary followed by a JSON result block.

Required environment variables:
  GOOGLE_CLOUD_PROJECT          GCP project ID
  GOOGLE_CLOUD_REGION           GCP region (default: us-central1)
  GOOGLE_CREDENTIALS_BASE64     Base64 service-account key (DigitalOcean)
                                OR rely on system ADC (local dev)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Minimal 1×1 PNG used as the test image (no Pillow dependency required)
# ---------------------------------------------------------------------------
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_WIDTH = 64


def _hr(char: str = "-") -> str:
    return char * _WIDTH


def _status_line(name: str, status: str, detail: str = "") -> str:
    pad = _WIDTH - len(name) - len(status) - 4
    line = f"  {name} {'.' * max(pad, 1)} {status}"
    if detail:
        line += f"\n      {detail}"
    return line


def _probe_image_bytes() -> bytes:
    """Return a small JPEG if Pillow is available, else fall back to 1×1 PNG."""
    try:
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color=(90, 120, 200)).save(buf, "JPEG", quality=85)
        return buf.getvalue()
    except ImportError:
        return _TINY_PNG


def _bootstrap() -> None:
    """Set up Google credentials before importing any SDK."""
    # Ensure the shared utils path is importable when running from repo root
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from shared.utils.google_auth import setup_google_credentials
        setup_google_credentials()
    except Exception as exc:
        print(f"  [WARN] google_auth bootstrap failed: {exc}")


# ---------------------------------------------------------------------------
# Individual provider checks
# ---------------------------------------------------------------------------

def check_moderation(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.moderation import GoogleModerationProvider
    provider = GoogleModerationProvider()
    result = provider.analyze(image_bytes)
    return {
        "is_safe": result.is_safe,
        "top_label": result.top_label,
        "confidence": result.confidence,
        "scores_keys": list(result.scores.keys()),
    }


def check_face(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.face import GoogleFaceProvider
    provider = GoogleFaceProvider()
    result = provider.detect(image_bytes)
    return {
        "faces_detected": result.faces_detected,
        "embedding_present": any(len(f.embedding) > 0 for f in result.faces),
    }


def check_captioning(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.captioning import GoogleCaptioningProvider
    provider = GoogleCaptioningProvider()
    result = provider.caption(image_bytes)
    return {"caption_length": len(result.caption), "caption_preview": result.caption[:100]}


def check_tagging(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.tagger import GoogleTaggerProvider
    provider = GoogleTaggerProvider()
    result = provider.tag(image_bytes, top_n=5)
    return {"tags": result.tags, "scores": result.scores}


def check_scene(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.scene import GoogleSceneProvider
    provider = GoogleSceneProvider()
    result = provider.recognize(image_bytes)
    return {
        "scene": result.scene,
        "confidence": result.confidence,
        "scores_count": len(result.scores),
    }


def check_embedding(image_bytes: bytes) -> dict[str, Any]:
    from shared.providers.google.embedding import GoogleEmbeddingProvider, EXPECTED_DIMS
    provider = GoogleEmbeddingProvider()
    result = provider.embed(image_bytes)
    dims_ok = result.dimensions == EXPECTED_DIMS
    return {
        "dimensions": result.dimensions,
        "expected_dims": EXPECTED_DIMS,
        "dims_match": dims_ok,
        "first_3_values": result.embedding[:3],
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    ("moderation   (Vision Safe Search)",   check_moderation),
    ("face         (Vision Face Detection)", check_face),
    ("captioning   (Gemini 1.5 Flash)",      check_captioning),
    ("tagging      (Gemini 1.5 Flash)",      check_tagging),
    ("scene        (Gemini 1.5 Flash)",      check_scene),
    ("embedding    (Vertex AI Multimodal)",  check_embedding),
]


def main() -> int:
    print(_hr("="))
    print("  Kaleidoscope — Google Cloud Provider Verification")
    print(_hr("="))

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID", "")
    region = os.getenv("GOOGLE_CLOUD_REGION") or os.getenv("GOOGLE_LOCATION", "us-central1")
    has_creds_b64 = bool(os.getenv("GOOGLE_CREDENTIALS_BASE64", "").strip())

    print(f"  Project : {project or '(not set — using ADC)'}")
    print(f"  Region  : {region}")
    print(f"  Creds   : {'GOOGLE_CREDENTIALS_BASE64 set' if has_creds_b64 else 'system ADC'}")
    print(_hr())

    if not project:
        print("  ERROR: GOOGLE_CLOUD_PROJECT / GOOGLE_PROJECT_ID is not set.")
        return 1

    _bootstrap()
    image_bytes = _probe_image_bytes()

    results: dict[str, Any] = {}
    failed = 0

    for label, fn in CHECKS:
        try:
            detail = fn(image_bytes)
            status = PASS
            error = None
        except Exception as exc:
            detail = {}
            error = repr(exc)[:300]
            status = FAIL
            failed += 1

        results[label.strip()] = {"status": status, "detail": detail, "error": error}
        extra = error or ""
        print(_status_line(label, status, extra))

    print(_hr())
    total = len(CHECKS)
    passed = total - failed
    print(f"  Result: {passed}/{total} passed  |  {failed} failed")
    print(_hr("="))

    print("\n--- JSON ---")
    print(json.dumps(results, indent=2))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
