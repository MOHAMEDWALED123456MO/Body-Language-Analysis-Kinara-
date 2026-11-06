import cv2
import numpy as np

from engine.profile import compute_profile
from engine.video_runner import analyze_video
from test_pose_signals import FH, FW, build_profile, make, record, world


def write_video(path, seconds, fps=30, size=(FW, FH)):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for _ in range(int(seconds * fps)):
        vw.write(np.zeros((size[1], size[0], 3), np.uint8))
    vw.release()


def fake_detector(lean_from, analyzed_fps, **kw):
    count = [0]

    def detect(_landmarker, _frame):
        t = count[0] / analyzed_fps
        count[0] += 1
        return make(**kw), world(15 if t >= lean_from else 0)
    return detect


def test_video_time_and_episode(tmp_path):
    path = tmp_path / "v.mp4"
    write_video(path, 8)
    s = analyze_video(path, None, build_profile(), target_fps=15,
                      detect_fn=fake_detector(4.0, 15))
    assert 7.5 < s["total_seconds"] < 8.1
    assert s["analyzed_fps"] == 15.0
    lf = s["signals"]["lean_forward"]
    assert lf["episodes"] == 1 and 3.0 < lf["seconds"] < 4.4
    assert 4.0 <= lf["spans"][0][0] <= 4.8


def test_framing_shift_for_different_camera_distance(tmp_path):
    prof = compute_profile({
        "neutral": record(7, hips=False), "lean_forward": record(5, w=0.26, hips=False),
        "lean_back": record(5, w=0.15, hips=False), "talk": record(10, move=0.03, hips=False)})
    assert prof["sources"]["lean"] == "proxy"
    path = tmp_path / "far.mp4"
    write_video(path, 6)
    s = analyze_video(path, None, prof, target_fps=15,
                      detect_fn=fake_detector(99, 15, w=0.32, hips=False))
    assert s["baseline_adjust"]["lean_scale"] > 1.3
    assert s["signals"]["lean_forward"]["episodes"] == 0
    s2 = analyze_video(path, None, prof, target_fps=15, auto_baseline=False,
                       detect_fn=fake_detector(99, 15, w=0.32, hips=False))
    assert s2["signals"]["lean_forward"]["episodes"] == 1


def test_bad_path():
    try:
        analyze_video("nope.mp4", None, build_profile())
    except RuntimeError as e:
        assert "Cannot open" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_diagnostics_are_reported(tmp_path):
    path = tmp_path / "d.mp4"
    write_video(path, 6)
    s = analyze_video(path, None, build_profile(), target_fps=15,
                      detect_fn=fake_detector(99, 15, w=0.3))
    assert s["frame_size"] == [FW, FH]
    assert abs(s["metrics"]["w_frac"]["median"] - 0.3) < 0.01
    assert sum(s["distance_seconds"].values()) > 5
    assert s["distance_seconds"]["ok"] > 5


def test_camera_pitch_difference_is_absorbed(tmp_path):
    prof = build_profile()
    path = tmp_path / "pitch.mp4"
    write_video(path, 6)
    s = analyze_video(path, None, prof, target_fps=15, detect_fn=fake_detector(99, 15, neck=0.30))
    assert s["baseline_adjust"]["neck_shift"] < -0.1
    expected = prof["thresholds"]["shoulder_raise_neck"] + s["baseline_adjust"]["neck_shift"]
    assert abs(s["thresholds"]["shoulder_raise_neck"] - expected) < 0.01
    assert s["signals"]["shoulder_raise"]["episodes"] == 0
    s2 = analyze_video(path, None, prof, target_fps=15, auto_baseline=False,
                       detect_fn=fake_detector(99, 15, neck=0.30))
    assert s2["signals"]["shoulder_raise"]["episodes"] >= 1


def test_portrait_video_distance_is_fair(tmp_path):
    path = tmp_path / "portrait.mp4"
    write_video(path, 6, size=(360, 640))
    s = analyze_video(path, None, build_profile(), target_fps=15,
                      detect_fn=fake_detector(99, 15, w=0.6))
    assert s["frame_size"] == [360, 640]
    assert s["distance_seconds"]["too_close"] < 1 and s["distance_seconds"]["ok"] > 5
