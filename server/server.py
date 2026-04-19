from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Annotated, Optional
import shutil
import subprocess
import imageio_ffmpeg
import supervision as sv
import pymongo

app = FastAPI()

# Allow the Vite dev server (5173 or 5174) to call us from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR = Path("Annotated")
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {"video/mp4"}

# Placeholder events the frontend renders over the timeline until the CV
# pipeline surfaces real ones.
DEFAULT_EVENTS = [
    "Tip-off",
    "First basket",
    "Pick and roll — Team 0",
    "Fast break",
    "Turnover",
    "3-point attempt",
    "Isolation play — Team 1",
    "Timeout",
]


def _find_annotated_video() -> Optional[Path]:
    if not ANNOTATED_DIR.exists():
        return None
    matches = sorted(ANNOTATED_DIR.glob("*.mp4"))
    return matches[0] if matches else None


def _get_video_duration(path: Path) -> float:
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return 120.0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if fps > 0 and frames > 0:
            return float(frames / fps)
        return 120.0
    except Exception:
        return 120.0


FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def _transcode_to_h264(src: Path, dst: Path) -> bool:
    """Re-encode src into a web-playable H.264/AAC mp4 at dst.
    Returns True on success. Browsers can't decode MPEG-4 Part 2 (FMP4/XviD),
    HEVC, or other non-H.264 codecs, so every upload is normalised here."""
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", str(src),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return True
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="replace")
        print(f"[transcode] ffmpeg failed: {stderr[-500:]}")
        return False
    except subprocess.TimeoutExpired:
        print("[transcode] ffmpeg timeout after 10 minutes")
        return False


def _placeholder_timestamps(duration: float) -> list[dict]:
    if duration < len(DEFAULT_EVENTS):
        duration = float(len(DEFAULT_EVENTS))
    step = duration / (len(DEFAULT_EVENTS) + 1)
    return [
        {
            "time": round((i + 1) * step, 1),
            "description": DEFAULT_EVENTS[i],
            "thumbnail": f"https://picsum.photos/seed/{i + 1}/120/68",
        }
        for i in range(len(DEFAULT_EVENTS))
    ]


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/api/video/info")
async def video_info():
    """Tell the frontend whether an annotated video is ready.
    On hit, the player renders and streams from /videoSend/<filename>.
    On miss, the player renders the drag-and-drop upload backboard."""
    video = _find_annotated_video()
    if video is None:
        return {"hasVideo": False}

    duration = _get_video_duration(video)
    return {
        "hasVideo": True,
        "metadata": {
            "duration": duration,
            "title": video.name,
            "url": f"http://localhost:8000/videoSend/{video.name}",
        },
        "timestamps": _placeholder_timestamps(duration),
    }


@app.get("/api/video/timestamps")
async def video_timestamps(duration: float):
    return _placeholder_timestamps(duration)


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

    # ------------------------------------------------------------------
    # DEMO BRIDGE — until the CV pipeline is wired in.
    # Transcode the raw upload into a web-playable H.264/AAC mp4 and put
    # the result in Annotated/. Browsers refuse anything other than H.264
    # (FMP4/XviD, HEVC, ProRes, etc. all fail silently), so this step is
    # required even once real annotation lands — unless the CV pipeline
    # already emits H.264. Fallback to raw copy if ffmpeg blows up, so
    # the player at least has something to try.
    # ------------------------------------------------------------------
    annotated_dest = ANNOTATED_DIR / filename
    if not _transcode_to_h264(dest, annotated_dest):
        shutil.copy2(dest, annotated_dest)

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

    # Serve as inline video (not a download) so <video> can stream it.
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
    )


@app.delete("/api/video")
async def delete_video():
    """Wipe uploads/ and Annotated/ so the player falls back to the
    upload backboard. Called from the close (X) button in the player."""
    removed = []
    for folder in (UPLOAD_DIR, ANNOTATED_DIR):
        if folder.exists():
            for mp4 in folder.glob("*.mp4"):
                try:
                    mp4.unlink()
                    removed.append(str(mp4))
                except OSError:
                    pass
    return {"removed": removed}
