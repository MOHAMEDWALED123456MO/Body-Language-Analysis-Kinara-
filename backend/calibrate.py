import cv2

from engine.calibration import run_wizard
from engine.pose_model import create_landmarker
from engine.profile import save_profile

PROFILE = "engine/profiles/default.json"

cap = cv2.VideoCapture(0)
landmarker = create_landmarker()
try:
    profile = run_wizard(cap, landmarker)
except RuntimeError as e:
    print("Calibration failed:", e)
    profile = None
cap.release()
cv2.destroyAllWindows()

if profile is None:
    print("Calibration was not completed. Nothing was saved.")
else:
    save_profile(profile, PROFILE)
    print("Saved:", PROFILE)
    print("Sources:", profile["sources"])
    for k, v in profile["thresholds"].items():
        print(f"  {k:22s}", "NOT CALIBRATED" if v is None else round(v, 3))
    for w in profile["warnings"]:
        print("WARNING:", w)
