from pathlib import Path
from typing import List, Optional

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
from .team_identification import identify_nba_teams
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


SHOT_DISPLAY_DURATION_SECONDS = 2.0


def get_shot_category(distance: float) -> str:
    if distance >= 23.75:
        return "3PT"
    if distance >= 10.0:
        return "Midrange"
    return "Paint"


def run_model(
    source_video_path: str,
    target_video_path: str,
    team_names: dict | None = None,
) -> List[Shot]:
    # Per-run team name overrides. Priority:
    #   1. Explicit `team_names` arg from the caller (user override).
    #   2. NBA team auto-detected from the fitted classifier's jersey colors.
    #   3. Generic "Team 0" / "Team 1" from config as a last resort.
    # The jersey editor on the frontend lets the user correct auto-detection
    # after annotation, so a wrong guess here is non-fatal.
    caller_overrides = dict(team_names) if team_names else {}

    source = Path(source_video_path)
    target = Path(target_video_path)

    video_info = sv.VideoInfo.from_video_path(str(source))
    team_classifier, fit_crops = fit_team_classifier(CLIENT)

    detected_team_names = identify_nba_teams(
        team_classifier, fit_crops, fallback=TEAM_NAMES
    )
    team_names = {**TEAM_NAMES, **detected_team_names, **caller_overrides}
    print(f"[run_model] team_names resolved to: {team_names}")
    byte_tracker = sv.ByteTrack(frame_rate=30)
    number_validator = init_number_validator()
    shot_event_tracker = ShotEventTracker(
        reset_time_frames=int(video_info.fps * 1.7),
        minimum_frames_between_starts=int(video_info.fps * 0.5),
        cooldown_frames_after_made=int(video_info.fps * 0.5),
    )
    smoother = KeyPointsSmoother(length=3)

    LEFT_BASKET_COURT_COORDS = CONFIG.vertices[CONFIG.left_basket_index]
    RIGHT_BASKET_COURT_COORDS = CONFIG.vertices[CONFIG.right_basket_index]

    team_0_annotator = sv.RichLabelAnnotator(
        font_size=20, color=get_team_color_by_id(0), text_color=sv.Color.BLACK,
        text_offset=(0, -20), text_position=sv.Position.TOP_CENTER,
    )
    team_1_annotator = sv.RichLabelAnnotator(
        font_size=20, color=get_team_color_by_id(1), text_color=sv.Color.WHITE,
        text_offset=(0, -20), text_position=sv.Position.TOP_CENTER,
    )

    shots: List[Shot] = []
    shot_in_progress_xy: Optional[np.ndarray] = None
    player_tracker_id_for_shot: Optional[int] = None

    def callback(frame: np.ndarray, index: int) -> np.ndarray:
        nonlocal shots, shot_in_progress_xy, player_tracker_id_for_shot

        current_time_seconds = index / video_info.fps

        # 1. Player detection + tracking
        result_players = CLIENT.infer(frame, model_id=PLAYER_DETECTION_MODEL_ID)
        initial_player_detections = sv.Detections.from_inference(result_players)
        has_jump_shot = len(
            initial_player_detections[
                initial_player_detections.class_id == JUMP_SHOT_CLASS_ID
            ]
        ) > 0
        has_layup_dunk = len(
            initial_player_detections[
                initial_player_detections.class_id == LAYUP_DUNK_CLASS_ID
            ]
        ) > 0
        has_ball_in_basket = len(
            initial_player_detections[
                initial_player_detections.class_id == BALL_IN_BASKET_CLASS_ID
            ]
        ) > 0

        player_detections = initial_player_detections
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
        if len(player_detections) > 0:
            player_crops = [sv.crop_image(frame, xyxy) for xyxy in player_detections.xyxy]
            current_frame_teams = team_classifier.predict(player_crops)
            player_detections.data["team_id"] = current_frame_teams
        else:
            player_detections.data["team_id"] = np.array([])

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

        image_to_court = None
        court_to_image = None
        if have_enough_points:
            court_vertices_masked = np.array(CONFIG.vertices)[key_mask]
            detected_on_image = key_points[:, key_mask].xy[0]
            image_to_court = ViewTransformer(source=detected_on_image, target=court_vertices_masked)
            court_to_image = ViewTransformer(source=court_vertices_masked, target=detected_on_image)

        # 5. Shot event tracking
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
                    shot_in_progress_xy = anchors_court[0]
                    if len(shot_player_detections.tracker_id) > 0:
                        player_tracker_id_for_shot = int(shot_player_detections.tracker_id[0])
                    else:
                        player_tracker_id_for_shot = None

            for result, event_list in ((True, made_events), (False, missed_events)):
                if event_list and shot_in_progress_xy is not None and player_tracker_id_for_shot is not None:
                    distance_to_left = euclidean_distance(
                        shot_in_progress_xy,
                        LEFT_BASKET_COURT_COORDS,
                    )
                    distance_to_right = euclidean_distance(
                        shot_in_progress_xy,
                        RIGHT_BASKET_COURT_COORDS,
                    )

                    if distance_to_left < distance_to_right:
                        target_basket_coords = LEFT_BASKET_COURT_COORDS
                    else:
                        target_basket_coords = RIGHT_BASKET_COURT_COORDS

                    shot_type = event_list[0].get("type", "")
                    shot_player_info = player_detections[
                        player_detections.tracker_id == player_tracker_id_for_shot
                    ]
                    shot_player_team_id = 0
                    shot_player_team_name = "Unknown"
                    shot_player_jersey_number = None

                    if len(shot_player_info) > 0:
                        shot_player_team_id = int(shot_player_info.data["team_id"][0])
                        shot_player_team_name = team_names.get(shot_player_team_id, "Unknown")
                        validated_numbers = number_validator.get_validated(
                            tracker_ids=[player_tracker_id_for_shot]
                        )
                        if validated_numbers and validated_numbers[0] not in (None, ""):
                            try:
                                shot_player_jersey_number = int(validated_numbers[0])
                            except (ValueError, TypeError):
                                pass

                    current_shot_distance = euclidean_distance(
                        start_point=shot_in_progress_xy,
                        end_point=target_basket_coords,
                    )
                    shot_category = get_shot_category(current_shot_distance)

                    shots.append(
                        Shot(
                            x=float(shot_in_progress_xy[0]),
                            y=float(shot_in_progress_xy[1]),
                            distance=current_shot_distance,
                            result=result,
                            team=shot_player_team_id,
                            timestamp=current_time_seconds,
                            team_color=shot_player_team_name,
                            jersey_number=shot_player_jersey_number,
                            shot_type=shot_type,
                            shot_category=shot_category,
                        )
                    )
                    shot_in_progress_xy = None
                    player_tracker_id_for_shot = None

        # 6. Annotation
        annotated_frame = frame.copy()

        if len(player_detections) > 0:
            validated_numbers = number_validator.get_validated(
                tracker_ids=player_detections.tracker_id
            )
            player_labels = []
            for i, num in enumerate(validated_numbers):
                team_id = int(player_detections.data["team_id"][i])
                team_name = team_names.get(team_id, "Unknown")
                display_num = f"#{num}" if num not in (None, "") else ""
                player_labels.append(f"{display_num} {team_name}".strip())

            team_0_detections = player_detections[player_detections.data["team_id"] == 0]
            team_1_detections = player_detections[player_detections.data["team_id"] == 1]
            team_0_labels = [player_labels[i] for i in range(len(player_detections)) if player_detections.data["team_id"][i] == 0]
            team_1_labels = [player_labels[i] for i in range(len(player_detections)) if player_detections.data["team_id"][i] == 1]

            annotated_frame = team_0_annotator.annotate(scene=annotated_frame, detections=team_0_detections, labels=team_0_labels)
            annotated_frame = team_1_annotator.annotate(scene=annotated_frame, detections=team_1_detections, labels=team_1_labels)

        display_shots = [
            shot
            for shot in shots
            if 0 <= (current_time_seconds - shot.timestamp) <= SHOT_DISPLAY_DURATION_SECONDS
        ]

        if have_enough_points and court_to_image is not None and len(display_shots) > 0:
            made_shots = [s for s in display_shots if s.result]
            missed_shots = [s for s in display_shots if not s.result]

            if len(made_shots) > 0:
                made_xy_image = court_to_image.transform_points(points=extract_xy(made_shots))
                det_made = sv.Detections(
                    xyxy=sv.pad_boxes(np.hstack((made_xy_image, made_xy_image)), px=1, py=1),
                    class_id=extract_class_id(made_shots),
                )
                labels_made = [f"{int(s.distance)} ft ({s.shot_category})" for s in made_shots]
                annotated_frame = triangle_annotator.annotate(scene=annotated_frame, detections=det_made)
                annotated_frame = text_annotator.annotate(scene=annotated_frame, detections=det_made, labels=labels_made)

            if len(missed_shots) > 0:
                missed_xy_image = court_to_image.transform_points(points=extract_xy(missed_shots))
                det_missed = sv.Detections(
                    xyxy=sv.pad_boxes(np.hstack((missed_xy_image, missed_xy_image)), px=1, py=1),
                    class_id=extract_class_id(missed_shots),
                )
                labels_missed = [f"MISSED ({s.shot_category})" for s in missed_shots]
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


