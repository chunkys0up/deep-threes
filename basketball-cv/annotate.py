from Shot import Shot
from typing import Union, Sequence, Optional, List, Tuple
import numpy as np
import supervision as sv
from config import *

# LOOK INTO THIS
TEAM_COLOR_0 = sv.Color.from_hex("#FFFFFF") # White for Boston Celtics
TEAM_COLOR_1 = sv.Color.from_hex("#0000FF") # Blue for New York Knicks

# Define team-specific text annotators
# TEAM_COLOR_0 and TEAM_COLOR_1 are defined in cell 'sDOceuGIp20d'
team_0_text_annotator = sv.RichLabelAnnotator(
    font_size=20,
    color=TEAM_COLOR_0,
    text_color=sv.Color.BLACK,
    text_offset=(0, -20),
    text_position=sv.Position.TOP_CENTER
)

team_1_text_annotator = sv.RichLabelAnnotator(
    font_size=20,
    color=TEAM_COLOR_1,
    text_color=sv.Color.WHITE,
    text_offset=(0, -20),
    text_position=sv.Position.TOP_CENTER
)

triangle_annotator = sv.TriangleAnnotator(
    color=MAKE_MISS_COLOR,
    base=25,
    height=21,
    color_lookup=sv.ColorLookup.CLASS
)
text_annotator = sv.RichLabelAnnotator(
    font_size=60,
    color=MAKE_MISS_COLOR,
    text_color=TEXT_COLOR,
    text_offset=(0, -30),
    color_lookup=sv.ColorLookup.CLASS,
    text_position=sv.Position.TOP_CENTER
)

triangle_annotator_missed = sv.TriangleAnnotator(
    color=sv.Color.from_hex("#850101"),
    base=25,
    height=21,
    color_lookup=sv.ColorLookup.CLASS
)

text_annotator_missed = sv.RichLabelAnnotator(
    font_size=60,
    color=sv.Color.from_hex("#850101"),
    text_color=TEXT_COLOR,
    text_offset=(0, -30),
    color_lookup=sv.ColorLookup.CLASS,
    text_position=sv.Position.TOP_CENTER
)

def euclidean_distance(
    start_point: Union[Sequence[float], np.ndarray],
    end_point: Union[Sequence[float], np.ndarray]
) -> float:
    start_point_array = np.asarray(start_point, dtype=float)
    end_point_array = np.asarray(end_point, dtype=float)

    if start_point_array.shape != (2,) or end_point_array.shape != (2,):
        raise ValueError("Both points must have shape (2,).")

    return float(np.linalg.norm(end_point_array - start_point_array))

def extract_made(shots: list[Shot]):
    return [shot for shot in shots if shot.result]

def extract_xy(shots: list[Shot]):
    return np.array([[shot.x, shot.y] for shot in shots], dtype=float)

def extract_class_id(shots: list[Shot]):
    return np.array([shot.team for shot in shots], dtype=int)

def extract_label(shots: list[Shot]):
    return np.array([f"{shot.distance:.2f} ft" for shot in shots], dtype=str) 