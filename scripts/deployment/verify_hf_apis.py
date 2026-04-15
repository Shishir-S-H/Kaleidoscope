#!/usr/bin/env python3
"""One-off: verify face Space + HF serverless models used by Kaleidoscope AI."""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# Minimal valid 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _probe_image_path() -> Path:
    """224×224 JPEG — tiny images break some vision models on serverless inference."""
    try:
        from PIL import Image
    except ImportError:
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            f.write(_PNG)
            f.close()
            return Path(f.name)
        except Exception:
            f.close()
            Path(f.name).unlink(missing_ok=True)
            raise
    fd, name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    path = Path(name)
    Image.new("RGB", (224, 224), color=(90, 120, 200)).save(path, "JPEG", quality=90)
    return path



def main() -> int:
    results: dict = {
        "face_space": {},
        "hf_models": {},
        "hf_token_present": bool(
            os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        ),
    }

    for label, url, method in (
        ("root", "https://phantomfury-kaleidoscope-face-recognition.hf.space/", "GET"),
        (
            "detect_no_file",
            "https://phantomfury-kaleidoscope-face-recognition.hf.space/detect",
            "POST",
        ),
    ):
        req = urllib.request.Request(url, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=30)
            body = r.read(800).decode("utf-8", errors="replace")
            results["face_space"][label] = {"http": r.status, "body_preview": body[:400]}
        except urllib.error.HTTPError as e:
            body = e.read(800).decode("utf-8", errors="replace")
            results["face_space"][label] = {"http": e.code, "body_preview": body[:400]}
        except Exception as e:
            results["face_space"][label] = {"error": str(e)}

    boundary = "----BoundaryKaleidoscopeVerify"
    crlf = b"\r\n"
    body = (
        b"--" + boundary.encode()
        + crlf
        + b'Content-Disposition: form-data; name="file"; filename="t.png"'
        + crlf
        + b"Content-Type: image/png"
        + crlf
        + crlf
        + _PNG
        + crlf
        + b"--"
        + boundary.encode()
        + b"--"
        + crlf
    )
    req = urllib.request.Request(
        "https://phantomfury-kaleidoscope-face-recognition.hf.space/detect",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=120)
        results["face_space"]["detect_with_file"] = {
            "http": r.status,
            "body_preview": r.read(2000).decode("utf-8", errors="replace")[:800],
        }
    except urllib.error.HTTPError as e:
        body = e.read(1200).decode("utf-8", errors="replace")
        results["face_space"]["detect_with_file"] = {
            "http": e.code,
            "body_preview": body[:600],
        }
    except Exception as e:
        results["face_space"]["detect_with_file"] = {"error": str(e)}

    token = os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    try:
        import huggingface_hub
        from huggingface_hub import InferenceClient

        results["huggingface_hub_version"] = huggingface_hub.__version__
    except ImportError as e:
        results["hf_models"] = {"error": f"huggingface_hub missing: {e}"}
        print(json.dumps(results, indent=2))
        return 0

    client = InferenceClient(token=token or None)
    img_path = _probe_image_path()

    def run_feature(model_id: str) -> dict:
        try:
            out = client.feature_extraction(str(img_path), model=model_id)
        finally:
            pass
        flat = out
        while isinstance(flat, list) and flat and isinstance(flat[0], list):
            flat = flat[0]
        dim = len(flat) if isinstance(flat, list) else "n/a"
        return {"ok": True, "embedding_dim": dim}

    def run_classify(model_id: str) -> dict:
        out = client.image_classification(str(img_path), model=model_id)
        top = out[0] if out else None
        return {
            "ok": True,
            "top_label": str(getattr(top, "label", top))[:80],
            "top_score": float(getattr(top, "score", 0)),
        }

    def run_caption(model_id: str) -> dict:
        out = client.image_to_text(str(img_path), model=model_id)
        txt = getattr(out, "generated_text", None) or str(out)[:200]
        return {"ok": True, "caption_preview": txt[:120]}

    tests = [
        ("fe", "openai/clip-vit-base-patch32", lambda: run_feature("openai/clip-vit-base-patch32")),
        ("fe", "openai/clip-vit-base-patch16", lambda: run_feature("openai/clip-vit-base-patch16")),
        (
            "ic",
            "Falconsai/nsfw_image_detection",
            lambda: run_classify("Falconsai/nsfw_image_detection"),
        ),
        (
            "ic",
            "facebook/convnext-base-384-22k-1k",
            lambda: run_classify("facebook/convnext-base-384-22k-1k"),
        ),
        (
            "ic",
            "corenet-community/places365-224x224-vit-base",
            lambda: run_classify("corenet-community/places365-224x224-vit-base"),
        ),
        (
            "itt",
            "Salesforce/blip2-opt-2.7b",
            lambda: run_caption("Salesforce/blip2-opt-2.7b"),
        ),
    ]

    try:
        for task, model_id, fn in tests:
            key = f"{task}:{model_id}"
            try:
                results["hf_models"][key] = fn()
            except Exception as e:
                results["hf_models"][key] = {"ok": False, "error": repr(e)[:500]}
    finally:
        try:
            img_path.unlink(missing_ok=True)
        except OSError:
            pass

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
