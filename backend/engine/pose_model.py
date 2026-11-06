"""MediaPipe wrapper: create the pose detector, run it on a frame, draw the skeleton."""
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_PATH = "models/pose_landmarker_lite.task"
CONNECTIONS = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24)]
POINTS = [0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24]


def create_landmarker(path=MODEL_PATH):
    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=path),
        running_mode=vision.RunningMode.IMAGE,
    )
    return vision.PoseLandmarker.create_from_options(options)


def detect(landmarker, frame_bgr):
    """Returns (image landmarks, world landmarks) of the first person, or (None, None)."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.pose_landmarks:
        return None, None
    world = result.pose_world_landmarks[0] if result.pose_world_landmarks else None
    return result.pose_landmarks[0], world


def draw(frame, lm):
    h, w = frame.shape[:2]
    pts = {i: (int(lm[i].x * w), int(lm[i].y * h)) for i in POINTS}
    for a, b in CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (255, 200, 0), 2)
    for p in pts.values():
        cv2.circle(frame, p, 5, (0, 0, 255), -1)
