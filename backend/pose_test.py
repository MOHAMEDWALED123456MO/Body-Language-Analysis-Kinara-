import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# تحميل الموديل
options = vision.PoseLandmarkerOptions(
    base_options=mp_python.BaseOptions(
        model_asset_path="models/pose_landmarker_lite.task"
    ),
    running_mode=vision.RunningMode.IMAGE,
)
landmarker = vision.PoseLandmarker.create_from_options(options)

# الجزء العلوي من الجسم: الكتفين والدراعات والجذع
CONNECTIONS = [
    (11, 12), (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
]
POINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24]

cap = cv2.VideoCapture(0)

while True:
    ok, frame = cap.read()
    if not ok:
        print("Camera not found")
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if result.pose_landmarks:
        h, w = frame.shape[:2]
        landmarks = result.pose_landmarks[0]
        pts = {i: (int(p.x * w), int(p.y * h)) for i, p in enumerate(landmarks)}

        for a, b in CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], (255, 200, 0), 3)
        for i in POINTS:
            cv2.circle(frame, pts[i], 6, (0, 0, 255), -1)

    cv2.imshow("Kinara Pose", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()