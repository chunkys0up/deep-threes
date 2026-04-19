from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Annotated, Optional, Literal
import os
import json
import re
import shutil
import subprocess
import imageio_ffmpeg

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
import basketball_cv.run_model as run_model
from db import fetch_shots, replace_video_session


# Load .env BEFORE reading any environment variables.
load_dotenv(Path(__file__).parent / ".env")

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

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "Uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR = BASE_DIR / "Annotated"
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

# --------------------------------------------------------------------
# Gemini client — initialised once at module load.
# Missing key isn't fatal: server still boots, /api/chat degrades to 500.
# --------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemma-3-27b-it")
_gemini_client: Optional["genai.Client"] = None
if GEMINI_API_KEY:
    try:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"[chat] Gemini client ready (model={GEMINI_MODEL})")
    except Exception as e:
        print(f"[chat] Failed to init Gemini client: {e}")
        _gemini_client = None
else:
    print("[chat] GEMINI_API_KEY not set — /api/chat will return 500 until it is")


class ChatMessage(BaseModel):
    sender: Literal["user", "bot"]
    text: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


def _fmt_mmss(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _build_system_instruction() -> str:
    base = (
        "You are the AI assistant for Deep Court Analytics — a basketball "
        "computer-vision tool used by coaches and analysts. "
        "Be concise (1–3 sentences unless summarising), basketball-literate, "
        "and cite timestamps (mm:ss) when the user asks about specific events. "
        "If no video is loaded, tell the user to upload one on the Film page. "
        "If you don't have data for something, say so honestly rather than guessing.\n\n"
        "STRUCTURED OUTPUT CONTRACT:\n"
        " - Always return valid JSON: { text: string, highlights: number[] }.\n"
        " - `text` is your natural-language reply.\n"
        " - `highlights` is a list of INTEGER INDICES into the events table "
        "below. Return indices for events that match the user's query — "
        "e.g. 'show me the turnovers', 'shots from long range', 'first basket'. "
        "Return an EMPTY array for greetings, summaries, or questions that "
        "aren't about specific events."
    )
    video = _find_annotated_video()
    if video is None:
        return base + "\n\nThere is no video loaded right now. The events table is empty — always return `highlights: []`."
    duration = _get_video_duration(video)
    events = _placeholder_timestamps(duration)
    lines = "\n".join(
        f"  [{i}] {_fmt_mmss(e['time'])} — {e['description']}"
        for i, e in enumerate(events)
    )
    return (
        f"{base}\n\n"
        f"A video is currently loaded: {video.name} "
        f"({_fmt_mmss(duration)} long).\n"
        f"Events table (placeholder until CV pipeline lands — indices are 0-based):\n{lines}"
    )


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
    # Distribute events evenly inside the actual video duration so every event
    # position stays inside [0, 100%] for the scrubber — no more half-clipped
    # thumbnails on the right edge.
    if duration <= 0:
        duration = 120.0
    step = duration / (len(DEFAULT_EVENTS) + 1)
    return [
        {
            "time": round((i + 1) * step, 2),
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


@app.get("/api/shots")
async def get_shots():
    return fetch_shots()


@app.post("/videoUpload")
async def videoUpload(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,

):
    if file.content_type not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported Media Type")

    ext = Path(file.filename or "").suffix.lower()
    filename = f"input{ext}"
    dest = UPLOAD_DIR / filename
    outputFilename = f"output{ext}"
    annotated_dest = ANNOTATED_DIR / outputFilename

    if dest.exists():
        dest.unlink()
    if annotated_dest.exists():
        annotated_dest.unlink()

    with dest.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    await file.close()

    shots = run_model.run_model(str(dest), str(annotated_dest))
    shot_count = replace_video_session(
        shots,
        source_video=dest.name,
        annotated_video=annotated_dest.name,
    )

    return {
        "message": "uploaded",
        "title": title,
        "original_filename": filename,
        "stored_as": dest.name,
        "annotated_filename": annotated_dest.name,
        "shots_stored": shot_count,
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


CHAT_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "text": {"type": "STRING"},
        "highlights": {
            "type": "ARRAY",
            "items": {"type": "INTEGER"},
        },
    },
    "required": ["text", "highlights"],
}


class RateLimitError(Exception):
    """Signals the Gemini free-tier 429; caller may fall back to Ollama."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after


def _parse_chat_json(raw: str) -> tuple[str, list[int]]:
    """Parse the {text, highlights[]} JSON blob both providers emit.
    Defensive against truncation, floats-as-strings, schema drift, and
    markdown code-fence wrapping (common with Gemma/Ollama)."""
    text = ""
    highlights: list[int] = []

    cleaned = (raw or "").strip()
    # Strip ```json ... ``` or ``` ... ``` fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        parsed = json.loads(cleaned) if cleaned else {}
        text = str(parsed.get("text", "")).strip()
        for h in parsed.get("highlights") or []:
            try:
                highlights.append(int(h))
            except (TypeError, ValueError):
                continue
    except json.JSONDecodeError:
        text = cleaned or raw
    if not text:
        text = "(no response)"
    return text, highlights


def _call_gemini(req: ChatRequest) -> tuple[str, list[int]]:
    if _gemini_client is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "GEMINI_API_KEY not set on server. Create server/.env with "
                "GEMINI_API_KEY=... and restart uvicorn."
            ),
        )

    # Inline the system instruction as a prefix to the CURRENT user message.
    # Reason: Gemma models (served via the same Gemini API endpoint) reject
    # the separate `system_instruction` config field with
    # "Developer instruction is not enabled for models/gemma-*".
    # Inlining works equally well for both Gemma and Gemini models.
    system_txt = _build_system_instruction()
    inlined_message = f"{system_txt}\n\n---\n\nUser message: {req.message}"

    recent = req.history[-20:]
    contents = []
    for m in recent:
        role = "user" if m.sender == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.text}]})
    contents.append({"role": "user", "parts": [{"text": inlined_message}]})

    # JSON-mode + response_schema is supported by gemini-* models only.
    # Gemma-* models served via the same API reject it with
    # "JSON mode is not enabled for models/gemma-*". Fall back to plain
    # generation + best-effort JSON parsing (system prompt already instructs
    # the model to emit our JSON shape).
    config_kwargs: dict = {}
    if GEMINI_MODEL.startswith("gemini-"):
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = CHAT_RESPONSE_SCHEMA

    try:
        response = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            retry_after = 30
            m = re.search(r"retryDelay['\"]?:\s*['\"](\d+(?:\.\d+)?)s", msg)
            if not m:
                m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
            if m:
                try:
                    retry_after = int(float(m.group(1))) + 2
                except ValueError:
                    pass
            retry_after = max(5, min(120, retry_after))
            raise RateLimitError(retry_after)
        print(f"[chat] Gemini call failed: {e}")
        raise HTTPException(
            status_code=502, detail=f"Gemini upstream error: {e}")

    return _parse_chat_json((response.text or "").strip())


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send the user's message to Gemini/Gemma via Google AI Studio.
    Returns { text, highlights[] } where highlights is the list of event
    indices the frontend uses to filter the seekbar + thumbnails."""
    try:
        text, highlights = _call_gemini(req)
    except RateLimitError as rl:
        print(f"[chat] rate-limited; frontend should wait {rl.retry_after}s")
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after": rl.retry_after},
        )
    return {"text": text, "highlights": highlights}


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
