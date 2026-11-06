import sys
import time

import cv2

from engine.pose_model import create_landmarker, detect, draw
from engine.pose_signals import PoseSignalEngine
from engine.profile import load_profile
from engine.registry import SIGNALS

PROFILE = "engine/profiles/default.json"
try:
    profile = load_profile(PROFILE)
except FileNotFoundError:
    print("No calibration found. Run:  python calibrate.py")
    sys.exit(1)

engine = PoseSignalEngine(profile)
landmarker = create_landmarker()
cap = cv2.VideoCapture(0)
t_start = time.perf_counter()

while True:
    ok, frame = cap.read()
    if not ok:
        print("Camera not found")
        break
    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    lm, wlm = detect(landmarker, frame)
    res = engine.update(lm, wlm, w, h, time.perf_counter() - t_start)
    if lm is not None:
        draw(frame, lm)
    if not res["visible"]:
        cv2.putText(frame, "Shoulders not visible", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    else:
        y = 30
        for s in SIGNALS:
            r = res["signals"][s["id"]]
            if r["active"]:
                color = (0, 220, 0) if s["kind"] == "good" else (0, 140, 255)
            else:
                color = (130, 130, 130)
            extra = r["state"] or ("" if r["value"] is None else f"{r['value']:.2f}")
            cv2.putText(frame, f"{s['en']}  {extra}", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            y += 24
    cv2.imshow("Kinara Live Pose Signals", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
summary = engine.summary()
print(f"\nSession: {summary['total_seconds']}s  (visible {summary['visible_seconds']}s)")
for s in SIGNALS:
    d = summary["signals"][s["id"]]
    if d["seconds"] > 0:
        print(f"  {s['en']:28s} {d['percent']:5.1f}%   episodes={d['episodes']}  longest={d['longest']}s")
