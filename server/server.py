from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional, Literal
import os
import sys
import json
import re
import shutil
import subprocess
import uuid
import imageio_ffmpeg

# Put the project root on sys.path so `basketball_cv` (which lives one level
# above `server/`) is importable regardless of where uvicorn is launched from.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
# NOTE: basketball_cv.run_model is imported LAZILY inside /videoUpload so the
# server can still boot even when Roboflow SDK deps aren't installed yet.
from db import (
    clear_current_session,
    fetch_shots,
    fetch_current_session,
    replace_video_session,
    get_roster,
    save_roster,
    resolve_player,
    save_gallery_session,
    list_gallery_sessions,
    get_gallery_session,
    delete_gallery_session,
    load_gallery_session_as_current,
)


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
# Persistent archive of previous annotations — each session lives under its
# own uuid-named subdirectory: Gallery/<session_id>/{input.mp4,output.mp4,thumb.jpg}.
GALLERY_DIR = BASE_DIR / "Gallery"
GALLERY_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {"video/mp4"}

# Distance threshold (feet) used to classify a jump shot as a three-pointer
# when responding to natural-language queries. Matches what db.py uses.
_THREE_POINT_DISTANCE_FT = 22.0


def _find_annotated_video() -> Optional[Path]:
    if not ANNOTATED_DIR.exists():
        return None
    current = ANNOTATED_DIR / "output.mp4"
    if current.exists():
        return current
    matches = sorted(ANNOTATED_DIR.glob("*.mp4"))
    return matches[0] if matches else None


def _annotated_session_id(filename: str) -> str:
    return f"annotated:{filename}"


def _annotated_filename_from_session_id(session_id: str) -> str | None:
    prefix = "annotated:"
    if not session_id.startswith(prefix):
        return None
    filename = session_id[len(prefix):]
    if not filename or "/" in filename or "\\" in filename:
        return None
    return filename


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


def _build_system_instruction(user_query: str = "") -> str:
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
        " - `highlights` is a list of INTEGER INDICES — use the `[N]` values "
        "shown in brackets in the events table below. Return indices for events "
        "that match the user's query. Return an EMPTY array for greetings, "
        "summaries, or questions that aren't about specific events."
    )
    video = _find_annotated_video()
    if video is None:
        return (
            base
            + "\n\nThere is no video loaded right now. The events table is empty — always return `highlights: []`."
        )

    duration = _get_video_duration(video)
    shots, all_events = _all_events()

    if not all_events:
        return (
            base
            + f"\n\nA video is loaded ({video.name}, {_fmt_mmss(duration)}) but "
              "no shots have been extracted yet. The events table is empty — "
              "always return `highlights: []`."
        )

    filtered_events, original_indices = _filter_events_by_query(
        shots, all_events, user_query
    )

    if not filtered_events:
        events_block = "  (no events match the query)"
        scope_note = f"0 of {len(all_events)} events match"
    else:
        events_block = "\n".join(
            f"  [{idx}] {_fmt_mmss(ev['time'])} — {ev['description']}"
            for idx, ev in zip(original_indices, filtered_events)
        )
        scope_note = (
            "showing all events"
            if len(filtered_events) == len(all_events)
            else f"pre-filtered by the user's query — {len(filtered_events)} of {len(all_events)} events shown"
        )

    return (
        f"{base}\n\n"
        f"A video is currently loaded: {video.name} "
        f"({_fmt_mmss(duration)} long).\n"
        f"Events table ({scope_note}; bracketed numbers are the INDICES to use in "
        f"`highlights`):\n{events_block}"
    )


