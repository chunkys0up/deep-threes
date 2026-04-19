from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Iterable

import pymongo
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "deep_threes")
SHOTS_COLLECTION_NAME = os.environ.get("MONGO_SHOTS_COLLECTION", "shots")
SESSION_COLLECTION_NAME = os.environ.get("MONGO_SESSION_COLLECTION", "session")

client = pymongo.MongoClient(MONGO_URI)
database = client[MONGO_DB_NAME]
shots_collection = database[SHOTS_COLLECTION_NAME]
session_collection = database[SESSION_COLLECTION_NAME]


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
    return list(
        shots_collection.find({}, {"_id": 0}).sort("timestamp_seconds", pymongo.ASCENDING)
    )
