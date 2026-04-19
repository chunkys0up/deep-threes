from typing import Union, Sequence
import numpy as np
from .Shot import Shot

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