def _extract_thumbnail(src: Path, dst: Path, at_seconds: float = 0.5) -> bool:
    """Grab a single frame from `src` as a JPEG at `dst`.
    Fast-seek (`-ss` before `-i`) so we don't have to decode the whole clip.
    Returns True on success; failures are logged but non-fatal — the gallery
    card just shows a default placeholder if the thumb is missing."""
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-ss", f"{max(0.0, float(at_seconds)):.3f}",
        "-i", str(src),
        "-frames:v", "1",
        "-q:v", "3",
        str(dst),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return True
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="replace")
        print(f"[thumbnail] ffmpeg failed: {stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        print("[thumbnail] ffmpeg timeout after 30s")
        return False


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


def _web_playable_cache_path(src: Path) -> Path:
    cache_dir = GALLERY_DIR / "_web"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / src.name


def _ensure_web_playable_video(src: Path) -> Path:
    """Return a browser-safe mp4 path for `src`.
    We lazily transcode every served annotated file into a cache on first use,
    then reuse that cache until the source file changes."""
    cached = _web_playable_cache_path(src)
    try:
        if cached.exists() and cached.stat().st_mtime >= src.stat().st_mtime:
            return cached
    except OSError:
        pass

    tmp_cached = cached.with_suffix(cached.suffix + ".tmp.mp4")
    if tmp_cached.exists():
        try:
            tmp_cached.unlink()
        except OSError:
            pass

    if _transcode_to_h264(src, tmp_cached):
        if cached.exists():
            try:
                cached.unlink()
            except OSError:
                pass
        tmp_cached.rename(cached)
        return cached

    if tmp_cached.exists():
        try:
            tmp_cached.unlink()
        except OSError:
            pass
    return src


def _annotated_thumbnail_path(filename: str) -> Path:
    thumbs_dir = GALLERY_DIR / "_thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    return thumbs_dir / f"{filename}.jpg"


def _ensure_annotated_thumbnail(filename: str) -> Path | None:
    video_path = ANNOTATED_DIR / filename
    if not video_path.exists():
        return None

    thumb_path = _annotated_thumbnail_path(filename)
    try:
        if thumb_path.exists() and thumb_path.stat().st_mtime >= video_path.stat().st_mtime:
            return thumb_path
    except OSError:
        pass

    duration = _get_video_duration(video_path)
    thumb_at = max(0.5, duration * 0.1)
    if _extract_thumbnail(video_path, thumb_path, at_seconds=thumb_at):
        return thumb_path
    return None


def _shot_to_event(shot: dict, index: int, roster: dict | None = None) -> dict:
    """Translate a Mongo shot doc into the {time, description, thumbnail}
    shape the frontend seekbar + thumbnails strip consumes.
    Applies roster overrides so custom team/player names flow through."""
    shot_type = shot.get("shot_type") or ""
    distance = float(shot.get("distance_feet") or 0)
    made = bool(shot.get("made"))
    team_detected = (shot.get("team_name") or "").strip()
    jersey = shot.get("player_number")
    timestamp = float(shot.get("timestamp_seconds") or 0)

    # Roster lookup — falls back to detected values if no override is set.
    team_override, player_override = resolve_player(team_detected, jersey, roster)
    team_display = team_override or team_detected
    player_display = player_override or (
        (shot.get("player_name") or "").strip() or None
    )

    if shot_type == "layup_dunk":
        type_label = "Layup/dunk"
    elif shot_type == "jump_shot":
        if distance >= _THREE_POINT_DISTANCE_FT:
            type_label = f"3PT jumper ({distance:.1f} ft)"
        else:
            type_label = f"Jumper ({distance:.1f} ft)"
    else:
        type_label = "Shot"

    parts = [type_label, "made" if made else "missed"]
    if team_display:
        parts.append(f"— {team_display}")
    if player_display:
        parts.append(player_display)
    elif jersey is not None:
        parts.append(f"#{jersey}")

    return {
        "time": round(timestamp, 2),
        "description": " ".join(parts),
        "thumbnail": f"https://picsum.photos/seed/shot{index}/120/68",
    }


def _all_events() -> tuple[list[dict], list[dict]]:
    """Current video's events, sourced exclusively from Mongo.
    Returns (raw_shots, events) where `events` is the frontend-facing shape
    and `raw_shots` are kept for keyword filtering. Empty lists when the CV
    pipeline hasn't populated the collection yet."""
    shots = fetch_shots()
    roster = get_roster()
    events = [_shot_to_event(s, i + 1, roster=roster) for i, s in enumerate(shots)]
    return shots, events


_THREE_POINT_KEYWORDS = (
    "three pointer",
    "three-pointer",
    "three point",
    "three-point",
    "3 pointer",
    "3-pointer",
    "3-point",
    "3pt",
    "from downtown",
    "beyond the arc",
    "from deep",
)
_MADE_KEYWORDS = ("made", "makes", "scored", "converted", "bucket")
_MISSED_KEYWORDS = ("missed", "miss ", " miss", "bricked", "airball")


def _filter_events_by_query(
    shots: list[dict], events: list[dict], user_query: str
) -> tuple[list[dict], list[int]]:
    """Python-side keyword filter over Mongo shot docs. Returns
    (filtered_events, original_indices) so Gemini's highlights still line up
    with VideoPlayer's full-shot index space."""
    if not user_query or not events:
        return events, list(range(len(events)))

    q = user_query.lower()
    filters: list = []

    if "layup" in q or "dunk" in q or "at the rim" in q:
        filters.append(lambda s: s.get("shot_type") == "layup_dunk")
    elif "jumper" in q or "jump shot" in q:
        filters.append(lambda s: s.get("shot_type") == "jump_shot")

    if any(k in q for k in _THREE_POINT_KEYWORDS):
        filters.append(
            lambda s: float(s.get("distance_feet") or 0) >= _THREE_POINT_DISTANCE_FT
        )

    if any(k in q for k in _MISSED_KEYWORDS):
        filters.append(lambda s: not bool(s.get("made")))
    elif any(k in q for k in _MADE_KEYWORDS):
        filters.append(lambda s: bool(s.get("made")))

    if "celtic" in q or "boston" in q:
        filters.append(
            lambda s: "celtic" in (s.get("team_name") or "").lower()
        )
    if "knick" in q or "new york" in q or "nyk" in q:
        filters.append(
            lambda s: "knick" in (s.get("team_name") or "").lower()
        )

    m = re.search(r"(?:#|\bnumber\b|\bjersey\b)\s*(\d{1,2})", q)
    if m:
        try:
            target = int(m.group(1))
            filters.append(lambda s: s.get("player_number") == target)
        except ValueError:
            pass

    if not filters:
        return events, list(range(len(events)))

    filtered_events: list[dict] = []
    original_indices: list[int] = []
    for idx, (shot, ev) in enumerate(zip(shots, events)):
        if all(f(shot) for f in filters):
            filtered_events.append(ev)
            original_indices.append(idx)

    return filtered_events, original_indices


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
    _shots, events = _all_events()
    return {
        "hasVideo": True,
        "metadata": {
            "duration": duration,
            "title": video.name,
            "url": f"http://localhost:8000/videoSend/{video.name}",
        },
        # Mongo-only — empty list until the CV pipeline writes real shots.
        "timestamps": events,
    }


@app.get("/api/video/timestamps")
async def video_timestamps(duration: float | None = None):
    _shots, events = _all_events()
    return events


@app.get("/api/shots")
async def get_shots():
    return fetch_shots()


@app.get("/api/players")
async def players():
    """Distinct (team, jersey_number) pairs from the current shots collection
    plus the saved roster overrides so the editor can hydrate with both the
    detected data and any user edits."""
    shots = fetch_shots()
    by_team: dict[str, set[int]] = {}
    for s in shots:
        team = (s.get("team_name") or "").strip()
        jersey = s.get("player_number")
        if not team or jersey is None:
            continue
        try:
            by_team.setdefault(team, set()).add(int(jersey))
        except (TypeError, ValueError):
            continue

    teams = [
        {"team_color": team, "jerseys": sorted(js)}
        for team, js in sorted(by_team.items())
    ]
    return {"teams": teams, "roster": get_roster()}


class RosterRequest(BaseModel):
    teams: dict[str, dict] = {}


@app.get("/api/roster")
async def roster_get():
    return get_roster()


@app.put("/api/roster")
async def roster_put(body: RosterRequest):
    save_roster(body.model_dump())
    return get_roster()


@app.post("/videoUpload")
async def videoUpload(
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,
    team_0_name: Annotated[str | None, Form()] = None,
    team_1_name: Annotated[str | None, Form()] = None,
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

    # Lazy import — the Roboflow/torch dependency chain is heavy and optional
    # for everything except the upload path.
    try:
        import basketball_cv.run_model as run_model
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "CV pipeline dependencies not installed. "
                f"Run `pip install -r requirements.txt` in the venv. ({e})"
            ),
        )

    # User-provided team names (from the upload backboard). Blank → None so
    # run_model falls back to the config defaults.
    team_names_override: dict[int, str] = {}
    if team_0_name and team_0_name.strip():
        team_names_override[0] = team_0_name.strip()
    if team_1_name and team_1_name.strip():
        team_names_override[1] = team_1_name.strip()

    shots = run_model.run_model(
        str(dest), str(annotated_dest),
        team_names=team_names_override or None,
    )

    # OpenCV's VideoWriter (used inside run_model) writes FMP4 / MPEG-4 Part 2
    # by default, which browsers can't decode. Re-encode the annotated output
    # in place to H.264/AAC so <video> plays it. Does a tmp-file swap so the
    # original annotated file isn't corrupted if ffmpeg fails.
    tmp_dest = annotated_dest.with_suffix(annotated_dest.suffix + ".h264.tmp.mp4")
    if _transcode_to_h264(annotated_dest, tmp_dest):
        annotated_dest.unlink()
        tmp_dest.rename(annotated_dest)
        print(f"[transcode] annotated video re-encoded to H.264: {annotated_dest.name}")
    else:
        # Leave the raw FMP4 output — browser will show the codec-error overlay
        # but at least the shots data is still good.
        if tmp_dest.exists():
            tmp_dest.unlink()
        print("[transcode] ffmpeg step failed, leaving raw annotated output as-is")

    shot_count = replace_video_session(
        shots,
        source_video=dest.name,
        annotated_video=annotated_dest.name,
    )

    # Auto-snapshot this annotation into the gallery so the user can reload it
    # later without re-running the CV pipeline. Any failure here is logged but
    # does NOT fail the upload — the current session is already live.
    gallery_session_id = None
    try:
        gallery_session_id = _snapshot_to_gallery(
            raw_input=dest,
            annotated_output=annotated_dest,
            title=title or (file.filename or filename),
        )
    except Exception as e:
        print(f"[gallery] snapshot failed ({e.__class__.__name__}: {e})")

    return {
        "message": "uploaded",
        "title": title,
        "original_filename": filename,
        "stored_as": dest.name,
        "annotated_filename": annotated_dest.name,
        "shots_stored": shot_count,
        "content_type": file.content_type,
        "gallery_session_id": gallery_session_id,
    }


