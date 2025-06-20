import io
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from PIL import Image
import torch
import open_clip

app = FastAPI(title="Content Moderation Service (CLIP)", description="Zero-shot content moderation using OpenCLIP.", version="1.0.0")

# Load OpenCLIP model at startup
MODEL_NAME = "ViT-B-32"
PRETRAINED = "openai"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

try:
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    model = model.to(DEVICE)
    model.eval()
except Exception as e:
    model = None
    preprocess = None
    tokenizer = None
    print(f"Failed to load OpenCLIP model: {e}")

# Moderation labels
LABELS = ["nsfw", "nudity", "violence", "safe"]

@app.post("/moderate", summary="Moderate an image for unsafe content", response_description="Moderation result")
async def moderate_image(
    file: UploadFile = File(...),
    image_id: str = Query(None, description="Optional image ID. If not provided, will use filename or generate UUID.")
):
    """
    Accepts an image file and returns moderation scores for unsafe content using OpenCLIP zero-shot classification.
    """
    if model is None or preprocess is None or tokenizer is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
    # Prepare image
    image_input = preprocess(image).unsqueeze(0).to(DEVICE)
    # Prepare text
    text_inputs = tokenizer(LABELS)
    text_inputs = text_inputs.to(DEVICE)
    # Inference
    with torch.no_grad():
        image_features = model.encode_image(image_input)
        text_features = model.encode_text(text_inputs)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        logits_per_image = (image_features @ text_features.T).squeeze(0)
        probs = logits_per_image.softmax(dim=0).cpu().tolist()
    # Map scores to labels
    scores = {label: float(prob) for label, prob in zip(LABELS, probs)}
    # Calculate safe field
    safe = all(scores.get(label, 0.0) < 0.3 for label in ["nsfw", "nudity", "violence"])
    # Determine image_id
    if image_id:
        img_id = image_id
    elif file.filename:
        img_id = file.filename.rsplit(".", 1)[0]
    else:
        img_id = str(uuid.uuid4())
    # Timestamp
    timestamp = datetime.now(timezone.utc).isoformat()
    # Build response
    response = {
        "image_id": img_id,
        "service": "content_moderation",
        "result": {
            "safe": safe,
            "scores": scores
        },
        "model": "OpenCLIP ViT-B/32",
        "timestamp": timestamp
    }
    return JSONResponse(content=response) 