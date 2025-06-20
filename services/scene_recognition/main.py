import io
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import torch
import open_clip

app = FastAPI(title="Scene Recognition", description="Zero-shot scene recognition with OpenCLIP", version="1.0.0")

# Predefined candidate scene labels
SCENE_LABELS = [
    "beach", "conference room", "urban city", "classroom", "mountains", "temple", "party", "forest", "desert", "kitchen", "stadium", "library", "restaurant", "airport", "hospital", "hotel room", "living room", "park", "shopping mall", "street", "subway station", "swimming pool", "office", "museum", "cafe", "church", "garage", "gym", "harbor", "highway", "jungle", "lake", "mosque", "nightclub", "playground", "plaza", "school", "theater", "train station", "zoo"
]

MODEL_NAME = "ViT-B-32"
PRETRAINED = "openai"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
model.to(DEVICE)
tokenizer = open_clip.get_tokenizer(MODEL_NAME)

@app.post("/process")
async def process_scene(
    file: UploadFile = File(...),
    image_id: str = Query(None, description="Optional image ID")
):
    img_id = image_id or (file.filename.split(".")[0] if file.filename else str(uuid.uuid4()))
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    image_input = preprocess(image).unsqueeze(0).to(DEVICE)
    text_inputs = tokenizer([f"a photo of a {scene}" for scene in SCENE_LABELS]).to(DEVICE)

    with torch.no_grad():
        image_features = model.encode_image(image_input)
        text_features = model.encode_text(text_inputs)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        scores = similarity[0].cpu().tolist()

    scene_scores = dict(zip(SCENE_LABELS, scores))
    best_scene = max(scene_scores.items(), key=lambda x: x[1])[0]

    response = {
        "image_id": img_id,
        "service": "scene_recognition",
        "result": {
            "scene": best_scene,
            "scores": {scene: round(scene_scores[scene], 4) for scene in SCENE_LABELS if scene_scores[scene] > 0.01}
        },
        "model": "OpenCLIP ViT-B/32",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return JSONResponse(content=response) 