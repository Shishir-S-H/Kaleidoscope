import os
import uuid
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from databases import Database
from sqlalchemy import (
    Column, String, DateTime, Table, MetaData, create_engine, JSON as SAJSON
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from dotenv import load_dotenv
from minio import Minio
import io

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://kaleido:strongpass@db:5432/kaleidoscope")

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "kaleidoscope-images")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Initialize MinIO client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

# Database setup
metadata = MetaData()
image_metadata = Table(
    "image_metadata",
    metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("image_id", String, nullable=False),
    Column("metadata", SAJSON, nullable=False),
    Column("timestamp", DateTime, default=datetime.utcnow)
)
database = Database(DATABASE_URL)

app = FastAPI(title="Orchestrator Service")

class ImageInput(BaseModel):
    image_id: str
    image_url: str

@app.on_event("startup")
async def startup():
    await database.connect()
    # Create table if not exists
    engine = create_engine(DATABASE_URL.replace('asyncpg', 'psycopg2'))
    metadata.create_all(engine)

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator"}

@app.get("/test-minio")
async def test_minio():
    """Test MinIO connectivity"""
    try:
        async with httpx.AsyncClient() as client:
            # Test MinIO health endpoint
            health_response = await client.get("http://minio:9000/minio/health/live")
            
            # Test specific image
            image_url = "http://minio:9000/kaleidoscope-images/960b7e4f-f9f8-4d00-bc9a-5d67fadbf5ed.jpg"
            image_response = await client.get(image_url)
            
            return {
                "minio_health": health_response.status_code,
                "image_status": image_response.status_code,
                "image_url": image_url,
                "image_headers": dict(image_response.headers)
            }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.post("/process-image")
async def process_image(payload: ImageInput):
    try:
        # Extract object name from image_url
        object_name = payload.image_url.split('/')[-1]
        
        # Fetch image from MinIO directly
        try:
            image_response = minio_client.get_object(MINIO_BUCKET, object_name)
            image_bytes = image_response.read()
            image_response.close()
            image_response.release_conn()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch image from MinIO: {str(e)}")

        # 2. Call content_moderation
        async with httpx.AsyncClient() as client:
            cm_resp = await client.post(
                "http://content_moderation:8001/moderate", 
                files={"file": (object_name, image_bytes, "image/jpeg")}
            )
            if cm_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Content moderation service error")
            cm_result = cm_resp.json()
            if not cm_result.get("result", {}).get("safe", False):
                result = {
                    "image_id": payload.image_id,
                    "moderation": cm_result,
                    "status": "unsafe"
                }
                # Store in DB
                await database.execute(image_metadata.insert().values(
                    id=uuid.uuid4(),
                    image_id=payload.image_id,
                    metadata=result,
                    timestamp=datetime.utcnow()
                ))
                return JSONResponse(content=result)

            # 2b. If safe, call other services in parallel
            tagger = client.post(
                "http://image_tagger:8000/process", 
                files={"file": (object_name, image_bytes, "image/jpeg")}
            )
            scene = client.post(
                "http://scene_recognition:8000/process", 
                files={"file": (object_name, image_bytes, "image/jpeg")}
            )
            caption = client.post(
                "http://image_captioning:8000/process", 
                files={"file": (object_name, image_bytes, "image/jpeg")}
            )
            tagger_resp, scene_resp, caption_resp = await asyncio.gather(tagger, scene, caption)
            result = {
                "image_id": payload.image_id,
                "moderation": cm_result,
                "tags": tagger_resp.json() if tagger_resp.status_code == 200 else None,
                "scene": scene_resp.json() if scene_resp.status_code == 200 else None,
                "caption": caption_resp.json() if caption_resp.status_code == 200 else None,
                "status": "processed"
            }
            # 3. Store in DB
            await database.execute(image_metadata.insert().values(
                id=uuid.uuid4(),
                image_id=payload.image_id,
                metadata=result,
                timestamp=datetime.utcnow()
            ))
            return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 