def _snapshot_to_gallery(
    *,
    raw_input: Path,
    annotated_output: Path,
    title: str,
) -> str:
    """Archive the current annotation: keep the raw input + thumbnail under
    server/Gallery/<sid>/, store the archived video under server/Annotated/,
    and persist a metadata + shots + roster snapshot to Mongo."""
    session_id = uuid.uuid4().hex
    session_dir = GALLERY_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    input_copy = session_dir / "input.mp4"
    thumb_copy = session_dir / "thumb.jpg"
    archived_output_name = f"{session_id}.mp4"
    archived_output = ANNOTATED_DIR / archived_output_name

    shutil.copy2(raw_input, input_copy)
    shutil.copy2(annotated_output, archived_output)

    duration = _get_video_duration(archived_output)
    thumb_at = max(0.5, duration * 0.1)
    _extract_thumbnail(archived_output, thumb_copy, at_seconds=thumb_at)

    # Pull shots + roster from Mongo as they stand right now — these were just
    # written by `replace_video_session` above.
    current_shots = fetch_shots()
    current_roster = get_roster()

    save_gallery_session(
        session_id=session_id,
        title=title.strip() or f"session-{session_id[:8]}",
        duration_seconds=duration,
        input_video_relpath=f"{session_id}/input.mp4",
        annotated_video_relpath=archived_output_name,
        thumbnail_relpath=f"{session_id}/thumb.jpg",
        shots=current_shots,
        roster=current_roster,
    )
    print(f"[gallery] snapshot saved: {session_id} ({title}, {len(current_shots)} shots)")
    return session_id


