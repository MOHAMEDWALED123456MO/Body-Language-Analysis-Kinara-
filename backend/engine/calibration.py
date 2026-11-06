"""Guided calibration: you perform a few poses, Kinara learns YOUR limits from them."""
import time

import cv2

from . import config as C
from .pose_model import detect, draw
from .pose_signals import MetricTracker
from .profile import REQUIRED, check_stage, choose_sources, compute_profile

WIN = "Kinara Calibration"
STAGES = [
    ("neutral", "Sit naturally and relax. Look at the camera.", 7),
    ("lean_forward", "Lean toward the camera.", 5),
    ("lean_back", "Lean back, away from the camera.", 5),
    ("slouch", "Slouch: let your head and shoulders collapse forward.", 5),
    ("shrug", "Raise both shoulders up toward your ears.", 5),
    ("tilt", "Drop one shoulder lower than the other.", 5),
    ("turn", "Turn your upper body away from the camera.", 5),
    ("talk", "Talk about your day with your normal hand movement.", 10),
]


def _put(frame, text, y, color=(255, 255, 255), scale=0.75):
    cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def _record(cap, landmarker, text, seconds, idx, total, note):
    """One stage. Returns (samples, visible_ratio) or None if the user quit."""
    tracker = MetricTracker()
    phase, t0 = "wait", 0.0
    samples, valid, seen = [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Camera not found")
        frame = cv2.flip(frame, 1)
        lm, wlm = detect(landmarker, frame)
        h, w = frame.shape[:2]
        now = time.perf_counter()
        if lm is not None:
            draw(frame, lm)
        _put(frame, f"Step {idx}/{total}: {text}", 35, (255, 220, 0))
        if note:
            _put(frame, note, 70, (0, 140, 255), 0.65)
        if phase == "wait":
            _put(frame, "Press SPACE when ready   (Q = quit)", h - 25, (0, 255, 0))
        elif phase == "count":
            left = 3 - (now - t0)
            if left <= 0:
                phase, t0 = "rec", now
            else:
                _put(frame, f"Get ready... {int(left) + 1}", h // 2, (0, 255, 255), 2.0)
        else:
            el = now - t0
            m = tracker.process(lm, wlm, w, h, now) if lm is not None else None
            seen += 1
            valid += m is not None
            if m is not None and el >= C.SETTLE_SEC:
                samples.append(m)
            cv2.rectangle(frame, (20, h - 40), (20 + int((w - 40) * min(el / seconds, 1)), h - 25),
                          (0, 255, 0), -1)
            _put(frame, "Recording - hold it", h - 50, (0, 0, 255))
            if el >= seconds:
                return samples, valid / max(seen, 1)
        cv2.imshow(WIN, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            return None
        if key == 32 and phase == "wait":
            phase, t0 = "count", time.perf_counter()


def run_wizard(cap, landmarker):
    """Runs all stages and returns the personal profile (None if you quit)."""
    samples, neutral, sources, total = {}, None, None, len(STAGES)
    for idx, (name, text, secs) in enumerate(STAGES, 1):
        note = ""
        for _ in (1, 2):                      # one retry if the pose was not clear enough
            res = _record(cap, landmarker, text, secs, idx, total, note)
            if res is None:
                return None
            data, ratio = res
            samples[name] = data
            if ratio < 0.7:
                good, note = False, "I can't see your shoulders well. Move back and improve the light."
            elif name == "neutral":
                neutral, sources = data, choose_sources(data)
                good = len(data) >= C.MIN_SAMPLES
            elif name in REQUIRED:
                good = check_stage(name, neutral, data, sources)
                note = "Not different enough from your neutral pose. Exaggerate it more."
            else:
                good = len(data) >= C.MIN_SAMPLES
                note = "Not enough data. Keep your upper body in view."
            if good:
                break
        if name == "neutral" and not good:
            raise RuntimeError("Could not record a clean neutral pose. Check the camera and light.")
    cv2.destroyWindow(WIN)
    return compute_profile(samples)
