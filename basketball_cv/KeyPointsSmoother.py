from collections import deque
from typing import  Optional
import numpy as np

class KeyPointsSmoother:
    def __init__(self, length: int):
        self.length = length
        self.buffer = deque(maxlen=length)

    def update(
        self,
        xy: np.ndarray,
        confidence: Optional[np.ndarray] = None,
        conf_threshold: float = 0.0,
    ) -> np.ndarray:
        if xy.ndim != 3 or xy.shape[0] == 0:
            return xy
        if xy.shape[0] > 1:
            xy = xy[:1]
            if confidence is not None:
                confidence = confidence[:1]

        xy_f = xy.astype(np.float32, copy=True)

        if confidence is not None:
            assert confidence.shape[:2] == xy.shape[:2]
            mask = (confidence >= conf_threshold)[..., None]
            xy_f = np.where(mask, xy_f, np.nan)

        self.buffer.append(xy_f)
        stacked = np.stack(self.buffer, axis=0)

        if np.isnan(stacked).any():
            with np.errstate(invalid="ignore"):
                mean_xy = np.nanmean(stacked, axis=0)
        else:
            mean_xy = stacked.mean(axis=0)

        return mean_xy
