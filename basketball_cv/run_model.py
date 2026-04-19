from pathlib import Path
from typing import List

import numpy as np
import supervision as sv

from .roboflow_client import loadClient
from .config import *
from .Shot import Shot
from .KeyPointsSmoother import KeyPointsSmoother
from .jersey_number_team_detection import (
    fit_team_classifier,
    classify_teams,
    recognize_jersey_numbers,
    init_number_validator,
)
from .annotate import (
    euclidean_distance,
    extract_xy,
    extract_class_id,
    triangle_annotator,
    text_annotator,
    triangle_annotator_missed,
    text_annotator_missed,
)

from sports import ViewTransformer
from sports.basketball import ShotEventTracker

CLIENT = loadClient()


def run_model(source_video_path: str, target_video_path: str) -> List[Shot]:
    source = Path(source_video_path)
    target = Path(target_video_path)

    video_info = sv.VideoInfo.from_video_path(str(source))

    team_classifier = fit_team_classifier(CLIENT)

    byte_tracker = sv.ByteTrack(frame_rate=video_info.fps)
    number_validator = init_number_validator()
    shot_event_tracker = ShotEventTracker(
        reset_time_frames=int(video_info.fps * 1.7),
        minimum_frames_between_starts=int(video_info.fps * 0.5),
        cooldown_frames_after_made=int(video_info.fps * 0.5),
    )
    smoother = KeyPointsSmoother(length=3)

    LEFT_BASKET = CONFIG.vertices[CONFIG.left_basket_index]
    RIGHT_BASKET = CONFIG.vertices[CONFIG.right_basket_index]

    team_0_annotator = sv.RichLabelAnnotator(
        font_size=20, color=get_team_color_by_id(0), text_color=sv.Color.BLACK,
        text_offset=(0, -20), text_position=sv.Position.TOP_CENTER,
    )
    team_1_annotator = sv.RichLabelAnnotator(
        font_size=20, color=get_team_color_by_id(1), text_color=sv.Color.WHITE,
        text_offset=(0, -20), text_position=sv.Position.TOP_CENTER,
    )

    shots: List[Shot] = []
    shot_state = {"xy": None, "tracker_id": None}
    image_to_court = None
    court_to_image = None

    def callback(frame: np.ndarray, index: int) -> np.ndarray:
        nonlocal image_to_court, court_to_image

        # 1. Player detection + tracking
        result_players = CLIENT.infer(frame, model_id=PLAYER_DETECTION_MODEL_ID)
        player_detections = sv.Detections.from_inference(result_players)
        player_detections = player_detections.with_nms(
            threshold=PLAYER_DETECTION_MODEL_IOU_THRESHOLD, class_agnostic=True
        )
        player_detections = player_detections[
            player_detections.confidence > PLAYER_DETECTION_MODEL_CONFIDENCE
        ]
        player_detections = player_detections[np.isin(player_detections.class_id, PLAYER_CLASS_IDS)]
        player_detections = byte_tracker.update_with_detections(detections=player_detections)

        frame_h, frame_w, *_ = frame.shape
        player_detections.mask = sv.xyxy_to_mask(
            boxes=player_detections.xyxy, resolution_wh=(frame_w, frame_h)
        )

        # 2. Team classification
        player_detections = classify_teams(frame, player_detections, team_classifier)

        # 3. Jersey number recognition every 5 frames
        if index % 5 == 0:
            recognize_jersey_numbers(frame, player_detections, number_validator, CLIENT)

        # 4. Court detection + view transformers
        court_result = CLIENT.infer(frame, model_id=COURT_DETECTION_MODEL_ID)
        key_points = sv.KeyPoints.from_inference(court_result)
        key_points.xy = smoother.update(
            xy=key_points.xy, confidence=key_points.confidence, conf_threshold=0.5
        )

        key_mask = key_points.confidence[0] > KEYPOINT_CONFIDENCE_THRESHOLD
        have_enough_points = np.count_nonzero(key_mask) >= 4

        if have_enough_points:
            court_vertices_masked = np.array(CONFIG.vertices)[key_mask]
            detected_on_image = key_points[:, key_mask].xy[0]
            image_to_court = ViewTransformer(source=detected_on_image, target=court_vertices_masked)
            court_to_image = ViewTransformer(source=court_vertices_masked, target=detected_on_image)

        # 5. Shot event tracking
        has_jump_shot = len(player_detections[player_detections.class_id == JUMP_SHOT_CLASS_ID]) > 0
        has_layup_dunk = len(player_detections[player_detections.class_id == LAYUP_DUNK_CLASS_ID]) > 0
        has_ball_in_basket = len(player_detections[player_detections.class_id == BALL_IN_BASKET_CLASS_ID]) > 0

        events = shot_event_tracker.update(
            frame_index=index,
            has_jump_shot=has_jump_shot,
            has_layup_dunk=has_layup_dunk,
            has_ball_in_basket=has_ball_in_basket,
        )

        if events and have_enough_points and image_to_court is not None:
            start_events = [e for e in events if e["event"] == "START"]
            made_events = [e for e in events if e["event"] == "MADE"]
            missed_events = [e for e in events if e["event"] == "MISSED"]

            if start_events:
                shot_player_detections = player_detections[
                    (player_detections.class_id == JUMP_SHOT_CLASS_ID)
                    | (player_detections.class_id == LAYUP_DUNK_CLASS_ID)
                ]
                anchors_image = shot_player_detections.get_anchors_coordinates(
                    anchor=sv.Position.BOTTOM_CENTER
                )
                if len(anchors_image) > 0:
                    anchors_court = image_to_court.transform_points(points=anchors_image)
                    shot_state["xy"] = anchors_court[0]
                    shot_state["tracker_id"] = (
                        shot_player_detections.tracker_id[0]
                        if len(shot_player_detections.tracker_id) > 0
                        else None
                    )

            for result, event_list in [(True, made_events), (False, missed_events)]:
                if event_list and shot_state["xy"] is not None and shot_state["tracker_id"] is not None:
                    pos = shot_state["xy"]
                    target_basket = (
                        LEFT_BASKET
                        if euclidean_distance(pos, LEFT_BASKET) < euclidean_distance(pos, RIGHT_BASKET)
                        else RIGHT_BASKET
                    )

                    tid = shot_state["tracker_id"]
                    shot_player_info = player_detections[player_detections.tracker_id == tid]
                    team_id = int(shot_player_info.data["team_id"][0]) if len(shot_player_info) > 0 else 0
                    team_name = TEAM_NAMES.get(team_id, "Unknown")

                    validated = number_validator.get_validated(tracker_ids=[tid])
                    jersey_number = None
                    if validated and validated[0] not in (None, ""):
                        try:
                            jersey_number = int(validated[0])
                        except (ValueError, TypeError):
                            pass

                    shots.append(Shot(
                        x=float(pos[0]),
                        y=float(pos[1]),
                        distance=euclidean_distance(pos, target_basket),
                        result=result,
                        team=team_id,
                        timestamp=index / video_info.fps,
                        team_color=team_name,
                        jersey_number=jersey_number,
                        shot_type=event_list[0].get("type", ""),
                    ))
                    shot_state["xy"] = None
                    shot_state["tracker_id"] = None

        # 6. Annotation
        annotated_frame = frame.copy()

        if len(player_detections) > 0:
            validated_numbers = number_validator.get_validated(
                tracker_ids=player_detections.tracker_id
            )
            player_labels = []
            for i, num in enumerate(validated_numbers):
                team_id = int(player_detections.data["team_id"][i])
                team_name = TEAM_NAMES.get(team_id, "Unknown")
                display_num = f"#{num}" if num not in (None, "") else ""
                player_labels.append(f"{display_num} {team_name}".strip())

            team_0_detections = player_detections[player_detections.data["team_id"] == 0]
            team_1_detections = player_detections[player_detections.data["team_id"] == 1]
            team_0_labels = [player_labels[i] for i in range(len(player_detections)) if player_detections.data["team_id"][i] == 0]
            team_1_labels = [player_labels[i] for i in range(len(player_detections)) if player_detections.data["team_id"][i] == 1]

            annotated_frame = team_0_annotator.annotate(scene=annotated_frame, detections=team_0_detections, labels=team_0_labels)
            annotated_frame = team_1_annotator.annotate(scene=annotated_frame, detections=team_1_detections, labels=team_1_labels)

        if have_enough_points and court_to_image is not None and len(shots) > 0:
            made_shots = [s for s in shots if s.result]
            missed_shots = [s for s in shots if not s.result]

            if len(made_shots) > 0:
                made_xy_image = court_to_image.transform_points(points=extract_xy(made_shots))
                det_made = sv.Detections(
                    xyxy=sv.pad_boxes(np.hstack((made_xy_image, made_xy_image)), px=1, py=1),
                    class_id=extract_class_id(made_shots),
                )
                labels_made = [f"{int(s.distance)} feet" for s in made_shots]
                annotated_frame = triangle_annotator.annotate(scene=annotated_frame, detections=det_made)
                annotated_frame = text_annotator.annotate(scene=annotated_frame, detections=det_made, labels=labels_made)

            if len(missed_shots) > 0:
                missed_xy_image = court_to_image.transform_points(points=extract_xy(missed_shots))
                det_missed = sv.Detections(
                    xyxy=sv.pad_boxes(np.hstack((missed_xy_image, missed_xy_image)), px=1, py=1),
                    class_id=extract_class_id(missed_shots),
                )
                labels_missed = ["missed"] * len(missed_shots)
                annotated_frame = triangle_annotator_missed.annotate(scene=annotated_frame, detections=det_missed)
                annotated_frame = text_annotator_missed.annotate(scene=annotated_frame, detections=det_missed, labels=labels_missed)

        return annotated_frame

    sv.process_video(
        source_path=str(source),
        target_path=str(target),
        callback=callback,
        show_progress=True,
    )

    return shots


if __name__ == "__main__":
    import sys

    ANNOTATED_DIR = Path(__file__).resolve().parent.parent / "server" / "Annotated"
    ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

    source = sys.argv[1] if len(sys.argv) > 1 else str(SOURCE_VIDEO_DIRECTORY / "game.mp4")
    target = sys.argv[2] if len(sys.argv) > 2 else str(ANNOTATED_DIR / (Path(source).stem + "-annotated.mp4"))

    shots = run_model(source_video_path=source, target_video_path=target)
    for shot in shots:
        print(shot)
