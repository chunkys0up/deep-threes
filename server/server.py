from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Annotated
import supervision as sv
import pymongo

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR = Path("Annotated")
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)



ALLOWED_EXTENSIONS = {"video/mp4"}

#filename = ""

# Database connection



@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/videoUpload")
async def videoUpload(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,

):
    if file.content_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported Media Type")

    ext = Path(file.filename or "").suffix.lower()
    filename = f"video{ext}"
    dest = UPLOAD_DIR / filename

    with dest.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    await file.close()

    return {
        "message": "uploaded",
        "title": title,
        "original_filename": filename,
        "stored_as": filename,
        "content_type": file.content_type,
    }

@app.get("/videoSend/{filename}")
async def send_video(filename: str):
    video_path = ANNOTATED_DIR / filename

    if not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video Not Found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=filename,
    )

