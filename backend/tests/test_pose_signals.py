import math
import random

from engine import config as C
from engine.pose_signals import MetricTracker, PoseSignalEngine
from engine.profile import compute_profile

FW = FH = 640
FPS = 30


class P:
    def __init__(self, x=0.5, y=0.5, z=0.0, v=1.0):
        self.x, self.y, self.z, self.visibility = x, y, z, v


def make(w=0.2, tilt_dy=0.0, neck=0.45, head_fwd=0.0, turn=0.0, cx=0.5, wrist_dx=0.0, hips=True):
    lm = [P(v=0.0) for _ in range(33)]
    sh_y = 0.6
    lm[11] = P(cx + w / 2, sh_y + tilt_dy / 2, turn * w / 2)
    lm[12] = P(cx - w / 2, sh_y - tilt_dy / 2, -turn * w / 2)
    ear_y = sh_y - neck * w
    lm[7], lm[8] = P(cx + 0.03, ear_y), P(cx - 0.03, ear_y)
    lm[0] = P(cx, ear_y + 0.02, -head_fwd * w)
    lm[13], lm[14] = P(cx + w, 0.75), P(cx - w, 0.75)
    lm[15], lm[16] = P(cx + w + wrist_dx, 0.85), P(cx - w + wrist_dx, 0.85)
    if hips:
        lm[23], lm[24] = P(cx + 0.08, 0.95), P(cx - 0.08, 0.95)
    return lm


def world(lean_deg):
    wl = [P(v=1.0) for _ in range(33)]
    zs = -0.5 * math.tan(math.radians(lean_deg))
    wl[11], wl[12] = P(0.1, -0.5, zs), P(-0.1, -0.5, zs)
    wl[23], wl[24] = P(0.08, 0.0, 0.0), P(-0.08, 0.0, 0.0)
    return wl


def frames(seconds, **kw):
    rnd = random.Random(1)
    lean = kw.pop("lean", 0.0)
    amp = kw.pop("move", 0.0)
    for i in range(int(seconds * FPS)):
        t = i / FPS
        k = dict(kw)
        k["neck"] = k.get("neck", 0.45) + rnd.uniform(-0.004, 0.004)
        k["wrist_dx"] = amp * math.sin(t * 6)
        yield make(**k), world(lean + rnd.uniform(-0.3, 0.3))


def record(seconds, **kw):
    tr, out = MetricTracker(), []
    for i, (lm, wl) in enumerate(frames(seconds, **kw)):
        m = tr.process(lm, wl, FW, FH, i / FPS)
        if m is not None and i / FPS >= C.SETTLE_SEC:
            out.append(m)
    return out


def build_profile():
    return compute_profile({
        "neutral": record(7),
        "lean_forward": record(5, lean=15),
        "lean_back": record(5, lean=-15),
        "slouch": record(5, head_fwd=0.45, neck=0.30),
        "shrug": record(5, neck=0.28),
        "tilt": record(5, tilt_dy=0.03),
        "turn": record(5, turn=0.35),
        "talk": record(10, move=0.03),
    })


def run(engine, seconds, t0=0.0, **kw):
    last = None
    for i, (lm, wl) in enumerate(frames(seconds, **kw)):
        last = engine.update(lm, wl, FW, FH, t0 + i / FPS)
    return last, t0 + seconds


def test_metrics_basic():
    m = MetricTracker().process(make(), world(0), FW, FH, 0.0)
    assert abs(m["w_frac"] - 0.2) < 1e-6
    assert abs(m["tilt"]) < 1e-6
    assert abs(m["neck_ears"] - 0.45) < 1e-6
    assert abs(m["lean_world"]) < 1e-6


def test_tilt_sign_is_orientation_independent():
    a = MetricTracker().process(make(tilt_dy=0.03), None, FW, FH, 0.0)
    b = MetricTracker().process(make(tilt_dy=-0.03), None, FW, FH, 0.0)
    assert abs(abs(a["tilt"]) - abs(b["tilt"])) < 1e-6 and a["tilt"] * b["tilt"] < 0


def test_profile_fully_calibrated():
    p = build_profile()
    assert p["sources"] == {"lean": "world", "neck": "ears"}
    assert all(v is not None for v in p["thresholds"].values()), p["warnings"]


def test_not_distinct_pose_is_not_calibrated():
    p = compute_profile({"neutral": record(7), "lean_forward": record(5, lean=0.2)})
    assert p["thresholds"]["lean_forward"] is None
    assert any("lean_forward" in w for w in p["warnings"])


def test_engine_detects_each_posture():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 3)
    s = r["signals"]
    assert s["upright"]["active"] and not any(s[k]["active"] for k in
        ["slouch", "lean_forward", "lean_back", "shoulder_raise", "shoulder_tilt", "turned_away"])
    cases = {"lean_forward": dict(lean=15), "lean_back": dict(lean=-15),
             "slouch": dict(head_fwd=0.45, neck=0.30), "shoulder_raise": dict(neck=0.28),
             "shoulder_tilt": dict(tilt_dy=0.03), "turned_away": dict(turn=0.35)}
    for name, kw in cases.items():
        r, t = run(eng, 2, t, **kw)
        act = {k for k, v in r["signals"].items() if v["active"]}
        assert name in act, (name, act)
        assert "upright" not in act
        r, t = run(eng, 2, t)
    assert r["signals"]["upright"]["active"]


def test_slouch_and_shrug_are_not_confused():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 2)
    r, t = run(eng, 2, t, head_fwd=0.45, neck=0.30)
    assert r["signals"]["slouch"]["active"] and not r["signals"]["shoulder_raise"]["active"]
    r, t = run(eng, 2, t)
    r, t = run(eng, 2, t, neck=0.28)
    assert r["signals"]["shoulder_raise"]["active"] and not r["signals"]["slouch"]["active"]


def test_short_blip_is_ignored():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 3)
    r, t = run(eng, 0.3, t, lean=15)
    assert not r["signals"]["lean_forward"]["active"]


def test_fidget_freeze_and_distance():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 3, move=0.12, w=0.3)
    assert r["signals"]["fidget"]["active"]
    r, t = run(eng, 14, t, w=0.3)
    assert r["signals"]["freeze"]["active"]
    r, t = run(eng, 2, t, w=0.6)
    assert r["signals"]["distance"]["state"] == "too_close"
    r, t = run(eng, 2, t, w=0.1)
    assert r["signals"]["distance"]["state"] == "too_far"
    r, t = run(eng, 2, t, cx=0.8)
    assert r["signals"]["off_center"]["active"]


def test_not_visible_and_summary():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 3)
    hidden = make()
    hidden[11].visibility = 0.0
    r = eng.update(hidden, None, FW, FH, t)
    assert r["visible"] is False
    r = eng.update(None, None, FW, FH, t + 0.03)
    assert r["visible"] is False
    _, t = run(eng, 4, t + 0.1, lean=15)
    s = eng.summary()
    assert s["signals"]["lean_forward"]["episodes"] == 1
    assert 3.0 < s["signals"]["lean_forward"]["seconds"] < 4.6
    assert s["visible_seconds"] > 6


def test_far_subject_skips_motion_signals():
    eng = PoseSignalEngine(build_profile())
    r, t = run(eng, 3, move=0.12, w=0.12)
    assert r["signals"]["distance"]["state"] == "too_far"
    assert not r["signals"]["fidget"]["active"]
    assert not r["signals"]["sway"]["active"]
    r, t = run(eng, 14, t, w=0.12)
    assert not r["signals"]["freeze"]["active"]
