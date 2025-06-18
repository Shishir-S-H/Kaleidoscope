# Kaleidoscope AI - Upload Gateway Service
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    # Save to file system or MinIO later
    return JSONResponse(content={"filename": file.filename})
