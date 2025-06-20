import io
import uuid
from datetime import datetime, timezone
from typing import List, Dict

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import torch
import open_clip

app = FastAPI(title="Image Tagger", description="Zero-shot image tagging with OpenCLIP", version="1.0.0")

# Predefined candidate tags
CANDIDATE_TAGS = [
    "people", "food", "landscape", "sports", "technology", "animal", "vehicle", "nature", "building", "art", "fashion", "music", "travel", "business", "education"
]

# Load model at startup
MODEL_NAME = "ViT-B-32"
PRETRAINED = "openai"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
model.to(DEVICE)
tokenizer = open_clip.get_tokenizer(MODEL_NAME)

@app.post("/process")
async def process_image(
    file: UploadFile = File(...),
    image_id: str = Query(None, description="Optional image ID")
):
    # Accept image_id from query or fallback to filename or uuid
    img_id = image_id or (file.filename.split(".")[0] if file.filename else str(uuid.uuid4()))
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    # Preprocess image
    image_input = preprocess(image).unsqueeze(0).to(DEVICE)

    # Prepare text tokens
    text_inputs = tokenizer([f"a photo of {tag}" for tag in CANDIDATE_TAGS]).to(DEVICE)

    # Inference
    with torch.no_grad():
        image_features = model.encode_image(image_input)
        text_features = model.encode_text(text_inputs)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        scores = similarity[0].cpu().tolist()

    # Prepare tags and scores
    tag_scores = dict(zip(CANDIDATE_TAGS, scores))
    sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
    top_tags = [tag for tag, score in sorted_tags if score > 0.1][:5]  # threshold and top-N

    response = {
        "image_id": img_id,
        "service": "image_tagger",
        "result": {
            "tags": top_tags,
            "scores": {tag: round(tag_scores[tag], 4) for tag in top_tags}
        },
        "model": "OpenCLIP ViT-B/32",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return JSONResponse(content=response) 