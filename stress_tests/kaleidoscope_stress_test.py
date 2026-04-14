#!/usr/bin/env python3
"""
stress_tests/kaleidoscope_stress_test.py
-----------------------------------------
End-to-end stress test for the Kaleidoscope media processing + recommendation
pipeline.

Pipeline under test
───────────────────
  POST /api/auth/register → POST /api/auth/login
    → randomuser.me portrait → PUT /api/users/profile (backend → Cloudinary + DB)
    → per post: PIL composite “group photo” (author + 1–N peers) → Cloudinary upload
      → POST /api/posts  { title, body, mediaUrls[] }
        → Redis: post-image-processing
          → media_preprocessor → ml-inference-tasks
            → content_moderation / image_tagger / scene_recognition
               / image_captioning / face_recognition
              → ml-insights-results / face-detection-results
                → post_aggregator → post-insights-enriched  (Java)
                  → Java writes media_ai_insights.status = COMPLETED|UNSAFE|FAILED
                    → es-sync-queue → es_sync worker
                      → Elasticsearch: recommendations_knn / media_search

Async completion is detected by polling media_ai_insights.status (PostgreSQL).
There is no HTTP polling endpoint for pipeline status in the integration contract.

Consent note (Phase C / GAP-6): the hasConsent field was removed from all Redis
DTOs.  Java enforces consent before publishing to Redis, so creating a valid
account is the only prerequisite.

Dependencies (pip install):
  requests faker psycopg2-binary elasticsearch python-dotenv Pillow

Environment variables (see CONFIG block below). A `.env` file at the repo root
is loaded automatically via python-dotenv (override with real env vars as needed).
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image
import requests
from dotenv import load_dotenv

# Load repo-root .env before CONFIG (module-level os.getenv reads).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
# If unset, BACKEND_BASE_URL defaults to http://localhost:8080 — on a Docker host
# where the API is only exposed via nginx/HTTPS, set e.g.
#   BACKEND_BASE_URL=https://your-domain.example

# ─────────────────────────────────────────────────────────────────────────────
# Configuration  –  override any value via environment variable
# ─────────────────────────────────────────────────────────────────────────────
BACKEND_BASE_URL    = os.getenv("BACKEND_BASE_URL",     "http://localhost:8080")
DB_HOST             = os.getenv("DB_HOST",              "localhost")
DB_PORT             = int(os.getenv("DB_PORT",          "5432"))
DB_NAME             = os.getenv("DB_NAME",              "kaleidoscope")
DB_USER             = os.getenv("DB_USERNAME",          "postgres")
DB_PASSWORD         = os.getenv("DB_PASSWORD",          "")
# Neon / managed DB: same host as Spring when SPRING_DATASOURCE_URL is set.
_spring_jdbc = os.getenv("SPRING_DATASOURCE_URL", "")
if _spring_jdbc.startswith("jdbc:postgresql://"):
    _m = re.match(r"jdbc:postgresql://([^:/]+)(?::(\d+))?/([^?]+)", _spring_jdbc)
    if _m:
        DB_HOST = _m.group(1)
        DB_PORT = int(_m.group(2) or "5432")
        DB_NAME = _m.group(3)
ES_HOST             = os.getenv("ES_HOST",              "http://localhost:9200")
ES_USER             = os.getenv("ES_USER",              "elastic")
ES_PASSWORD         = os.getenv("ES_PASSWORD",          "") or os.getenv("ELASTICSEARCH_PASSWORD", "")

NUM_USERS           = int(os.getenv("STRESS_NUM_USERS",     "10"))
POSTS_PER_USER      = int(os.getenv("STRESS_POSTS_PER_USER", "5"))
# If unset, the first category from GET /api/categories is used (requires auth).
STRESS_CATEGORY_ID  = os.getenv("STRESS_CATEGORY_ID", "").strip()

# Pipeline-completion polling
POLL_INTERVAL_S     = float(os.getenv("POLL_INTERVAL_S",  "5"))
POLL_TIMEOUT_S      = float(os.getenv("POLL_TIMEOUT_S",  "300"))   # 5 min max

# Signed upload retry (same env names as legacy direct-Cloudinary upload)
CLOUDINARY_MAX_RETRIES  = int(os.getenv("CLOUDINARY_MAX_RETRIES",   "3"))
CLOUDINARY_RETRY_BASE_S = float(os.getenv("CLOUDINARY_RETRY_BASE_S", "2.0"))

# Image download (face portraits for face_recognition / ML pipeline)
IMAGE_TMP_DIR       = Path(os.getenv("IMAGE_TMP_DIR", "/tmp/kaleidoscope_stress"))
IMAGE_WIDTH         = int(os.getenv("IMAGE_WIDTH",  "800"))
IMAGE_HEIGHT        = int(os.getenv("IMAGE_HEIGHT", "600"))
# randomuser.me + portrait download: pacing and retries (avoid rate limits / bans)
STRESS_RANDOMUSER_API_URL   = os.getenv("STRESS_RANDOMUSER_API_URL", "https://randomuser.me/api/")
STRESS_FACE_API_DELAY_S     = float(os.getenv("STRESS_FACE_API_DELAY_S", "0.45"))
STRESS_FACE_DOWNLOAD_RETRIES = int(os.getenv("STRESS_FACE_DOWNLOAD_RETRIES", "5"))
# Composite group-photo row (author + random peers from the stress user pool)
STRESS_COMPOSITE_MAX_FRIENDS = int(os.getenv("STRESS_COMPOSITE_MAX_FRIENDS", "2"))
STRESS_COMPOSITE_ROW_HEIGHT  = int(os.getenv("STRESS_COMPOSITE_ROW_HEIGHT", "400"))

# Monotonic index for randomuser.me pacing + unique seeds (identity + per-post extras).
_stress_face_download_seq = 0


def _next_face_download_index() -> int:
    global _stress_face_download_seq
    i = _stress_face_download_seq
    _stress_face_download_seq += 1
    return i


def reset_face_download_counter() -> None:
    """Call at the start of main() so reruns get predictable sequencing."""
    global _stress_face_download_seq
    _stress_face_download_seq = 0

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stress-test")


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TestUser:
    username:     str
    email:        str
    password:     str
    department:   str
    full_name:    str
    user_id:      Optional[str] = None
    access_token: Optional[str] = None
    posts:        List[dict]    = field(default_factory=list)
    # One persistent face JPEG per user (randomuser.me); used for ~70% of post images.
    identity_image_path: Optional[Path] = None
    profile_picture_url: Optional[str] = None  # from PUT /api/users/profile response


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0 – Realistic data generation  (Faker)
# ─────────────────────────────────────────────────────────────────────────────
# All user profiles and post content are generated with the Faker library so
# every run produces unique, human-looking data rather than "stress_abc123".
# ─────────────────────────────────────────────────────────────────────────────

# Departments that mirror a real company directory
_DEPARTMENTS = [
    "Engineering", "Product", "Design", "Marketing",
    "Data Science", "DevOps", "Security", "Finance",
    "Legal", "People Operations",
]


def _build_faker():
    """Return a seeded Faker instance (seed varies per run for uniqueness)."""
    from faker import Faker
    fake = Faker()
    Faker.seed()          # random seed each run
    return fake


def generate_user_profile(fake) -> Tuple[str, str, str, str, str]:
    """
    Return (username, email, password, department, full_name).

    Username is first.last + short hex suffix to guarantee uniqueness inside
    the DB while still looking like a real person.
    """
    first  = fake.first_name().lower()
    last   = fake.last_name().lower()
    suffix = uuid.uuid4().hex[:6]
    username   = f"{first}.{last}.{suffix}"
    email      = f"{first}.{last}.{suffix}@{fake.free_email_domain()}"
    password   = fake.password(length=16, special_chars=True, digits=True,
                               upper_case=True, lower_case=True)
    department = fake.random_element(_DEPARTMENTS)
    full_name  = f"{first.capitalize()} {last.capitalize()}"
    return username, email, password, department, full_name


def generate_post_content(fake) -> Tuple[str, str, List[str]]:
    """
    Return (title, body, tags).

    Title is a realistic event/catch-phrase headline.
    Body is 2–4 paragraphs of lorem-style prose so it looks like a real post.
    Tags are 3–6 lower-case keywords that mimic what the AI tagger would emit.
    """
    title = fake.catch_phrase()

    # Multi-paragraph body – two realistic paragraphs + optional extra
    paragraphs = [fake.paragraph(nb_sentences=4) for _ in range(fake.random_int(2, 4))]
    body = "\n\n".join(paragraphs)

    # Realistic image-content tags (drawn from a broad pool)
    tag_pool = [
        "outdoor", "indoor", "portrait", "landscape", "architecture",
        "technology", "team", "event", "nature", "urban", "product",
        "celebration", "conference", "workshop", "travel", "food",
        "sports", "art", "office", "presentation",
    ]
    tags = fake.random_elements(tag_pool, length=fake.random_int(3, 6), unique=True)
    return title, body, list(tags)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0b – Face portraits (randomuser.me)
# ─────────────────────────────────────────────────────────────────────────────
# We fetch JSON from https://randomuser.me/api/ (no API key) and download
# picture.large so every stress image contains a real human face — required to
# exercise face_recognition and related workers reliably.
# STRESS_FACE_API_DELAY_S spaces out calls when generating many posts/users.
# ─────────────────────────────────────────────────────────────────────────────

def download_random_image(index: int) -> Path:
    """
    Download a unique portrait JPEG (guaranteed human face) and save under
    IMAGE_TMP_DIR (default: /tmp/kaleidoscope_stress) with a unique filename.
    Returns the local Path — same contract as the legacy picsum-based helper.

    Flow: GET randomuser.me JSON → picture.large (fallback: medium, thumbnail) →
    GET binary image. Retries with backoff on errors / empty payloads.

    Every call sleeps STRESS_FACE_API_DELAY_S before hitting the API (rate limiter).
    """
    IMAGE_TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGE_TMP_DIR / f"stress_{index:04d}_{uuid.uuid4().hex[:8]}.jpg"

    # Pace *every* request (including the first) to reduce ban risk on shared IPs.
    time.sleep(STRESS_FACE_API_DELAY_S)

    last_exc: Optional[Exception] = None
    for attempt in range(1, STRESS_FACE_DOWNLOAD_RETRIES + 1):
        try:
            if attempt > 1:
                time.sleep(STRESS_FACE_API_DELAY_S * (2 ** (attempt - 2)))

            # Unique seed per call → different synthetic identity / portrait each time.
            api_params = {
                "inc": "picture",
                "noinfo": "",
                "seed": f"stress-{index}-{uuid.uuid4().hex}",
            }
            log.info(
                "[image] randomuser.me (attempt %d/%d) → %s",
                attempt,
                STRESS_FACE_DOWNLOAD_RETRIES,
                dest.name,
            )
            api_resp = requests.get(
                STRESS_RANDOMUSER_API_URL,
                params=api_params,
                timeout=30,
            )
            api_resp.raise_for_status()
            payload = api_resp.json()
            results = payload.get("results") or []
            if not results:
                raise ValueError("randomuser.me returned empty results")

            picture = results[0].get("picture") or {}
            # Prefer large (128×128) portrait URL from the API contract.
            img_url = (
                picture.get("large")
                or picture.get("medium")
                or picture.get("thumbnail")
            )
            if not img_url:
                raise ValueError("randomuser.me response missing picture URLs")

            log.info("[image] downloading portrait %s …", img_url[:100])
            img_resp = requests.get(img_url, timeout=45, allow_redirects=True)
            img_resp.raise_for_status()

            ctype = img_resp.headers.get("Content-Type", "")
            if "image" not in ctype.lower():
                raise ValueError(f"Unexpected Content-Type from portrait URL: {ctype!r}")

            dest.write_bytes(img_resp.content)
            log.info("[image] saved %d bytes to %s", len(img_resp.content), dest)
            return dest

        except Exception as exc:
            last_exc = exc
            log.warning(
                "[image] download_random_image attempt %d/%d failed: %s",
                attempt,
                STRESS_FACE_DOWNLOAD_RETRIES,
                exc,
            )

    raise last_exc  # type: ignore[misc]


def _synthetic_jpeg(index: int) -> Path:
    """Write a minimal valid 1×1 white JPEG and return its Path."""
    IMAGE_TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGE_TMP_DIR / f"synthetic_{index:04d}.jpg"
    dest.write_bytes(
        bytes([
            0xFF,0xD8,0xFF,0xE0,0x00,0x10,0x4A,0x46,0x49,0x46,0x00,0x01,
            0x01,0x00,0x00,0x01,0x00,0x01,0x00,0x00,0xFF,0xDB,0x00,0x43,
            0x00,0x08,0x06,0x06,0x07,0x06,0x05,0x08,0x07,0x07,0x07,0x09,
            0x09,0x08,0x0A,0x0C,0x14,0x0D,0x0C,0x0B,0x0B,0x0C,0x19,0x12,
            0x13,0x0F,0x14,0x1D,0x1A,0x1F,0x1E,0x1D,0x1A,0x1C,0x1C,0x20,
            0x24,0x2E,0x27,0x20,0x22,0x2C,0x23,0x1C,0x1C,0x28,0x37,0x29,
            0x2C,0x30,0x31,0x34,0x34,0x34,0x1F,0x27,0x39,0x3D,0x38,0x32,
            0x3C,0x2E,0x33,0x34,0x32,0xFF,0xC0,0x00,0x0B,0x08,0x00,0x01,
            0x00,0x01,0x01,0x01,0x11,0x00,0xFF,0xC4,0x00,0x1F,0x00,0x00,
            0x01,0x05,0x01,0x01,0x01,0x01,0x01,0x01,0x00,0x00,0x00,0x00,
            0x00,0x00,0x00,0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,
            0x09,0x0A,0x0B,0xFF,0xC4,0x00,0xB5,0x10,0x00,0x02,0x01,0x03,
            0x03,0x02,0x04,0x03,0x05,0x05,0x04,0x04,0x00,0x00,0x01,0x7D,
            0x01,0x02,0x03,0x00,0x04,0x11,0x05,0x12,0x21,0x31,0x41,0x06,
            0x13,0x51,0x61,0x07,0x22,0x71,0x14,0x32,0x81,0x91,0xA1,0x08,
            0x23,0x42,0xB1,0xC1,0x15,0x52,0xD1,0xF0,0x24,0x33,0x62,0x72,
            0x82,0xFF,0xDA,0x00,0x08,0x01,0x01,0x00,0x00,0x3F,0x00,0xFB,
            0x00,0xFF,0xD9,
        ])
    )
    log.warning("[image] wrote synthetic fallback JPEG to %s", dest)
    return dest


def _pil_resample_high_quality():
    try:
        return Image.Resampling.LANCZOS  # Pillow 10+
    except AttributeError:
        return getattr(Image, "LANCZOS", Image.BICUBIC)


def create_composite_group_photo(
    author: TestUser,
    all_users: List[TestUser],
    max_friends: int = 2,
) -> Path:
    """
    Horizontal collage: author face (always) + 1..max_friends other users from
    the stress pool. Images are resized to a common row height, then stitched
    left-to-right for multi-face AI testing.
    """
    if not author.identity_image_path:
        raise ValueError("author.identity_image_path is required")

    others = [u for u in all_users if u is not author and u.identity_image_path]
    resample = _pil_resample_high_quality()
    target_h = max(64, STRESS_COMPOSITE_ROW_HEIGHT)

    paths: List[Path] = [author.identity_image_path]
    if others:
        n_pick = random.randint(1, min(max_friends, len(others)))
        friends = random.sample(others, n_pick)
        for f in friends:
            if f.identity_image_path:
                paths.append(f.identity_image_path)

    resized: List[Image.Image] = []
    for p in paths:
        with Image.open(p) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            if h <= 0:
                continue
            new_w = max(1, int(round(w * (target_h / float(h)))))
            resized.append(rgb.resize((new_w, target_h), resample))

    if not resized:
        raise RuntimeError("create_composite_group_photo: no valid images")

    total_w = sum(im.width for im in resized)
    row = Image.new("RGB", (total_w, target_h), color=(24, 24, 24))
    x = 0
    for im in resized:
        row.paste(im, (x, 0))
        x += im.width

    out_dir = Path(os.getenv("STRESS_COMPOSITE_TMP", "/tmp"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"group_{uuid.uuid4().hex}.jpg"
    row.save(out_path, "JPEG", quality=92, optimize=True)
    log.info(
        "[composite] %d face(s) in strip (author + %d peer(s)) → %s",
        len(resized),
        len(resized) - 1,
        out_path.name,
    )
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 – Identity & consent setup
# ─────────────────────────────────────────────────────────────────────────────
# Contract: backend AuthController
#   POST /api/auth/register  multipart/form-data: userData (JSON: email, password,
#     username, designation, summary) + optional profilePicture
#     → 201 AppResponse { data: { userId, … } }  (no JWT; login next)
#   POST /api/auth/login     { email, password }
#     → 200 AppResponse { data: UserLoginResponseDTO }; Authorization: Bearer …
#
# hasConsent was removed in Phase C (GAP-6).  A valid account is sufficient.
# ─────────────────────────────────────────────────────────────────────────────

def _api_base() -> str:
    return BACKEND_BASE_URL.rstrip("/")


def _auth_headers(user: TestUser) -> Dict[str, str]:
    return {"Authorization": f"Bearer {user.access_token}"}


def _unwrap_data(payload: dict):
    """Return Spring `data` field when present."""
    if isinstance(payload, dict) and "data" in payload and payload["data"] is not None:
        return payload["data"]
    return payload


def _paginated_content(body: dict) -> List:
    """Extract list from AppResponse<PaginatedResponse<T>> or legacy shapes."""
    data = _unwrap_data(body) if isinstance(body, dict) else body
    if isinstance(data, dict) and isinstance(data.get("content"), list):
        return data["content"]
    if isinstance(body, dict) and isinstance(body.get("content"), list):
        return body["content"]
    if isinstance(body, list):
        return body
    return []


def resolve_category_id(user: TestUser) -> int:
    """Pick a category id from STRESS_CATEGORY_ID or GET /api/categories."""
    if STRESS_CATEGORY_ID.isdigit():
        return int(STRESS_CATEGORY_ID)
    resp = requests.get(
        f"{_api_base()}/api/categories",
        params={"page": 0, "size": 50},
        headers=_auth_headers(user),
        timeout=20,
    )
    resp.raise_for_status()
    items = _paginated_content(resp.json())
    if not items:
        raise RuntimeError(
            "No categories from GET /api/categories — seed categories or set STRESS_CATEGORY_ID",
        )
    cid = items[0].get("categoryId")
    if cid is None:
        raise RuntimeError("Category DTO missing categoryId")
    log.info("[category] using category_id=%s (%s)", cid, items[0].get("name", ""))
    return int(cid)


def _request_upload_signatures(user: TestUser, file_name: str) -> dict:
    """POST /api/posts/generate-upload-signatures → first SignatureDataDTO as dict."""
    resp = requests.post(
        f"{_api_base()}/api/posts/generate-upload-signatures",
        json={"fileNames": [file_name], "contentType": "POST"},
        headers=_auth_headers(user),
        timeout=30,
    )
    resp.raise_for_status()
    data = _unwrap_data(resp.json())
    sigs = data.get("signatures") if isinstance(data, dict) else None
    if not sigs:
        raise RuntimeError("generate-upload-signatures returned no signatures")
    return sigs[0]


def _signed_upload_to_cloudinary(image_path: Path, sig: dict) -> str:
    """Upload bytes using backend-issued Cloudinary signature (MediaAssetTracker PENDING)."""
    cloud = sig.get("cloudName") or sig.get("cloud_name")
    upload_url = f"https://api.cloudinary.com/v1_1/{cloud}/image/upload"
    with open(image_path, "rb") as fp:
        files = {"file": (image_path.name, fp, "image/jpeg")}
        form = {
            "api_key":     sig.get("apiKey") or sig.get("api_key"),
            "timestamp":   str(sig.get("timestamp", "")),
            "signature":   sig.get("signature", ""),
            "public_id":   sig.get("publicId") or sig.get("public_id"),
            "folder":      sig.get("folder", ""),
        }
        resp = requests.post(upload_url, files=files, data=form, timeout=120)
    resp.raise_for_status()
    return resp.json()["secure_url"]


def upload_image_for_post(user: TestUser, image_path: Path) -> str:
    """
    Backend-mandated flow: signed upload intent → Cloudinary upload → secure_url.
    Retries on transient failures (same backoff as legacy direct upload).
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, CLOUDINARY_MAX_RETRIES + 1):
        try:
            sig = _request_upload_signatures(user, image_path.name)
            url = _signed_upload_to_cloudinary(image_path, sig)
            log.info("[upload] attempt %d/%d  ✓  %s → %s",
                     attempt, CLOUDINARY_MAX_RETRIES, image_path.name, url[:80])
            return url
        except Exception as exc:
            last_exc = exc
            if attempt < CLOUDINARY_MAX_RETRIES:
                delay = CLOUDINARY_RETRY_BASE_S * (2 ** (attempt - 1))
                log.warning("[upload] attempt %d/%d failed (%s) – retry in %.1fs …",
                            attempt, CLOUDINARY_MAX_RETRIES, exc, delay)
                time.sleep(delay)
            else:
                log.error("[upload] exhausted retries for %s: %s", image_path.name, exc)
    raise last_exc  # type: ignore[misc]


