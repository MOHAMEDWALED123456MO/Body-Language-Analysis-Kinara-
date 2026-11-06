"""Run the pose signal engine on a video file (same engine as the live mode)."""
import cv2
import numpy as np

from . import config as C
from .pose_model import detect
from .pose_signals import MetricTracker, PoseSignalEngine


def _session_adjustments(frames, w, h, profile):
    """Compare how this video looks with how calibration looked, and re-center the thresholds
    that depend on camera setup (distance and angle). Result: 'relative to your typical posture
    in this video'. Trade-off: a posture held for the whole video becomes its own baseline."""
    src, base = profile["sources"], profile["baseline"]
    neck_key = "neck_ears" if src["neck"] == "ears" else "neck_nose"
    keys = ["lean_proxy", neck_key, "head_fwd"]
    tracker, vals = MetricTracker(), {k: [] for k in keys}
    for t, lm, wlm in frames:
        m = tracker.process(lm, wlm, w, h, t) if lm is not None else None
        if m:
            for k in keys:
                if m.get(k) is not None:
                    vals[k].append(m[k])

    def med(k):
        return float(np.median(vals[k])) if len(vals[k]) >= C.MIN_SAMPLES else None

    adj = {}
    if src["lean"] == "proxy" and base.get("lean_proxy", {}).get("mean", 0) > 0 and med("lean_proxy"):
        adj["lean_scale"] = med("lean_proxy") / base["lean_proxy"]["mean"]
    if neck_key in base and med(neck_key) is not None:
        adj["neck_shift"] = med(neck_key) - base[neck_key]["mean"]
    if "head_fwd" in base and med("head_fwd") is not None:
        adj["head_fwd_shift"] = med("head_fwd") - base["head_fwd"]["mean"]
    return adj


def analyze_video(path, landmarker, profile, target_fps=15, detect_fn=detect,
                  progress=None, auto_baseline=True):
    """Analyze a video file and return the session summary.

    Time comes from the video itself (frame number / fps), so results are the same
    whether the file is 30 seconds or 30 minutes long, and however fast the PC is."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    step = max(1, round(fps / target_fps))

    frames, idx, w, h = [], 0, 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            h, w = frame.shape[:2]
            lm, wlm = detect_fn(landmarker, frame)
            frames.append((idx / fps, lm, wlm))
        idx += 1
        if progress and total and idx % 30 == 0:
            progress(min(idx / total, 1.0))
    cap.release()
    if not frames:
        raise RuntimeError("The video has no readable frames")

    adjust = _session_adjustments(frames, w, h, profile) if auto_baseline else {}
    engine = PoseSignalEngine(profile, adjust=adjust)
    for t, lm, wlm in frames:
        engine.update(lm, wlm, w, h, t)
    summary = engine.summary()
    summary.update({"video": str(path), "video_fps": round(fps, 2),
                    "analyzed_fps": round(fps / step, 2), "frames_analyzed": len(frames),
                    "baseline_adjust": {k: round(v, 3) for k, v in adjust.items()},
                    "frame_size": [w, h]})
    if progress:
        progress(1.0)
    return summary
