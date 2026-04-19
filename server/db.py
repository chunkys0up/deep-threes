"""Mongo helpers for the Deep Court Analytics shot data.

The CV pipeline writes Shot documents (see basketball-cv/Shot.py) into
`deep_threes.shots`. This module exposes read + keyword-filter helpers that
degrade gracefully — if Mongo isn't reachable or the collection is empty,
callers get [] and the app falls back to placeholder events.
"""

from __future__ import annotations

import os
import re
from typing import Optional

import pymongo
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "deep_threes")
MONGO_SHOTS_COLLECTION = os.environ.get("MONGO_SHOTS_COLLECTION", "shots")

# ServerSelectionTimeoutMS keeps Mongo-down scenarios from hanging requests.
_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
_db = _client[MONGO_DB]
shots_collection = _db[MONGO_SHOTS_COLLECTION]

# Basketball fieldtype knowledge — keep tight + regex-driven so the parser is
# deterministic and costs zero LLM tokens.
_SHOT_TYPE_LAYUP_KEYWORDS = ("layup", "dunk", "at the rim", "finish at the rim")
_SHOT_TYPE_JUMPER_KEYWORDS = ("jumper", "jump shot")
_THREE_POINT_KEYWORDS = (
    "three pointer",
    "three-pointer",
    "three point",
    "three-point",
    "3 pointer",
    "3-pointer",
    "3-point",
    "3pt",
    "deep",
    "from downtown",
    "from long range",
    "beyond the arc",
)
_MADE_KEYWORDS = ("made", "makes", "scored", "bucket", "converted")
_MISSED_KEYWORDS = ("missed", "miss ", " miss", "bricked", "airball")

# Distance threshold (feet) for "three pointer" when shot_type is stored as
# jump_shot or similar. NBA three-point line is 22 ft in corners, 23.75 ft
# elsewhere; 22.0 is a safe lower bound.
_THREE_POINT_DISTANCE_FT = 22.0


def is_mongo_available() -> bool:
    """Quick heartbeat — doesn't block the request on failure."""
    try:
        _client.admin.command("ping")
        return True
    except (ServerSelectionTimeoutError, PyMongoError):
        return False


def query_shots(filters: Optional[dict] = None, limit: int = 500) -> list[dict]:
    """Return shot documents, ordered by timestamp. Empty list on any failure.

    `filters` is a pymongo filter dict. Callers should NOT rely on it — if the
    CV pipeline hasn't written anything yet, you still get [].
    """
    try:
        cursor = (
            shots_collection.find(filters or {})
            .sort("timestamp", 1)
            .limit(limit)
        )
        return list(cursor)
    except (ServerSelectionTimeoutError, PyMongoError) as e:
        print(f"[db] Mongo unavailable ({e.__class__.__name__}); returning []")
        return []
    except Exception as e:
        print(f"[db] Unexpected query failure: {e}")
        return []


def extract_shot_filter(user_query: str) -> dict:
    """Parse a natural-language question into a pymongo filter dict.

    Examples:
      "show me three pointers" → {"distance": {"$gte": 22.0}}
      "missed layups"          → {"$and": [{"shot_type": "layup_dunk"}, {"result": False}]}
      "Celtics buckets by #23" → {"$and": [team, result, jersey]}

    Returns {} if no keywords matched — caller should treat that as "no filter,
    show everything".
    """
    q = (user_query or "").lower()
    if not q:
        return {}

    conds: list[dict] = []

    # Shot type
    if any(k in q for k in _SHOT_TYPE_LAYUP_KEYWORDS):
        conds.append({"shot_type": "layup_dunk"})
    elif any(k in q for k in _SHOT_TYPE_JUMPER_KEYWORDS):
        conds.append({"shot_type": "jump_shot"})

    # Three pointers — distance-based. If the user explicitly says 3pt AND
    # we already pinned shot_type to layup, the query won't match anything;
    # that's fine, it's semantically empty.
    if any(k in q for k in _THREE_POINT_KEYWORDS):
        conds.append({"distance": {"$gte": _THREE_POINT_DISTANCE_FT}})

    # Made / missed
    if any(k in q for k in _MADE_KEYWORDS):
        conds.append({"result": True})
    elif any(k in q for k in _MISSED_KEYWORDS):
        conds.append({"result": False})

    # Team — match on team_color string (stored as "Boston Celtics" / "New York Knicks").
    if "celtic" in q or "boston" in q:
        conds.append({"team_color": {"$regex": "celtic", "$options": "i"}})
    if "knick" in q or "new york" in q or "nyk" in q:
        conds.append({"team_color": {"$regex": "knick", "$options": "i"}})

    # Jersey number — "#23", "number 23", "jersey 23"
    m = re.search(r"(?:#|\bnumber\b|\bjersey\b)\s*(\d{1,2})", q)
    if m:
        try:
            conds.append({"jersey_number": int(m.group(1))})
        except ValueError:
            pass

    if not conds:
        return {}
    if len(conds) == 1:
        return conds[0]
    return {"$and": conds}


def shot_to_event(shot: dict, seed: int = 1) -> dict:
    """Translate a Shot mongo doc into the {time, description, thumbnail}
    shape the frontend seekbar + thumbnails strip consumes.

    `seed` controls the placeholder thumbnail so each shot gets a visually
    distinct image until the CV pipeline provides real frame grabs.
    """
    shot_type = shot.get("shot_type", "")
    distance = float(shot.get("distance") or 0)
    result = bool(shot.get("result"))
    team_color = (shot.get("team_color") or "").strip()
    jersey = shot.get("jersey_number")

    if shot_type == "layup_dunk":
        type_label = "Layup/dunk"
    elif shot_type == "jump_shot":
        if distance >= _THREE_POINT_DISTANCE_FT:
            type_label = f"3PT jumper ({distance:.1f} ft)"
        else:
            type_label = f"Jumper ({distance:.1f} ft)"
    else:
        type_label = "Shot"

    parts = [type_label, "made" if result else "missed"]
    if team_color:
        parts.append(f"— {team_color}")
    if jersey is not None:
        parts.append(f"#{jersey}")

    return {
        "time": round(float(shot.get("timestamp") or 0), 2),
        "description": " ".join(parts),
        "thumbnail": f"https://picsum.photos/seed/shot{seed}/120/68",
    }
