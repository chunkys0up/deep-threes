import numpy as np
import supervision as sv
from tqdm import tqdm
from typing import List, Tuple

from sports import ConsecutiveValueTracker, TeamClassifier
from .roboflow_client import infer_with_retry
from .config import (
    PLAYER_DETECTION_MODEL_ID,
    NUMBER_RECOGNITION_MODEL_ID,
    PLAYER_CLASS_IDS,
    NUMBER_CLASS_ID,
    PLAYER_DETECTION_MODEL_CONFIDENCE,
    PLAYER_DETECTION_MODEL_IOU_THRESHOLD,
    STRIDE,
    SOURCE_VIDEO_DIRECTORY,
)

def coords_above_threshold(
    matrix: np.ndarray, threshold: float, sort_desc: bool = True
) -> List[Tuple[int, int]]:
    rows, cols = np.where(matrix > threshold)
    pairs = list(zip(rows.tolist(), cols.tolist()))
    if sort_desc:
        pairs.sort(key=lambda p: matrix[p[0], p[1]], reverse=True)
    return pairs


def fit_team_classifier(client) -> Tuple[TeamClassifier, List[np.ndarray]]:
    """Fit the two-cluster jersey classifier and return it alongside the crops
    it was trained on. The crops are reused downstream to guess which NBA
    team each cluster corresponds to via color matching."""
    crops = []

    for video_path in sv.list_files_with_extensions(SOURCE_VIDEO_DIRECTORY, extensions=["mp4", "avi", "mov"]):
        frame_generator = sv.get_video_frames_generator(source_path=video_path, stride=STRIDE)

        for frame in tqdm(frame_generator):
            result = infer_with_retry(client, frame, PLAYER_DETECTION_MODEL_ID)
            if result is None:
                # Skip this training frame entirely — fitting survives losing a few.
                continue
            detections = sv.Detections.from_inference(result)
            detections = detections.with_nms(threshold=PLAYER_DETECTION_MODEL_IOU_THRESHOLD, class_agnostic=True)
            detections = detections[detections.confidence > PLAYER_DETECTION_MODEL_CONFIDENCE]
            detections = detections[np.isin(detections.class_id, PLAYER_CLASS_IDS)]

            # Shrink each player bbox to 40% of its original size before
            # cropping — the resulting patch is jersey+shorts only, no floor
            # or head or referees, which makes the TeamClassifier's embedding
            # space much cleaner. Mirrors the reference Colab; predict-time
            # crops are deliberately left full-size (see classify_teams and
            # run_model.py callback).
            boxes = sv.scale_boxes(xyxy=detections.xyxy, factor=0.4)

            # Filter out zero-area / empty crops before feeding the team
            # classifier — cv2.cvtColor raises on empty input and kills the run.
            for box in boxes:
                crop = sv.crop_image(frame, box)
                if crop is None:
                    continue
                if getattr(crop, "size", 0) == 0:
                    continue
                if crop.shape[0] < 2 or crop.shape[1] < 2:
                    continue
                crops.append(crop)

    if not crops:
        raise RuntimeError(
            "Team classifier found no usable player crops — upload may have "
            "no visible players or detection confidence is too high."
        )

    team_classifier = TeamClassifier(device="cpu")
    team_classifier.fit(crops)
    return team_classifier, crops


def classify_teams(frame: np.ndarray, player_detections: sv.Detections, team_classifier: TeamClassifier) -> sv.Detections:
    if len(player_detections) > 0:
        player_crops = [sv.crop_image(frame, xyxy) for xyxy in player_detections.xyxy]
        player_detections.data["team_id"] = team_classifier.predict(player_crops)
    else:
        player_detections.data["team_id"] = np.array([])
    return player_detections


def recognize_jersey_numbers(
    frame: np.ndarray,
    player_detections: sv.Detections,
    number_validator: ConsecutiveValueTracker,
    client,
) -> ConsecutiveValueTracker:
    frame_h, frame_w, *_ = frame.shape

    result_numbers = infer_with_retry(client, frame, PLAYER_DETECTION_MODEL_ID)
    if result_numbers is None:
        # Missing one OCR frame just means jersey numbers stay uncorroborated
        # for a bit longer — the ConsecutiveValueTracker handles that fine.
        return number_validator
    number_detections = sv.Detections.from_inference(result_numbers)
    number_detections = number_detections[number_detections.class_id == NUMBER_CLASS_ID]
    number_detections.mask = sv.xyxy_to_mask(
        boxes=number_detections.xyxy, resolution_wh=(frame_w, frame_h)
    )

    number_crops = [
        sv.crop_image(frame, xyxy)
        for xyxy in sv.clip_boxes(sv.pad_boxes(xyxy=number_detections.xyxy, px=10, py=10), (frame_w, frame_h))
    ]

    numbers_recognized = []
    for number_crop in number_crops:
        jersey_number_result = infer_with_retry(
            client, number_crop, NUMBER_RECOGNITION_MODEL_ID
        )
        if jersey_number_result is None:
            numbers_recognized.append(None)
            continue
        try:
            numbers_recognized.append(jersey_number_result["response"][">"])
        except (KeyError, TypeError):
            numbers_recognized.append(None)

    if len(player_detections) > 0 and len(number_detections) > 0:
        iou = sv.mask_iou_batch(
            masks_true=player_detections.mask,
            masks_detection=number_detections.mask,
            overlap_metric=sv.OverlapMetric.IOS,
        )

        pairs = coords_above_threshold(iou, 0.5)

        if pairs:
            player_idx_matched, number_idx_matched = zip(*pairs)
            matched_player_tracker_ids = [player_detections.tracker_id[int(i)] for i in player_idx_matched]
            matched_numbers = [numbers_recognized[int(i)] for i in number_idx_matched]
            number_validator.update(tracker_ids=matched_player_tracker_ids, values=matched_numbers)

    return number_validator


def init_number_validator() -> ConsecutiveValueTracker:
    return ConsecutiveValueTracker(n_consecutive=1)


def get_validated_labels(player_detections: sv.Detections, number_validator: ConsecutiveValueTracker) -> List[str]:
    validated_numbers = number_validator.get_validated(tracker_ids=player_detections.tracker_id)
    player_detections.data["label"] = [f"#{num}" if num is not None else "" for num in validated_numbers]
    return validated_numbers
