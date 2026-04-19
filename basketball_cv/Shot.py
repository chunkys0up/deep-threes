from dataclasses import dataclass
from typing import Optional

@dataclass
class Shot:
    x: float
    y: float
    distance: float
    result: bool
    team: int
    timestamp: float        # seconds into the video
    team_color: str         # "Boston Celtics" or "New York Knicks"
    jersey_number: Optional[int]  # None if OCR didn't detect it
    shot_type: str          # "jump_shot" or "layup_dunk"