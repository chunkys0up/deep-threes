import os
import time
from dotenv import load_dotenv
from inference_sdk import InferenceHTTPClient

def loadClient():
    load_dotenv()
    roboflow_api_key = os.environ.get("ROBOFLOW_API_KEY")

    CLIENT = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=roboflow_api_key
    )
    return CLIENT


def infer_with_retry(client, frame, model_id, retries: int = 2, delay: float = 2.0):
    """Call `client.infer(frame, model_id=...)` with a small retry loop.

    Roboflow's serverless endpoint occasionally returns Cloudflare 524 timeouts
    or other 5xx blips — usually a cold start or a brief origin overload — and
    those kill the whole `sv.process_video` loop if we let them propagate.
    We try up to `retries + 1` times with a short sleep between attempts and
    return `None` if every attempt fails. Callers decide how to degrade (skip
    the frame, reuse last state, etc.)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            return client.infer(frame, model_id=model_id)
        except Exception as e:
            last_err = e
            if attempt < retries:
                print(
                    f"[infer] {model_id} attempt {attempt + 1}/{retries + 1} "
                    f"failed ({e.__class__.__name__}); retrying in {delay:.1f}s"
                )
                time.sleep(delay)
    print(
        f"[infer] {model_id} giving up after {retries + 1} attempts: "
        f"{last_err.__class__.__name__}: {last_err}"
    )
    return None


PLAYER_DETECTION_MODEL_ID = "basketball-player-detection-3-ycjdo/4"
NUMBER_RECOGNITION_MODEL_ID = "basketball-jersey-numbers-ocr/6"
COURT_DETECTION_MODEL_ID = "basketball-court-detection-2/14"