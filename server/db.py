from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Iterable

import pymongo
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "deep_threes")
SHOTS_COLLECTION_NAME = os.environ.get("MONGO_SHOTS_COLLECTION", "shots")
SESSION_COLLECTION_NAME = os.environ.get("MONGO_SESSION_COLLECTION", "session")
ROSTER_COLLECTION_NAME = os.environ.get("MONGO_ROSTER_COLLECTION", "roster")
GALLERY_COLLECTION_NAME = os.environ.get("MONGO_GALLERY_COLLECTION", "gallery_sessions")


client = pymongo.MongoClient(MONGO_URI)
database = client[MONGO_DB_NAME]
shots_collection = database[SHOTS_COLLECTION_NAME]
session_collection = database[SESSION_COLLECTION_NAME]
roster_collection = database[ROSTER_COLLECTION_NAME]
gallery_collection = database[GALLERY_COLLECTION_NAME]


def _shot_to_document(
    shot: Any,
    *,
    source_video: str,
    annotated_video: str,
) -> dict[str, Any]:
    raw = asdict(shot) if is_dataclass(shot) else dict(shot)
    made = bool(raw.get("result"))

    return {
        "timestamp_seconds": float(raw["timestamp"]),
        "distance_feet": float(raw["distance"]),
        "player_number": raw.get("jersey_number"),
        "player_name": None,
        "team_name": raw.get("team_color"),
        "team_id": raw.get("team"),
        "made": made,
        "result": "made" if made else "missed",
        "shot_type": raw.get("shot_type"),
        "court_x": float(raw["x"]),
        "court_y": float(raw["y"]),
        "source_video": source_video,
        "annotated_video": annotated_video,
    }


def replace_video_session(
    shots: Iterable[Any],
    *,
    source_video: str,
    annotated_video: str,
) -> int:
    shot_docs = [
        _shot_to_document(
            shot,
            source_video=source_video,
            annotated_video=annotated_video,
        )
        for shot in shots
    ]

    shots_collection.delete_many({})
    session_collection.delete_many({})

    session_collection.insert_one(
        {
            "source_video": source_video,
            "annotated_video": annotated_video,
            "processed_at": datetime.now(timezone.utc),
            "shot_count": len(shot_docs),
        }
    )

    if shot_docs:
        shots_collection.insert_many(shot_docs)

    return len(shot_docs)


def fetch_shots() -> list[dict[str, Any]]:
    # Return [] when Mongo isn't reachable so API handlers stay responsive.
    try:
        return list(
            shots_collection.find({}, {"_id": 0}).sort(
                "timestamp_seconds", pymongo.ASCENDING)
        )
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] Mongo unavailable ({e.__class__.__name__}); returning []")
        return []


def fetch_current_session() -> dict[str, Any] | None:
    try:
        return session_collection.find_one({}, {"_id": 0})
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] session fetch failed ({e.__class__.__name__}); returning None")
        return None


def clear_current_session() -> None:
    try:
        shots_collection.delete_many({})
        session_collection.delete_many({})
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] session clear failed ({e.__class__.__name__})")


# ---------------------------------------------------------------------------
# Roster — jersey-number → player name + team display name hashmap.
# Single-doc collection keyed by _id="current"; the whole mapping is replaced
# on each save. Shape:
#   {
#     "teams": {
#       "<detected_team_name>": {
#         "display_name": "<user override, falls back to detected>",
#         "players": { "<jersey_number_str>": "<player name>" }
#       },
#       ...
#     }
#   }
# ---------------------------------------------------------------------------
_ROSTER_DOC_ID = "current"


def get_roster() -> dict[str, Any]:
    try:
        doc = roster_collection.find_one({"_id": _ROSTER_DOC_ID})
        if not doc:
            return {"teams": {}}
        doc.pop("_id", None)
        doc.setdefault("teams", {})
        return doc
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] roster fetch failed ({e.__class__.__name__}); returning empty")
        return {"teams": {}}


def save_roster(mapping: dict[str, Any]) -> None:
    teams = mapping.get("teams") if isinstance(mapping, dict) else None
    if not isinstance(teams, dict):
        teams = {}
    cleaned: dict[str, Any] = {"teams": {}}
    for team_name, cfg in teams.items():
        if not isinstance(team_name, str) or not isinstance(cfg, dict):
            continue
        players_raw = cfg.get("players") if isinstance(cfg.get("players"), dict) else {}
        players: dict[str, str] = {}
        for jersey, name in players_raw.items():
            if isinstance(jersey, (str, int)) and isinstance(name, str):
                players[str(jersey)] = name.strip()
        cleaned["teams"][team_name] = {
            "display_name": str(cfg.get("display_name") or "").strip(),
            "players": players,
        }
    try:
        roster_collection.replace_one(
            {"_id": _ROSTER_DOC_ID},
            {"_id": _ROSTER_DOC_ID, **cleaned},
            upsert=True,
        )
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] roster save failed ({e.__class__.__name__})")


