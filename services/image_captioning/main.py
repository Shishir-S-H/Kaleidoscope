import io
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

app = FastAPI(title="Image Captioning", description="Image captioning with BLIP", version="1.0.0")

MODEL_NAME = "Salesforce/blip-image-captioning-base"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

processor = BlipProcessor.from_pretrained(MODEL_NAME)
model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME).to(DEVICE)

@app.post("/process")
async def process_caption(
    file: UploadFile = File(...),
    image_id: str = Query(None, description="Optional image ID")
):
    img_id = image_id or (file.filename.split(".")[0] if file.filename else str(uuid.uuid4()))
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file.")

    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=30)
        caption = processor.decode(out[0], skip_special_tokens=True)

    response = {
        "image_id": img_id,
        "service": "image_captioning",
        "result": {
            "caption": caption
        },
        "model": "BLIP",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return JSONResponse(content=response) 