import os
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

PLAYER_DETECTION_MODEL_ID = "basketball-player-detection-3-ycjdo/4"
NUMBER_RECOGNITION_MODEL_ID = "basketball-jersey-numbers-ocr/6"
COURT_DETECTION_MODEL_ID = "basketball-court-detection-2/14"