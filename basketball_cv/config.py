import os
from pathlib import Path

import supervision as sv

from sports import MeasurementUnit
from sports.basketball import CourtConfiguration, League, draw_court

SOURCE_VIDEO_DIRECTORY = Path(__file__).resolve().parent.parent / "server" / "Uploads"

# Model IDs
PLAYER_DETECTION_MODEL_ID = "basketball-player-detection-3-ycjdo/4"
NUMBER_RECOGNITION_MODEL_ID = "basketball-jersey-numbers-ocr/6"
COURT_DETECTION_MODEL_ID = "basketball-court-detection-2/14"

# Model Classification IDs
BALL_IN_BASKET_CLASS_ID = 1
JUMP_SHOT_CLASS_ID = 5
LAYUP_DUNK_CLASS_ID = 6
NUMBER_CLASS_ID = 2
PLAYER_CLASS_ID = 3
SHOT_CLASS_ID = 5


# Detection thresholds
KEYPOINT_CONFIDENCE_THRESHOLD = 0.5
DETECTION_CONFIDENCE = 0.3
PLAYER_DETECTION_MODEL_CONFIDENCE = 0.3
PLAYER_DETECTION_MODEL_IOU_THRESHOLD = 0.7

# Player class IDs: player, player-in-possession, player-jump-shot, player-layup-dunk, player-shot-block
PLAYER_CLASS_IDS = [3, 4, 5, 6, 7]
JUMP_SHOT_CLASS_ID = 5
LAYUP_DUNK_CLASS_ID = 6
JUMP_SHOT_MIN_CONSECUTIVE_FRAMES = 3
LAYUP_DUNK_MIN_CONSECUTIVE_FRAMES = 3

STRIDE = 30

# Court config
CONFIG = CourtConfiguration(league=League.NBA, measurement_unit=MeasurementUnit.FEET)

COURT_SCALE = 20
COURT_PADDING = 50
COURT_LINE_THICKNESS = 4

court_base = draw_court(
    config=CONFIG,
    scale=COURT_SCALE,
    padding=COURT_PADDING,
    line_thickness=COURT_LINE_THICKNESS,
)

# Colors
TEXT_COLOR = sv.Color.from_hex("#FFFFFF")
MAKE_MISS_COLOR = sv.ColorPalette.from_hex(["#007A33", "#006BB6"])

# Generic defaults — the real team names come in per-upload from the frontend
# ("Home team" / "Away team" inputs on the upload backboard) and override
# these at run-time via `run_model(..., team_names={0: "Warriors", 1: "Suns"})`.
TEAM_NAMES = {
    0: "Team 0",
    1: "Team 1",
}

TEAM_COLORS = {
    "Team 0": "#FFFFFF",
    "Team 1": "#0000FF",
}


def get_team_color(team_name: str) -> sv.Color:
    hex_color = TEAM_COLORS.get(team_name)
    if hex_color is None:
        return sv.Color.WHITE
    return sv.Color.from_hex(hex_color)


def get_team_color_by_id(team_id: int) -> sv.Color:
    return get_team_color(TEAM_NAMES.get(team_id, ""))
