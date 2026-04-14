#!/usr/bin/env python3
"""
stress_tests/kaleidoscope_stress_test.py
-----------------------------------------
End-to-end stress test for the Kaleidoscope media processing + recommendation
pipeline.

Pipeline under test
───────────────────
  POST /api/auth/register → POST /api/auth/login
    → Cloudinary upload (local /tmp image)
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
  requests faker psycopg2-binary elasticsearch python-dotenv

Environment variables (see CONFIG block below). A `.env` file at the repo root
is loaded automatically via python-dotenv (override with real env vars as needed).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Load repo-root .env before CONFIG (module-level os.getenv reads).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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

NUM_USERS           = int(os.getenv("STRESS_NUM_USERS",     "3"))
POSTS_PER_USER      = int(os.getenv("STRESS_POSTS_PER_USER", "2"))
# If unset, the first category from GET /api/categories is used (requires auth).
STRESS_CATEGORY_ID  = os.getenv("STRESS_CATEGORY_ID", "").strip()

# Pipeline-completion polling
POLL_INTERVAL_S     = float(os.getenv("POLL_INTERVAL_S",  "5"))
POLL_TIMEOUT_S      = float(os.getenv("POLL_TIMEOUT_S",  "300"))   # 5 min max

# Signed upload retry (same env names as legacy direct-Cloudinary upload)
CLOUDINARY_MAX_RETRIES  = int(os.getenv("CLOUDINARY_MAX_RETRIES",   "3"))
CLOUDINARY_RETRY_BASE_S = float(os.getenv("CLOUDINARY_RETRY_BASE_S", "2.0"))

# Image download
IMAGE_TMP_DIR       = Path(os.getenv("IMAGE_TMP_DIR", "/tmp/kaleidoscope_stress"))
IMAGE_WIDTH         = int(os.getenv("IMAGE_WIDTH",  "800"))
IMAGE_HEIGHT        = int(os.getenv("IMAGE_HEIGHT", "600"))

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
# Phase 0b – Dynamic image sourcing  (picsum.photos)
# ─────────────────────────────────────────────────────────────────────────────
# We use https://picsum.photos/<w>/<h>  which redirects to a real photograph.
# Adding ?random=<n> avoids the CDN returning the same byte-sequence for every
# call, which helps exercise the AI workers with varied content.
# ─────────────────────────────────────────────────────────────────────────────

def download_random_image(index: int) -> Path:
    """
    Download a unique random JPEG from picsum.photos and save it to IMAGE_TMP_DIR.
    Returns the local Path of the saved file.

    The ?random query parameter is a per-call unique integer so each request
    fetches a different photograph even within the same test run.
    """
    IMAGE_TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGE_TMP_DIR / f"stress_{index:04d}_{uuid.uuid4().hex[:8]}.jpg"

    # Use a unique seed so picsum.photos returns different images each call.
    # The /seed/<seed>/<w>/<h> endpoint is deterministic per seed, so combining
    # the loop index with a run-level UUID guarantees uniqueness.
    run_seed = f"stress_{index}_{uuid.uuid4().hex[:12]}"
    url = f"https://picsum.photos/seed/{run_seed}/{IMAGE_WIDTH}/{IMAGE_HEIGHT}"

    log.info("[image] downloading %s → %s", url, dest.name)
    resp = requests.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise ValueError(f"Unexpected Content-Type from picsum: {content_type!r}")

    dest.write_bytes(resp.content)
    log.info("[image] saved %d bytes to %s", len(resp.content), dest)
    return dest


def download_images_for_run(total_posts: int) -> List[Path]:
    """
    Pre-download one unique image per post so each post gets distinct content.
    Failures are logged but do not abort the run; a previously-downloaded image
    is reused as a fallback.
    """
    paths: List[Path] = []
    fallback: Optional[Path] = None

    for i in range(total_posts):
        try:
            p = download_random_image(i)
            paths.append(p)
            fallback = p
        except Exception as exc:
            log.warning("[image] download %d failed: %s", i, exc)
            if fallback:
                log.warning("[image] reusing %s as fallback", fallback.name)
                paths.append(fallback)
            else:
                # Last resort: tiny synthetic JPEG (1×1 white pixel)
                synthetic = _synthetic_jpeg(i)
                paths.append(synthetic)
                fallback = synthetic

    return paths


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
                users.append(u)
        except Exception as exc:
            log.error("[user] user %d setup failed: %s", i, exc)
    log.info("[phase-1] %d/%d users ready", len(users), n)
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
    user:        TestUser,
    media_url:   str,
    title:       str,
    body:        str,
    summary:     str,
    category_id: int,
) -> dict:
    """Create a post; returns `data` PostCreationResponseDTO as dict."""
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
                "width":            IMAGE_WIDTH,
                "height":           IMAGE_HEIGHT,
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
    image_paths: List[Path],
    fake,
    category_id: int,
) -> List[dict]:
    """
    For every user × POSTS_PER_USER, upload the pre-downloaded image to
    Cloudinary, then create the post.  Content (title, body) is Faker-generated
    per post.  Returns all successfully created PostDTOs.
    """
    all_posts: List[dict] = []
    image_index = 0

    for user in users:
        for p_idx in range(POSTS_PER_USER):
            title, body, _tags = generate_post_content(fake)
            summary = body[:240].replace("\n", " ") + ("..." if len(body) > 240 else "")
            img_path = image_paths[image_index % len(image_paths)]
            image_index += 1

            try:
                media_url = upload_image_for_post(user, img_path)
                post      = create_post(user, media_url, title, body, summary, category_id)
                user.posts.append(post)
                all_posts.append(post)
            except Exception as exc:
                log.error("[ingest] user=%s post=%d failed: %s",
                          user.username, p_idx, exc)

    log.info("[phase-2] %d posts created across %d users", len(all_posts), len(users))
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
# REST endpoints (Java):
#   GET /api/recommendations?page=0&size=20       → Page<PostDTO>
#   GET /api/search/media?q=<term>&page=0&size=10 → Page<MediaResultDTO>
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
    """Call /api/recommendations for each user; log item counts."""
    log.info("[validate] GET /api/recommendations …")
    for user in users:
        if not user.access_token:
            continue
        try:
            resp = requests.get(
                f"{_api_base()}/api/recommendations",
                params  = {"page": 0, "size": 20},
                headers = {"Authorization": f"Bearer {user.access_token}"},
                timeout = 15,
            )
            resp.raise_for_status()
            items = _paginated_content(resp.json())
            icon  = "✓" if items else "⚠ empty"
            log.info("[validate] %s  user=%-28s  recommendations=%d",
                     icon, user.username, len(items))
        except Exception as exc:
            log.error("[validate] /api/recommendations failed for %s: %s",
                      user.username, exc)


def validate_rest_media_search(users: List[TestUser]) -> None:
    """
    Call /api/search/media with several AI-relevant terms; log hit counts.
    Uses a representative pool of terms that the tagging/scene workers would
    commonly produce for real photographs sourced from picsum.photos.
    """
    log.info("[validate] GET /api/search/media …")
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
                f"{_api_base()}/api/search/media",
                params  = {"q": term, "page": 0, "size": 10},
                headers = {"Authorization": f"Bearer {user.access_token}"},
                timeout = 15,
            )
            resp.raise_for_status()
            items = _paginated_content(resp.json())
            log.info("[validate]   search q=%-20r  hits=%d", term, len(items))
        except Exception as exc:
            log.error("[validate] /api/search/media q=%r failed: %s", term, exc)


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

        # KNN probe: zero-vector surfaces whatever is actually indexed
        probe     = [0.0] * 512
        knn_resp  = es.search(
            index = "recommendations_knn",
            body  = {
                "knn": {
                    "field":          "image_embedding",
                    "query_vector":   probe,
                    "k":              5,
                    "num_candidates": 50,
                    "filter":         {"term": {"is_safe": True}},
                }
            },
        )
        knn_hits = knn_resp["hits"]["hits"]
        log.info("[validate-es] KNN probe → %d hit(s) from recommendations_knn",
                 len(knn_hits))

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
        NUM_USERS, len(posts), total, ok, unsafe, failed, pending,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("═══════════════════════════════════════════════════")
    log.info("  Kaleidoscope End-to-End Stress Test")
    log.info("  Backend  : %s", BACKEND_BASE_URL)
    log.info("  Database : %s:%d/%s", DB_HOST, DB_PORT, DB_NAME)
    log.info("  ES       : %s", ES_HOST)
    log.info("  Users    : %d   Posts/user: %d", NUM_USERS, POSTS_PER_USER)
    log.info("═══════════════════════════════════════════════════")

    fake = _build_faker()

    # ── Phase 1: create users ────────────────────────────────────────────────
    users = setup_users(NUM_USERS, fake)
    if not users:
        log.error("No users created – aborting.")
        sys.exit(1)

    # ── Phase 0b: pre-download unique images ─────────────────────────────────
    total_posts = len(users) * POSTS_PER_USER
    image_paths = download_images_for_run(total_posts)
    log.info("[images] %d image(s) ready in %s", len(image_paths), IMAGE_TMP_DIR)

    # ── Phase 2: ingest content ───────────────────────────────────────────────
    category_id = resolve_category_id(users[0])
    posts = ingest_content(users, image_paths, fake, category_id)
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