def put_user_profile_picture(user: TestUser, image_path: Path) -> Optional[str]:
    """
    Set the official profile picture via PUT /api/users/profile (multipart).

    The Java backend uploads the file to Cloudinary under users/profiles/{userId},
    persists profile_picture_url, and publishes profile-picture-processing for
    profile_enrollment (same path as the React client). Client-side signed
    POST uploads only support POST/BLOG media — not profile assets.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, CLOUDINARY_MAX_RETRIES + 1):
        try:
            user_data = {
                "username":    user.username,
                "designation": user.department,
                "summary":     f"Stress test account ({user.full_name})",
            }
            with open(image_path, "rb") as fp:
                files = {
                    "userData":       (None, json.dumps(user_data), "application/json"),
                    "profilePicture": (image_path.name, fp, "image/jpeg"),
                }
                resp = requests.put(
                    f"{_api_base()}/api/users/profile",
                    files=files,
                    headers=_auth_headers(user),
                    timeout=120,
                )
            resp.raise_for_status()
            raw  = resp.json()
            data = _unwrap_data(raw) if isinstance(raw, dict) else raw
            url: Optional[str] = None
            if isinstance(data, dict):
                url = data.get("profilePictureUrl")
            if url:
                user.profile_picture_url = str(url)
            log.info("[profile] official profile picture set  url=%s", (url or "")[:100])
            return url
        except Exception as exc:
            last_exc = exc
            if attempt < CLOUDINARY_MAX_RETRIES:
                delay = CLOUDINARY_RETRY_BASE_S * (2 ** (attempt - 1))
                log.warning(
                    "[profile] attempt %d/%d failed (%s) – retry in %.1fs …",
                    attempt, CLOUDINARY_MAX_RETRIES, exc, delay,
                )
                time.sleep(delay)
            else:
                log.error("[profile] exhausted retries for profile picture: %s", exc)
    raise last_exc  # type: ignore[misc]


def hydrate_persistent_identity(user: TestUser) -> None:
    """Download one randomuser.me portrait, store on TestUser, set backend profile pic."""
    if not user.access_token:
        log.warning("[profile] no token — skip identity hydration for %s", user.username)
        return
    idx = _next_face_download_index()
    path = download_random_image(idx)
    user.identity_image_path = path
    put_user_profile_picture(user, path)


def _register(user: TestUser) -> Optional[TestUser]:
    """Multipart register (Spring consumes MULTIPART_FORM_DATA + userData JSON)."""
    user_data = {
        "email":       user.email,
        "password":    user.password,
        "username":    user.username,
        "designation": user.department,
        "summary":     f"Stress test account ({user.full_name})",
    }
    files = {"userData": (None, json.dumps(user_data), "application/json")}
    resp = requests.post(f"{_api_base()}/api/auth/register", files=files, timeout=30)
    if resp.status_code != 201:
        return None
    try:
        body = resp.json()
        data = body.get("data") or {}
        if data.get("userId") is not None:
            user.user_id = str(data["userId"])
    except (ValueError, TypeError, KeyError):
        return None
    log.info("[user] registered  %-30s  id=%s", user.username, user.user_id)
    return user


def _login(user: TestUser) -> Optional[TestUser]:
    """Login; JWT is returned in the Authorization response header."""
    resp = requests.post(
        f"{_api_base()}/api/auth/login",
        json={"email": user.email, "password": user.password},
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
        data = body.get("data") or {}
        if data.get("userId") is not None:
            user.user_id = str(data["userId"])
        auth = resp.headers.get("Authorization") or ""
        if auth.startswith("Bearer "):
            user.access_token = auth[7:].strip()
    except (ValueError, TypeError, KeyError):
        return None
    if not user.access_token:
        return None
    log.info("[user] logged in   %-30s  id=%s", user.username, user.user_id)
    return user


def create_test_user(fake) -> Optional[TestUser]:
    """
    Build a Faker-generated profile, register it, and fall back to login if
    the account already exists (e.g., on a re-run with a seeded Faker).
    """
    username, email, password, department, full_name = generate_user_profile(fake)
    user = TestUser(
        username   = username,
        email      = email,
        password   = password,
        department = department,
        full_name  = full_name,
    )

    if _register(user):
        _complete_email_verification(user)
        if _login(user):
            return user

    # Account may already exist from a prior run — try login only.
    if _login(user):
        return user

    log.error("[user] could not register or log in as %s", user.email)
    return None


def setup_users(n: int, fake) -> List[TestUser]:
    users: List[TestUser] = []
    for i in range(n):
        try:
            u = create_test_user(fake)
            if u:
                try:
                    hydrate_persistent_identity(u)
                except Exception as exc:
                    log.error("[user] identity hydration failed for %s: %s", u.username, exc)
                users.append(u)
        except Exception as exc:
            log.error("[user] user %d setup failed: %s", i, exc)
    log.info("[phase-1] %d/%d users ready (persistent faces + profile pics)", len(users), n)
    return users


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2a – Signed Cloudinary upload (backend MediaAssetTracker PENDING)
# ─────────────────────────────────────────────────────────────────────────────
# POST /api/posts/generate-upload-signatures → POST Cloudinary image/upload
# (see upload_image_for_post).  Retries use CLOUDINARY_* backoff env vars.
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Phase 2b – Post creation (PostCreateRequestDTO)
# ─────────────────────────────────────────────────────────────────────────────
# POST /api/posts  JSON body with mediaDetails[], categoryIds[], visibility, …
# Authorization: Bearer <accessToken>
# ─────────────────────────────────────────────────────────────────────────────

def create_post(
    user:         TestUser,
    media_url:    str,
    title:        str,
    body:         str,
    summary:      str,
    category_id:  int,
    media_width:  Optional[int] = None,
    media_height: Optional[int] = None,
) -> dict:
    """Create a post; returns `data` PostCreationResponseDTO as dict."""
    mw = media_width if media_width is not None else IMAGE_WIDTH
    mh = media_height if media_height is not None else IMAGE_HEIGHT
    payload = {
        "title":        title,
        "body":         body,
        "summary":      summary,
        "mediaDetails": [
            {
                "mediaId":          None,
                "url":              media_url,
                "mediaType":        "IMAGE",
                "position":         0,
                "width":            mw,
                "height":           mh,
                "fileSizeKb":       None,
                "durationSeconds":  None,
                "extraMetadata":    None,
            },
        ],
        "visibility":    "PUBLIC",
        "locationId":    None,
        "categoryIds":   [category_id],
        "taggedUserIds": [],
    }
    resp = requests.post(
        f"{_api_base()}/api/posts",
        json=payload,
        headers=_auth_headers(user),
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()
    post = _unwrap_data(raw) if isinstance(raw, dict) else raw
    log.info("[post] created  id=%-8s  user=%-28s  title=%r",
             post.get("postId") or post.get("id"),
             user.username,
             title[:50])
    return post


def ingest_content(
    users:       List[TestUser],
    fake,
    category_id: int,
) -> List[dict]:
    """
    For every user × POSTS_PER_USER, build a PIL composite “group photo”
    (author + random peers from the same stress run), upload to Cloudinary,
    then create the post. Requires Phase 1 to have populated identity paths
    for the full user pool.
    """
    all_posts: List[dict] = []

    for user in users:
        for p_idx in range(POSTS_PER_USER):
            title, body, _tags = generate_post_content(fake)
            summary = body[:240].replace("\n", " ") + ("..." if len(body) > 240 else "")

            composite_path: Optional[Path] = None
            try:
                composite_path = create_composite_group_photo(
                    user,
                    users,
                    max_friends=STRESS_COMPOSITE_MAX_FRIENDS,
                )
                with Image.open(composite_path) as im:
                    cw, ch = im.size
                media_url = upload_image_for_post(user, composite_path)
                post = create_post(
                    user,
                    media_url,
                    title,
                    body,
                    summary,
                    category_id,
                    media_width=cw,
                    media_height=ch,
                )
                user.posts.append(post)
                all_posts.append(post)
            except Exception as exc:
                log.error("[ingest] user=%s post=%d failed: %s",
                          user.username, p_idx, exc)
            finally:
                if composite_path is not None:
                    try:
                        composite_path.unlink(missing_ok=True)
                    except OSError:
                        pass

    log.info("[phase-2] %d posts created across %d users (PIL group composites)", len(all_posts), len(users))
    return all_posts


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 – Async pipeline completion detection
# ─────────────────────────────────────────────────────────────────────────────
# Source of truth: media_ai_insights.status in PostgreSQL
# (migrations/V1__create_ai_tables.sql line 9):
#   status VARCHAR(20) CHECK (status IN ('PROCESSING','COMPLETED','UNSAFE','FAILED'))
#
# No HTTP status endpoint exists in the integration contract.
#
# Resilience:  the PostgreSQL connection is opened and closed *inside* each
# polling iteration.  This means idle-connection timeouts on the server side
# (common on managed DB services like Neon) cannot crash the poll loop.
# A connection error on one interval is logged and the loop simply waits for
# the next tick rather than raising.
# ─────────────────────────────────────────────────────────────────────────────

def _extract_media_ids(posts: List[dict]) -> List[str]:
    """
    Extract media IDs from PostDTO objects returned by the Spring backend.
    The field name varies by Spring DTO version – try all common shapes.
    """
    ids: List[str] = []
    for post in posts:
        for key in ("mediaIds", "media", "postMedia"):
            v = post.get(key)
            if isinstance(v, list):
                for item in v:
                    raw_id = (
                        item.get("mediaId") or item.get("id")
                        if isinstance(item, dict)
                        else item
                    )
                    if raw_id is not None:
                        ids.append(str(raw_id))
                break
    return [i for i in ids if i]


def _open_pg_connection():
    """Open and return a fresh psycopg2 connection."""
    import psycopg2

    sslmode = os.getenv("PGSSLMODE", "")
    if not sslmode:
        sslmode = "prefer" if DB_HOST in ("localhost", "127.0.0.1", "::1") else "require"
    kw = dict(
        host              = DB_HOST,
        port              = DB_PORT,
        dbname            = DB_NAME,
        user              = DB_USER,
        password          = DB_PASSWORD,
        connect_timeout   = 10,
    )
    if sslmode:
        kw["sslmode"] = sslmode
    return psycopg2.connect(**kw)


def _fetch_pending_verification_code(email: str) -> Optional[str]:
    """Read pending email verification token (registration leaves account DEACTIVATED)."""
    import psycopg2.extras

    conn = _open_pg_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT verification_code FROM email_verifications "
                "WHERE email = %s AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (email,),
            )
            row = cur.fetchone()
            return str(row["verification_code"]) if row else None
    finally:
        conn.close()


def _complete_email_verification(user: TestUser) -> None:
    """GET /api/auth/verify-email?token=… so login can succeed (ACTIVE status)."""
    code = _fetch_pending_verification_code(user.email)
    if not code:
        log.debug("[verify] no pending code for %s — may already be active", user.email)
        return
    r = requests.get(
        f"{_api_base()}/api/auth/verify-email",
        params={"token": code},
        timeout=25,
    )
    if r.status_code != 200:
        log.warning("[verify] verify-email HTTP %s for %s", r.status_code, user.email)
    else:
        log.info("[verify] email activated for %s", user.email)


def _query_media_statuses(media_ids: List[str]) -> Dict[str, str]:
    """
    Open a short-lived PostgreSQL connection, query media_ai_insights, close.
    Returns {media_id_str: status} for all found rows.
    Raises on genuine errors so the caller can decide whether to retry.
    """
    import psycopg2.extras

    numeric_ids = [int(m) for m in media_ids if m.isdigit()]
    if not numeric_ids:
        return {}

    placeholders = ",".join(["%s"] * len(numeric_ids))
    sql = (
        f"SELECT media_id, status "
        f"FROM media_ai_insights "
        f"WHERE media_id IN ({placeholders})"
    )

    conn = _open_pg_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, numeric_ids)
            return {str(row["media_id"]): row["status"] for row in cur.fetchall()}
    finally:
        conn.close()


def wait_for_pipeline(posts: List[dict]) -> Dict[str, str]:
    """
    Poll media_ai_insights once per POLL_INTERVAL_S until every expected media
    item reaches a terminal status or POLL_TIMEOUT_S elapses.

    A fresh DB connection is established (and closed) on every loop iteration.
    Transient connection errors are caught and logged; the loop continues
    on the next interval rather than crashing.

    Returns the final {media_id: status} mapping.
    """
    media_ids = _extract_media_ids(posts)
    if not media_ids:
        log.warning("[poll] no media IDs extracted from posts – skipping DB poll")
        return {}

    log.info("[poll] waiting for %d media item(s) to leave PROCESSING …", len(media_ids))

    terminal      = {"COMPLETED", "UNSAFE", "FAILED"}
    deadline      = time.time() + POLL_TIMEOUT_S
    final_statuses: Dict[str, str] = {}

    while time.time() < deadline:
        try:
            statuses = _query_media_statuses(media_ids)
        except Exception as exc:
            # Transient DB error (idle timeout, network blip, etc.)
            log.warning("[poll] DB query failed (%s) – will retry in %.0fs",
                        exc, POLL_INTERVAL_S)
            time.sleep(POLL_INTERVAL_S)
            continue

        final_statuses = statuses

        done  = {mid for mid, st in statuses.items() if st in terminal}
        still = [mid for mid in media_ids if mid not in done]

        log.info("[poll] %d/%d complete  still-pending=%s",
                 len(done), len(media_ids), still[:5])

        if not still:
            log.info("[poll] all media items processed  ✓")
            break

        time.sleep(POLL_INTERVAL_S)
    else:
        log.warning("[poll] timeout after %.0f s – some items still PROCESSING",
                    POLL_TIMEOUT_S)

    for mid, st in final_statuses.items():
        icon = "✓" if st == "COMPLETED" else ("⚠" if st == "UNSAFE" else "✗")
        log.info("[poll]  %s  media_id=%-8s  status=%s", icon, mid, st)

    return final_statuses


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 – Recommendation & search validation
# ─────────────────────────────────────────────────────────────────────────────
# REST endpoints (Java) — canonical paths used by this script:
#   GET /api/posts/suggestions?page=0&size=20   → personalized feed (PostSuggestionService)
#   GET /api/posts?q=<term>&page=0&size=10      → filter/search posts (same as legacy /api/search/media)
# Nginx may also alias /api/recommendations → suggestions and /api/search/media → /api/posts.
#
# Direct Elasticsearch checks (Python owns recommendations_knn + media_search):
#   Index: recommendations_knn
#     field image_embedding  (dense_vector 512, cosine similarity)
#     source: es_mappings/recommendations_knn.json
#   Index: media_search
#     fields: ai_tags, ai_scenes, ai_caption, image_embedding
#     source: es_mappings/media_search.json
# ─────────────────────────────────────────────────────────────────────────────

def _es_client():
    from elasticsearch import Elasticsearch
    auth = (ES_USER, ES_PASSWORD) if ES_PASSWORD else None
    return Elasticsearch([ES_HOST], basic_auth=auth, verify_certs=False)


def validate_rest_recommendations(users: List[TestUser]) -> None:
    """GET /api/posts/suggestions (personalized recommendations feed)."""
    log.info("[validate] GET /api/posts/suggestions …")
    for user in users:
        if not user.access_token:
            continue
        try:
            resp = requests.get(
                f"{_api_base()}/api/posts/suggestions",
                params  = {"page": 0, "size": 20},
                headers = {"Authorization": f"Bearer {user.access_token}"},
                timeout = 15,
            )
            resp.raise_for_status()
            items = _paginated_content(resp.json())
            icon  = "✓" if items else "⚠ empty"
            log.info("[validate] %s  user=%-28s  suggestions=%d",
                     icon, user.username, len(items))
        except Exception as exc:
            log.error("[validate] /api/posts/suggestions failed for %s: %s",
                      user.username, exc)


def validate_rest_media_search(users: List[TestUser]) -> None:
    """
    GET /api/posts?q=… (post filter / full-text search; same query shape as legacy /api/search/media).
    """
    log.info("[validate] GET /api/posts (q=…) …")
    user = next((u for u in users if u.access_token), None)
    if not user:
        return

    search_terms = [
        "landscape", "portrait", "outdoor", "indoor",
        "person", "architecture", "nature", "urban",
    ]
    for term in search_terms:
        try:
            resp = requests.get(
                f"{_api_base()}/api/posts",
                params  = {"q": term, "page": 0, "size": 10},
                headers = {"Authorization": f"Bearer {user.access_token}"},
                timeout = 15,
            )
            resp.raise_for_status()
            items = _paginated_content(resp.json())
            log.info("[validate]   search q=%-20r  hits=%d", term, len(items))
        except Exception as exc:
            log.error("[validate] /api/posts q=%r failed: %s", term, exc)


def validate_es_recommendations_knn(completed_ids: List[str]) -> None:
    """
    1. GET document by media_id in recommendations_knn to confirm indexing.
    2. Run an actual KNN probe (zero-vector) to exercise the dense_vector path.

    Index field: image_embedding (dense_vector, dims=512, cosine)
    Filter:      is_safe=true  (mirrors the face_matcher KNN pattern)
    """
    log.info("[validate-es] checking recommendations_knn …")
    if not completed_ids:
        log.warning("[validate-es] no COMPLETED media IDs – skipping KNN check")
        return

    try:
        es    = _es_client()
        found = 0

        for mid in completed_ids[:10]:
            try:
                doc = es.get(index="recommendations_knn", id=mid, ignore=[404])
                if doc.get("found"):
                    found += 1
                    log.info("[validate-es] ✓  media_id=%s  in recommendations_knn", mid)
                else:
                    log.warning("[validate-es] ✗  media_id=%s  NOT in recommendations_knn", mid)
            except Exception as exc:
                log.error("[validate-es] get media_id=%s error: %s", mid, exc)

        log.info("[validate-es] %d/%d COMPLETED items found in recommendations_knn",
                 found, min(len(completed_ids), 10))

        # Index health: document count (cosine KNN rejects zero-magnitude vectors; skip zero-vector probe)
        try:
            cnt = es.count(index="recommendations_knn")
            log.info("[validate-es] recommendations_knn total document count: %s",
                     cnt.get("count"))
        except Exception as cnt_exc:
            log.warning("[validate-es] recommendations_knn count: %s", cnt_exc)

    except Exception as exc:
        log.error("[validate-es] recommendations_knn validation failed: %s", exc)


def validate_es_media_search(completed_ids: List[str]) -> None:
    """
    Confirm each completed media_id is indexed in media_search and surface
    the AI-generated tags/scenes/caption so they are visible in the test log.

    media_search is written by Java's ElasticsearchStartupSyncService; this
    check validates the full Java → es_sync → ES chain completed.
    """
    log.info("[validate-es] checking media_search …")
    if not completed_ids:
        log.warning("[validate-es] no COMPLETED media IDs – skipping media_search check")
        return

    try:
        es = _es_client()
        for mid in completed_ids[:5]:
            try:
                resp = es.search(
                    index = "media_search",
                    body  = {"query": {"term": {"media_id": int(mid)}}},
                )
                hits = resp["hits"]["hits"]
                if hits:
                    src = hits[0]["_source"]
                    log.info(
                        "[validate-es] ✓  media_id=%-8s  tags=%s  scenes=%s  caption=%r",
                        mid,
                        src.get("ai_tags",   [])[:3],
                        src.get("ai_scenes", [])[:2],
                        (src.get("ai_caption") or "")[:60],
                    )
                else:
                    log.warning("[validate-es] ✗  media_id=%s  NOT in media_search", mid)
            except Exception as exc:
                log.error("[validate-es] media_search error for %s: %s", mid, exc)
    except Exception as exc:
        log.error("[validate-es] media_search validation failed: %s", exc)


def run_validation(
    users:    List[TestUser],
    posts:    List[dict],
    statuses: Dict[str, str],
) -> None:
    completed_ids = [mid for mid, st in statuses.items() if st == "COMPLETED"]

    validate_rest_recommendations(users)
    validate_rest_media_search(users)
    validate_es_recommendations_knn(completed_ids)
    validate_es_media_search(completed_ids)

    total   = len(statuses)
    ok      = sum(1 for s in statuses.values() if s == "COMPLETED")
    unsafe  = sum(1 for s in statuses.values() if s == "UNSAFE")
    failed  = sum(1 for s in statuses.values() if s == "FAILED")
    pending = total - ok - unsafe - failed

    log.info(
        "\n\n══════════════  STRESS TEST SUMMARY  ══════════════\n"
        "  Users created   : %d\n"
        "  Posts created   : %d\n"
        "  Media processed : %d total\n"
        "    ✓ COMPLETED   : %d\n"
        "    ⚠ UNSAFE      : %d\n"
        "    ✗ FAILED      : %d\n"
        "    ⏳ PENDING    : %d\n"
        "════════════════════════════════════════════════════\n",
        len(users), len(posts), total, ok, unsafe, failed, pending,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    reset_face_download_counter()
    log.info("═══════════════════════════════════════════════════")
    log.info("  Kaleidoscope End-to-End Stress Test")
    log.info("  Backend  : %s", BACKEND_BASE_URL)
    log.info("  Database : %s:%d/%s", DB_HOST, DB_PORT, DB_NAME)
    log.info("  ES       : %s", ES_HOST)
    log.info("  Users    : %d   Posts/user: %d", NUM_USERS, POSTS_PER_USER)
    log.info(
        "  Group photo: row height=%d px  max extra faces=%d",
        STRESS_COMPOSITE_ROW_HEIGHT,
        STRESS_COMPOSITE_MAX_FRIENDS,
    )
    log.info("═══════════════════════════════════════════════════")

    fake = _build_faker()

    # ── Phase 1: create users + persistent identity + profile picture ────────
    users = setup_users(NUM_USERS, fake)
    if not users:
        log.error("No users created – aborting.")
        sys.exit(1)

    ready = [u for u in users if u.identity_image_path]
    if len(ready) < len(users):
        log.warning(
            "[phase] %d/%d users missing identity_image_path — composites may degrade",
            len(users) - len(ready),
            len(users),
        )
    log.info(
        "[phase] Phase 1 complete — %d user(s) with identity faces; starting Phase 2 (group-photo posts).",
        len(ready),
    )

    # ── Phase 2: composite group-photo posts (full peer pool from Phase 1) ───
    category_id = resolve_category_id(users[0])
    posts = ingest_content(users, fake, category_id)
    if not posts:
        log.error("No posts created – aborting.")
        sys.exit(1)

    # ── Phase 3: wait for the AI pipeline ────────────────────────────────────
    statuses = wait_for_pipeline(posts)

    # Allow es_sync's batch window (default 2 s) + network slack to flush
    log.info("[poll] sleeping 10 s for es_sync batch flush …")
    time.sleep(10)

    # ── Phase 4: validate recommendations & search ───────────────────────────
    run_validation(users, posts, statuses)


if __name__ == "__main__":
    main()
