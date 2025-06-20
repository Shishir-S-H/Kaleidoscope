# Kaleidoscope AI - Upload Gateway Service
import os
import io
from uuid import uuid4
from minio import Minio
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "kaleidoscope-images")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Ensure the bucket exists
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
            print(f"Created bucket: {MINIO_BUCKET}")
    except Exception as e:
        print(f"Error creating bucket: {e}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "upload_gateway"}

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image_id = str(uuid4())
        object_name = f"{image_id}.jpg"
        
        # Create a BytesIO object for MinIO
        file_data = io.BytesIO(contents)
        file_data.seek(0)
        
        # Upload to MinIO
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            data=file_data,
            length=len(contents),
            content_type="image/jpeg"
        )
        
        image_url = f"http://localhost:9000/{MINIO_BUCKET}/{object_name}"
        internal_url = f"http://minio:9000/{MINIO_BUCKET}/{object_name}"
        
        return JSONResponse(content={
            "image_id": image_id,
            "image_url": image_url,
            "internal_url": internal_url,
            "status": "uploaded"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
