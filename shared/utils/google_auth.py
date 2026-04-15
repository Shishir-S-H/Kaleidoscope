"""Google Cloud Application Default Credentials bootstrap.

On DigitalOcean (or any environment without ``gcloud`` installed), pass the
service-account JSON key as a Base64 string via ``GOOGLE_CREDENTIALS_BASE64``.
This module decodes it to a temp file and points the SDK at that file via
``GOOGLE_APPLICATION_CREDENTIALS``.

On a developer workstation with ``gcloud auth application-default login`` the
variable is absent and the standard ADC chain is used unchanged.

Usage — call once at provider start-up::

    from shared.utils.google_auth import setup_google_credentials
    setup_google_credentials()
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import threading

logger = logging.getLogger(__name__)

_setup_lock = threading.Lock()
_setup_done = False
_tmp_credential_file: tempfile.NamedTemporaryFile | None = None


def setup_google_credentials() -> None:
    """Decode GOOGLE_CREDENTIALS_BASE64 into a temp file, if set.

    Idempotent — safe to call from every provider ``__init__`` without
    re-creating the file on every instantiation.
    """
    global _setup_done, _tmp_credential_file

    with _setup_lock:
        if _setup_done:
            return

        b64_key = os.getenv("GOOGLE_CREDENTIALS_BASE64", "").strip()
        if not b64_key:
            logger.debug(
                "GOOGLE_CREDENTIALS_BASE64 not set; "
                "relying on system Application Default Credentials."
            )
            _setup_done = True
            return

        try:
            key_json_bytes = base64.b64decode(b64_key)
            key_dict = json.loads(key_json_bytes)
        except Exception as exc:
            raise ValueError(
                "GOOGLE_CREDENTIALS_BASE64 is set but could not be decoded as "
                f"valid Base64-encoded JSON: {exc}"
            ) from exc

        _tmp_credential_file = tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".json",
            prefix="gcp_creds_",
            delete=False,
        )
        _tmp_credential_file.write(key_json_bytes)
        _tmp_credential_file.flush()
        _tmp_credential_file.close()

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _tmp_credential_file.name

        cred_type = key_dict.get("type", "unknown")
        logger.info(
            "Google credentials (%s) written to %s and GOOGLE_APPLICATION_CREDENTIALS set.",
            cred_type,
            _tmp_credential_file.name,
        )
        _setup_done = True


def get_google_project() -> str:
    """Return the GCP project ID from env, raising clearly if absent."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_PROJECT_ID", "")
    if not project:
        raise EnvironmentError(
            "GCP project not configured. "
            "Set GOOGLE_CLOUD_PROJECT or GOOGLE_PROJECT_ID."
        )
    return project


def get_google_location() -> str:
    """Return the GCP region/location, defaulting to us-central1."""
    return os.getenv("GOOGLE_CLOUD_REGION") or os.getenv("GOOGLE_LOCATION", "us-central1")
