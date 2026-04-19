"""Match the TeamClassifier's two abstract clusters (0, 1) to real NBA teams.

Pipeline:
 1. Predict cluster ID for each training crop.
 2. Find the MODAL jersey color per crop: k-means cluster the upper-torso
    region's pixels, pick the largest cluster. The mode beats the median
    when the jersey carries a big white/black number on it — the median
    would be pulled toward the number, but the mode sticks with the fabric.
 3. Aggregate the modal colors across all crops in a cluster, take the
    median of those for a stable per-cluster color.
 4. Find the nearest NBA team by RGB distance. Assign greedily so the two
    clusters never collapse to the same team.

Best-effort only. Ambiguous palettes (Bulls/Rockets/Raptors — all red) will
misfire; the user corrects via the jersey editor.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

from .nba_teams import NBA_TEAM_PALETTE


_KMEANS_K = 3
_KMEANS_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 8, 1.0)


def _dominant_jersey_bgr(crop: np.ndarray) -> Optional[np.ndarray]:
    """Pull the MOST-POPULAR color from a jersey crop.

    Assumes the input is already tight — the pipeline feeds us crops from
    `sv.scale_boxes(xyxy=..., factor=0.4)` so the crop is roughly jersey +
    shorts, no floor/head/referee. We drop low-saturation pixels (white
    numbers, skin, court) so hue comes from the fabric, then k-means the
    remaining pixels into 3 clusters and return the centroid of the largest
    cluster — the jersey's modal color. Returns BGR (OpenCV convention)."""
    if crop is None or crop.size == 0:
        return None
    h, w = crop.shape[:2]
    if h < 10 or w < 10:
        return None

    region = crop
    if region.size == 0:
        return None

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    # Drop unsaturated (<40) and extreme-value pixels (shadows / highlights).
    # This cuts out white jersey numbers, skin tones, and court lines so the
    # remaining pixels are (mostly) fabric.
    sat_mask = hsv[:, :, 1] > 40
    val_mask = (hsv[:, :, 2] > 25) & (hsv[:, :, 2] < 240)
    mask = sat_mask & val_mask

    flat = region.reshape(-1, 3)
    flat_mask = mask.reshape(-1)

    # If nearly everything was filtered out (black/white uniform, e.g. Nets
    # or Spurs), fall back to the full region so the achromatic mode still
    # registers against black/white NBA palettes.
    if flat_mask.sum() < 30:
        kept = flat
    else:
        kept = flat[flat_mask]

    kept_f32 = kept.astype(np.float32)
    if len(kept_f32) < _KMEANS_K:
        # Too few pixels to cluster meaningfully — just average them.
        return np.mean(kept_f32, axis=0).astype(np.float64)

    # k-means the pixels. The LARGEST cluster is the modal (most-popular)
    # color of the jersey fabric.
    _, labels, centers = cv2.kmeans(
        kept_f32, _KMEANS_K, None, _KMEANS_CRITERIA, 3, cv2.KMEANS_PP_CENTERS
    )
    counts = np.bincount(labels.flatten(), minlength=_KMEANS_K)
    dominant = int(np.argmax(counts))
    return centers[dominant].astype(np.float64)


def _rank_by_distance(bgr: np.ndarray) -> List[str]:
    """Return NBA team names sorted by RGB distance (closest first).

    Input is BGR; palette is RGB — swap before comparing."""
    rgb = np.array([bgr[2], bgr[1], bgr[0]], dtype=np.float64)
    scored: List[tuple[float, str]] = []
    for name, team_rgb in NBA_TEAM_PALETTE:
        dist = float(np.linalg.norm(rgb - np.array(team_rgb, dtype=np.float64)))
        scored.append((dist, name))
    scored.sort(key=lambda pair: pair[0])
    return [name for _, name in scored]


def identify_nba_teams(
    classifier,
    crops: Sequence[np.ndarray],
    fallback: Optional[Dict[int, str]] = None,
) -> Dict[int, str]:
    """Guess NBA team names for clusters 0 and 1 of a fitted TeamClassifier.

    Returns `{0: "Team A", 1: "Team B"}`. On any failure (no usable crops,
    classifier error, everything too desaturated) returns `fallback` — which
    should be the generic "Team 0"/"Team 1" from config so the pipeline
    never crashes on this optional heuristic.
    """
    if fallback is None:
        fallback = {0: "Team 0", 1: "Team 1"}

    if not crops:
        return dict(fallback)

    try:
        cluster_ids = classifier.predict(list(crops))
    except Exception as e:
        print(f"[team-id] classifier.predict failed, using fallback: {e}")
        return dict(fallback)

    per_cluster: Dict[int, List[np.ndarray]] = {0: [], 1: []}
    for crop, cid in zip(crops, cluster_ids):
        try:
            cid_int = int(cid)
        except (TypeError, ValueError):
            continue
        if cid_int not in per_cluster:
            continue
        bgr = _dominant_jersey_bgr(crop)
        if bgr is None:
            continue
        per_cluster[cid_int].append(bgr)

    result: Dict[int, str] = {}
    assigned: set[str] = set()
    for cid in (0, 1):
        samples = per_cluster[cid]
        if not samples:
            result[cid] = fallback.get(cid, f"Team {cid}")
            continue
        # Each `sample` is already the MODAL color of one crop. Median across
        # crops smooths out per-frame noise (lighting, camera angle, occlusion).
        aggregated_bgr = np.median(np.vstack(samples), axis=0)
        for candidate in _rank_by_distance(aggregated_bgr):
            if candidate not in assigned:
                result[cid] = candidate
                assigned.add(candidate)
                break
        else:
            result[cid] = fallback.get(cid, f"Team {cid}")

    print(
        f"[team-id] auto-detected teams: {result} "
        f"(crops per cluster: 0→{len(per_cluster[0])}, 1→{len(per_cluster[1])})"
    )
    return result
