import numpy as np
import supervision as sv
from tqdm import tqdm
from pathlib import Path
from typing import List, Tuple

from sports import ConsecutiveValueTracker, TeamClassifier
from .config import (
    PLAYER_DETECTION_MODEL_ID,
    NUMBER_RECOGNITION_MODEL_ID,
    PLAYER_CLASS_IDS,
    NUMBER_CLASS_ID,
    PLAYER_DETECTION_MODEL_CONFIDENCE,
    PLAYER_DETECTION_MODEL_IOU_THRESHOLD,
    STRIDE,
    SOURCE_VIDEO_DIRECTORY,
    TEAM_CLASSIFIER_MAX_FRAMES,
)

def coords_above_threshold(
    matrix: np.ndarray, threshold: float, sort_desc: bool = True
) -> List[Tuple[int, int]]:
    rows, cols = np.where(matrix > threshold)
    pairs = list(zip(rows.tolist(), cols.tolist()))
    if sort_desc:
        pairs.sort(key=lambda p: matrix[p[0], p[1]], reverse=True)
    return pairs


def fit_team_classifier(client, source_video_path: str | Path | None = None) -> TeamClassifier:
    crops = []
    processed_frames = 0

    if source_video_path is not None:
        video_paths = [str(Path(source_video_path))]
    else:
        video_paths = sv.list_files_with_extensions(
            SOURCE_VIDEO_DIRECTORY,
            extensions=["mp4", "avi", "mov"],
        )

    for video_path in video_paths:
        frame_generator = sv.get_video_frames_generator(source_path=video_path, stride=STRIDE)

        for frame in tqdm(frame_generator):
            if processed_frames >= TEAM_CLASSIFIER_MAX_FRAMES:
                break

            result = client.infer(frame, model_id=PLAYER_DETECTION_MODEL_ID)
            detections = sv.Detections.from_inference(result)
            detections = detections.with_nms(threshold=PLAYER_DETECTION_MODEL_IOU_THRESHOLD, class_agnostic=True)
            detections = detections[detections.confidence > PLAYER_DETECTION_MODEL_CONFIDENCE]
            detections = detections[np.isin(detections.class_id, PLAYER_CLASS_IDS)]
            frame_h, frame_w = frame.shape[:2]
            boxes = sv.clip_boxes(detections.xyxy, resolution_wh=(frame_w, frame_h))

            for xyxy in boxes:
                crop = sv.crop_image(frame, xyxy)
                if crop is not None and crop.size > 0 and crop.shape[0] > 0 and crop.shape[1] > 0:
                    crops.append(crop)

            processed_frames += 1

        if processed_frames >= TEAM_CLASSIFIER_MAX_FRAMES:
            break

    if not crops:
        raise RuntimeError("No valid player crops found for team classification.")

    team_classifier = TeamClassifier(device="cpu")
    team_classifier.fit(crops)
    return team_classifier


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

    result_numbers = client.infer(frame, model_id=PLAYER_DETECTION_MODEL_ID)
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
        jersey_number_result = client.infer(number_crop, model_id=NUMBER_RECOGNITION_MODEL_ID)
        numbers_recognized.append(jersey_number_result["response"][">"])

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
