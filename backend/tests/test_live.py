"""Live hints: frame protocol, debounce, errors and access control."""
import struct

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from engine import auth, db, live


REAL_SESSION = live.LiveSession


def jpeg(w=64, h=48):
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 120, np.uint8))
    return buf.tobytes()


def frame(t_sec, data=None):
    return struct.pack(">d", t_sec * 1000.0) + (data if data is not None else jpeg())


class StubEngine:
    """Reports the signals in `active` as on, every frame."""
    def __init__(self, active=(), visible=True):
        self.active, self.visible = set(active), visible

    def update(self, lm, wlm, w, h, t):
        if not self.visible:
            return {"visible": False, "signals": {}}
        sig = {s: {"active": s in self.active, "value": None, "state": None} for s in live.HINT_IDS}
        sig["upright"] = {"active": not self.active, "value": None, "state": None}
        return {"visible": True, "signals": sig}

    def summary(self):
        return {}


def session(active=(), visible=True):
    return REAL_SESSION(engine=StubEngine(active, visible), detect_fn=lambda lm, img: (None, None), landmarker=object())


def test_hint_needs_to_hold_before_it_shows_and_lingers_after():
    s = session({"fidget"})
    assert s.process(frame(0.0))["hints"] == []
    assert s.process(frame(1.5))["hints"] == []
    assert s.process(frame(3.1))["hints"] == ["fidget"]
    s.engine.active = set()
    assert s.process(frame(4.0))["hints"] == ["fidget"]          # still within the 2 second linger
    out = s.process(frame(6.0))
    assert out["hints"] == [] and out["good"] is True


def test_at_most_two_hints_and_good_only_when_none():
    s = session({"fidget", "sway", "lean_forward"})
    s.process(frame(0.0))
    out = s.process(frame(3.5))
    assert len(out["hints"]) == 2 and out["good"] is False


def test_not_visible_reports_it_and_resets():
    s = session({"sway"}, visible=False)
    out = s.process(frame(0.0))
    assert out == {"visible": False, "hints": [], "good": False}


def test_bad_frames_are_rejected():
    s = session()
    with pytest.raises(ValueError):
        s.process(b"123")
    with pytest.raises(ValueError):
        s.process(frame(0.0, b"not a jpeg at all"))


def test_big_frames_are_downscaled():
    seen = {}
    s = REAL_SESSION(engine=StubEngine(), detect_fn=lambda lm, img: seen.setdefault("shape", img.shape) and (None, None), landmarker=object())
    s.process(frame(0.0, jpeg(2000, 1000)))
    assert max(seen["shape"][:2]) == live.MAX_SIDE


def test_missing_calibration_raises(monkeypatch):
    def nope(_):
        raise FileNotFoundError()
    monkeypatch.setattr(live, "load_profile", nope)
    with pytest.raises(live.LiveUnavailable) as e:
        REAL_SESSION()
    assert e.value.code == "no_calibration"


@pytest.fixture()
def main_app(tmp_path, monkeypatch):
    monkeypatch.setenv("KINARA_LLM", "none")
    import main
    return main


def test_websocket_round_trip(main_app, monkeypatch):
    monkeypatch.setenv("KINARA_AUTH", "off")
    monkeypatch.setattr(live, "LiveSession", lambda: session({"sway"}))
    with TestClient(main_app.app).websocket_connect("/ws/live") as ws:
        assert ws.receive_json() == {"ready": True}
        ws.send_bytes(frame(0.0)); assert ws.receive_json()["hints"] == []
        ws.send_bytes(frame(3.2)); assert ws.receive_json()["hints"] == ["sway"]
        ws.send_bytes(b"junk"); assert ws.receive_json()["skipped"] is True      # a bad frame doesn't end the stream
        ws.send_bytes(frame(3.5)); assert ws.receive_json()["visible"] is True


def test_websocket_reports_missing_calibration(main_app, monkeypatch):
    monkeypatch.setenv("KINARA_AUTH", "off")
    monkeypatch.setattr(live, "load_profile", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    with TestClient(main_app.app).websocket_connect("/ws/live") as ws:
        assert ws.receive_json() == {"error": "no_calibration"}


def test_websocket_requires_login_when_accounts_are_on(main_app, tmp_path, monkeypatch):
    monkeypatch.setenv("KINARA_AUTH", "on")
    db.reset("sqlite:///" + str(tmp_path / "t.db"))
    c = TestClient(main_app.app)
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/live"):
            pass
    c.post("/api/register", json={"name": "Ali", "email": "ali@x.com", "password": "secret123"})
    monkeypatch.setattr(live, "LiveSession", lambda: session())
    with c.websocket_connect("/ws/live") as ws:
        assert ws.receive_json() == {"ready": True}
    db.reset()