def _persist_shots_to_mongo(shots: List[Shot]) -> None:
    """Push the run's shots into deep_threes.shots so the web app can read them.
    Silent no-op if Mongo isn't reachable — the pipeline shouldn't break just
    because the DB isn't running."""
    from dataclasses import asdict
    try:
        import pymongo
    except ImportError:
        print("[db] pymongo not installed; skipping Mongo write")
        return
    try:
        client = pymongo.MongoClient(
            "mongodb://localhost:27017/", serverSelectionTimeoutMS=2000
        )
        coll = client["deep_threes"]["shots"]
        # Fresh roster per run — drop this delete if you want append-only history.
        coll.delete_many({})
        if shots:
            coll.insert_many([asdict(s) for s in shots])
        print(f"[db] Wrote {len(shots)} shots → deep_threes.shots")
    except Exception as e:
        print(f"[db] Mongo write skipped ({e.__class__.__name__}: {e})")


if __name__ == "__main__":
    import sys

    ANNOTATED_DIR = Path(__file__).resolve().parent.parent / "server" / "Annotated"
    ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

    source = sys.argv[1] if len(sys.argv) > 1 else str(SOURCE_VIDEO_DIRECTORY / "game.mp4")
    target = sys.argv[2] if len(sys.argv) > 2 else str(ANNOTATED_DIR / (Path(source).stem + "-annotated.mp4"))

    shots = run_model(source_video_path=source, target_video_path=target)
    for shot in shots:
        print(shot)

    _persist_shots_to_mongo(shots)