def resolve_player(
    team_name: str | None, jersey: int | None, roster: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Given a detected team + jersey, look up (display_team_name, player_name)
    overrides from the roster. Either/both may be None if no override set."""
    if roster is None:
        roster = get_roster()
    teams = roster.get("teams") or {}
    if not team_name or team_name not in teams:
        return None, None
    cfg = teams[team_name]
    display_team = cfg.get("display_name") or None
    player_name = None
    if jersey is not None:
        player_name = (cfg.get("players") or {}).get(str(jersey)) or None
    return display_team, player_name


# ---------------------------------------------------------------------------
# Gallery — persistent archive of past annotated sessions. Every successful
# upload snapshots the current state here so we can reload a video later
# without rerunning the CV pipeline. Mirrors the shape of the "current"
# session (shots + roster), plus metadata for the gallery UI.
# Doc shape (per entry):
#   {
#     "_id": "<uuid hex>",
#     "title": "<user's filename or upload title>",
#     "created_at": datetime,
#     "duration_seconds": float,
#     "shot_count": int,
#     "input_video_relpath": "<sid>/input.mp4",        # under server/Gallery
#     "annotated_video_relpath": "<sid>/output.mp4",
#     "thumbnail_relpath": "<sid>/thumb.jpg",
#     "shots": [ ...full shot docs copied from `shots` coll... ],
#     "roster_snapshot": { "teams": { ... } },
#   }
# ---------------------------------------------------------------------------


def save_gallery_session(
    *,
    session_id: str,
    title: str,
    duration_seconds: float,
    input_video_relpath: str,
    annotated_video_relpath: str,
    thumbnail_relpath: str,
    shots: list[dict[str, Any]],
    roster: dict[str, Any],
) -> None:
    doc = {
        "_id": session_id,
        "title": title,
        "created_at": datetime.now(timezone.utc),
        "duration_seconds": float(duration_seconds),
        "shot_count": len(shots),
        "input_video_relpath": input_video_relpath,
        "annotated_video_relpath": annotated_video_relpath,
        "thumbnail_relpath": thumbnail_relpath,
        "shots": shots,
        "roster_snapshot": roster if isinstance(roster, dict) else {"teams": {}},
    }
    try:
        gallery_collection.replace_one({"_id": session_id}, doc, upsert=True)
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] gallery save failed ({e.__class__.__name__}: {e})")


def list_gallery_sessions() -> list[dict[str, Any]]:
    """Metadata only — excludes the heavy `shots` and `roster_snapshot` arrays
    so the gallery index endpoint stays small. Sorted newest-first."""
    try:
        projection = {
            "shots": 0,
            "roster_snapshot": 0,
        }
        cursor = gallery_collection.find({}, projection).sort(
            "created_at", pymongo.DESCENDING
        )
        return list(cursor)
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] gallery list failed ({e.__class__.__name__}); returning []")
        return []


def get_gallery_session(session_id: str) -> dict[str, Any] | None:
    try:
        return gallery_collection.find_one({"_id": session_id})
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] gallery get failed ({e.__class__.__name__})")
        return None


def delete_gallery_session(session_id: str) -> bool:
    try:
        result = gallery_collection.delete_one({"_id": session_id})
        return result.deleted_count > 0
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] gallery delete failed ({e.__class__.__name__})")
        return False


def load_gallery_session_as_current(session_id: str) -> dict[str, Any] | None:
    """Restore a saved session as the "current" one: shots + session + roster
    collections get overwritten with this entry's snapshot. Returns the full
    gallery doc on success, None if not found or Mongo is down."""
    entry = get_gallery_session(session_id)
    if not entry:
        return None

    try:
        shots_collection.delete_many({})
        session_collection.delete_many({})

        snapshot_shots = entry.get("shots") or []
        if snapshot_shots:
            # Copy shots as independent docs; Mongo adds fresh _id values.
            to_insert = [{k: v for k, v in s.items() if k != "_id"} for s in snapshot_shots]
            shots_collection.insert_many(to_insert)

        session_collection.insert_one(
            {
                "source_video": entry.get("input_video_relpath"),
                "annotated_video": entry.get("annotated_video_relpath"),
                "processed_at": entry.get("created_at") or datetime.now(timezone.utc),
                "shot_count": len(snapshot_shots),
                "gallery_session_id": session_id,
            }
        )

        save_roster(entry.get("roster_snapshot") or {"teams": {}})
        return entry
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] gallery load failed ({e.__class__.__name__}: {e})")
        return None