@app.get("/videoSend/{filename}")
async def send_video(filename: str):
    video_path = ANNOTATED_DIR / filename

    if not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video Not Found")

    video_path = _ensure_web_playable_video(video_path)

    # Serve as inline video (not a download) so <video> can stream it.
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
    )


# --------------------------------------------------------------------
# Gallery — persistent archive of past annotated sessions.
# --------------------------------------------------------------------


def _gallery_entry_public(entry: dict) -> dict:
    """Shape a gallery doc for the frontend: IDs, URLs, meta — no shots array.
    URLs are server-rooted so the frontend doesn't need to know the filesystem
    layout; both `thumbnail_url` and `video_url` are absolute-from-origin."""
    sid = entry.get("_id") or entry.get("session_id")
    created_at = entry.get("created_at")
    return {
        "session_id": sid,
        "title": entry.get("title") or "",
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
        "duration_seconds": float(entry.get("duration_seconds") or 0),
        "shot_count": int(entry.get("shot_count") or 0),
        "thumbnail_url": f"/api/gallery/{sid}/thumbnail",
        "video_url": f"/api/gallery/{sid}/video",
    }


def _scanned_gallery_entries() -> list[dict]:
    gallery_entries = list_gallery_sessions()
    gallery_by_video = {
        str(entry.get("annotated_video_relpath") or ""): entry
        for entry in gallery_entries
        if entry.get("annotated_video_relpath")
    }
    current_session = fetch_current_session() or {}
    current_shots = fetch_shots()

    scanned: list[dict] = []
    for video_path in sorted(
        ANNOTATED_DIR.glob("*.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        filename = video_path.name
        if filename in gallery_by_video:
            entry = gallery_by_video[filename]
            public = _gallery_entry_public(entry)
            public["video_url"] = f"/videoSend/{filename}"
            scanned.append(public)
            continue

        created_at = datetime.fromtimestamp(
            video_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        shot_count = 0
        if filename == "output.mp4":
            created = current_session.get("processed_at")
            if hasattr(created, "isoformat"):
                created_at = created.isoformat()
            elif created:
                created_at = str(created)
            shot_count = int(current_session.get("shot_count") or len(current_shots))

        scanned.append(
            {
                "session_id": _annotated_session_id(filename),
                "title": filename,
                "created_at": created_at,
                "duration_seconds": _get_video_duration(video_path),
                "shot_count": shot_count,
                "thumbnail_url": f"/api/gallery/annotated/{filename}/thumbnail",
                "video_url": f"/videoSend/{filename}",
            }
        )

    return scanned


@app.get("/api/gallery")
async def gallery_list():
    return _scanned_gallery_entries()


class SaveCurrentRequest(BaseModel):
    title: Optional[str] = None


@app.post("/api/gallery/save-current")
async def gallery_save_current(body: SaveCurrentRequest | None = None):
    """Snapshot the currently-loaded session (Uploads/input.mp4 + Annotated/
    output.mp4 + current Mongo shots + roster) into the gallery without
    re-running the CV pipeline. Use this after an upload that happened before
    the auto-snapshot logic was in place, or to re-save after editing the
    roster. Title falls back to the source filename."""
    annotated = _find_annotated_video()
    if annotated is None:
        raise HTTPException(
            status_code=404,
            detail="No annotated video loaded — upload a clip first.",
        )

    # The raw input lives in UPLOAD_DIR with a matching or related filename.
    # Fall back to any *.mp4 under UPLOAD_DIR; the CV pipeline only keeps one.
    raw_inputs = sorted(UPLOAD_DIR.glob("*.mp4")) if UPLOAD_DIR.exists() else []
    raw_input = raw_inputs[0] if raw_inputs else annotated  # copy the annotated twice if no raw

    title = (body.title if body else None) or annotated.stem or "Saved session"

    try:
        session_id = _snapshot_to_gallery(
            raw_input=raw_input,
            annotated_output=annotated,
            title=title,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gallery snapshot failed: {e.__class__.__name__}: {e}",
        )

    return {"saved": True, "session_id": session_id, "title": title}


@app.get("/api/gallery/{session_id}/thumbnail")
async def gallery_thumbnail(session_id: str):
    thumb_path = GALLERY_DIR / session_id / "thumb.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path=thumb_path, media_type="image/jpeg")


@app.get("/api/gallery/annotated/{filename}/thumbnail")
async def gallery_annotated_thumbnail(filename: str):
    thumb_path = _ensure_annotated_thumbnail(filename)
    if thumb_path is None or not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(path=thumb_path, media_type="image/jpeg")


@app.get("/api/gallery/{session_id}/video")
async def gallery_video(session_id: str):
    entry = get_gallery_session(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Gallery session not found")
    video_name = entry.get("annotated_video_relpath")
    video_path = ANNOTATED_DIR / str(video_name)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Gallery video not found")
    return FileResponse(path=video_path, media_type="video/mp4")


@app.post("/api/gallery/{session_id}/load")
async def gallery_load(session_id: str):
    """Restore a saved session as the current one: Mongo state + the single
    `Uploads/input.mp4` + `Annotated/output.mp4` slots both get replaced with
    the gallery entry's files. The Film page's existing /api/video/info flow
    then picks it up like a fresh upload."""
    filename = _annotated_filename_from_session_id(session_id)
    if filename is not None:
        video_path = ANNOTATED_DIR / filename
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Gallery video not found")

        current_input = UPLOAD_DIR / "input.mp4"
        current_output = ANNOTATED_DIR / "output.mp4"
        if current_input.exists():
            try:
                current_input.unlink()
            except OSError:
                pass
        if filename != "output.mp4":
            if current_output.exists():
                try:
                    current_output.unlink()
                except OSError:
                    pass
            shutil.copy2(video_path, current_output)
            clear_current_session()
        return {
            "loaded": True,
            "session_id": session_id,
            "title": filename,
        }

    entry = load_gallery_session_as_current(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Gallery session not found")

    session_dir = GALLERY_DIR / session_id
    gallery_input = session_dir / "input.mp4"
    gallery_output = ANNOTATED_DIR / str(entry.get("annotated_video_relpath"))
    if not gallery_output.exists():
        raise HTTPException(
            status_code=410,
            detail="Gallery video files missing on disk — entry may be stale",
        )

    # Clear any current file slots before copying so the copy is deterministic
    # regardless of what extension/name the previous upload used.
    for folder in (UPLOAD_DIR, ANNOTATED_DIR):
        if folder.exists():
            for mp4 in folder.glob("*.mp4"):
                try:
                    mp4.unlink()
                except OSError:
                    pass

    shutil.copy2(gallery_output, ANNOTATED_DIR / "output.mp4")
    if gallery_input.exists():
        shutil.copy2(gallery_input, UPLOAD_DIR / "input.mp4")

    print(f"[gallery] loaded session {session_id} into current slots")
    return {
        "loaded": True,
        "session_id": session_id,
        "title": entry.get("title") or "",
    }


@app.delete("/api/gallery/{session_id}")
async def gallery_delete(session_id: str):
    filename = _annotated_filename_from_session_id(session_id)
    if filename is not None:
        removed: list[str] = []
        cached_path = _web_playable_cache_path(ANNOTATED_DIR / filename)
        if filename == "output.mp4":
            clear_current_session()
            if cached_path.exists():
                try:
                    cached_path.unlink()
                except OSError:
                    pass
            for path in (UPLOAD_DIR / "input.mp4", ANNOTATED_DIR / "output.mp4"):
                if path.exists():
                    try:
                        path.unlink()
                        removed.append(str(path))
                    except OSError:
                        pass
        else:
            video_path = ANNOTATED_DIR / filename
            if video_path.exists():
                try:
                    video_path.unlink()
                    removed.append(str(video_path))
                except OSError:
                    pass
            thumb_path = _annotated_thumbnail_path(filename)
            if thumb_path.exists():
                try:
                    thumb_path.unlink()
                except OSError:
                    pass
            if cached_path.exists():
                try:
                    cached_path.unlink()
                except OSError:
                    pass
        return {"deleted": True, "session_id": session_id, "removed": removed}

    entry = get_gallery_session(session_id)
    removed = delete_gallery_session(session_id)
    session_dir = GALLERY_DIR / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    if entry:
        archived_video = ANNOTATED_DIR / str(entry.get("annotated_video_relpath"))
        current_output = ANNOTATED_DIR / "output.mp4"
        if archived_video.exists() and archived_video != current_output:
            try:
                archived_video.unlink()
            except OSError:
                pass
    if not removed:
        raise HTTPException(status_code=404, detail="Gallery session not found")
    return {"deleted": True, "session_id": session_id}


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
    # Pass req.message so the system prompt can pre-filter the shots table
    # against the user's keywords via Mongo.
    system_txt = _build_system_instruction(req.message)
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
    """Clear only the current Uploads/input.mp4 and Annotated/output.mp4 slots.
    Archived gallery copies under server/Annotated remain intact."""
    clear_current_session()
    removed = []
    cached_output = _web_playable_cache_path(ANNOTATED_DIR / "output.mp4")
    if cached_output.exists():
        try:
            cached_output.unlink()
        except OSError:
            pass
    for path in (UPLOAD_DIR / "input.mp4", ANNOTATED_DIR / "output.mp4"):
        if path.exists():
            try:
                path.unlink()
                removed.append(str(path))
            except OSError:
                pass
    return {"removed": removed}
