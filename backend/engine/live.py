"""Live hints while recording. The browser sends small camera frames; this runs the same pose signal engine on them
and answers with at most two short hints. Nothing is stored: the full analysis still runs on the finished recording."""
import struct
import threading
import time

import cv2
import numpy as np

from . import jobs
from .profile import load_profile
from .registry import SIGNALS

HINT_IDS = ["lean_forward", "lean_back", "slouch", "shoulder_raise", "shoulder_tilt", "sway", "fidget", "freeze",
            "turned_away", "distance", "off_center"]
SHOW_SEC = 3.0            # a hint must hold this long before it is shown (avoids flicker)
KEEP_SEC = 2.0            # and stays this long after it ends
MAX_SIDE = 960
HEADER = struct.Struct(">d")     # each frame message: 8-byte timestamp in ms, then the JPEG
_lock = threading.Lock()
_landmarker = None


class LiveUnavailable(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _get_landmarker():
    global _landmarker
    with _lock:
        if _landmarker is None:
            _landmarker = jobs.LANDMARKER_FACTORY()
        return _landmarker


class LiveSession:
    def __init__(self, engine=None, detect_fn=None, landmarker=None):
        if engine is None:
            from .pose_signals import PoseSignalEngine
            try:
                engine = PoseSignalEngine(load_profile(jobs.PROFILE_PATH))
            except FileNotFoundError:
                raise LiveUnavailable("no_calibration")
        self.engine = engine
        self.detect = detect_fn or jobs.DETECT_FN
        self._lm = landmarker
        self._on_since, self._last_on, self._shown = {}, {}, []
        self.frames = 0

    def landmarker(self):
        if self._lm is None:
            try:
                self._lm = _get_landmarker()
            except FileNotFoundError:
                raise LiveUnavailable("no_model")
        return self._lm

    def process(self, message: bytes):
        """One frame message -> {'visible': bool, 'hints': [signal ids], 'good': bool}."""
        if len(message) <= HEADER.size:
            raise ValueError("empty frame")
        (t_ms,) = HEADER.unpack_from(message)
        img = cv2.imdecode(np.frombuffer(message, np.uint8, offset=HEADER.size), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("bad jpeg")
        h, w = img.shape[:2]
        if max(h, w) > MAX_SIDE:
            s = MAX_SIDE / max(h, w)
            img = cv2.resize(img, (int(w * s), int(h * s)))
            h, w = img.shape[:2]
        with _lock:
            lm, wlm = self.detect(self.landmarker(), img)
        t = t_ms / 1000.0
        res = self.engine.update(lm, wlm, w, h, t)
        self.frames += 1
        return self._hints(res, t)

    def _hints(self, res, t):
        if not res["visible"]:
            self._on_since.clear()
            return {"visible": False, "hints": [], "good": False}
        sig = res["signals"]
        for sid in HINT_IDS:
            if sig.get(sid, {}).get("active"):
                self._on_since.setdefault(sid, t)
                self._last_on[sid] = t
            else:
                self._on_since.pop(sid, None)
        ready = [s for s in HINT_IDS if s in self._on_since and t - self._on_since[s] >= SHOW_SEC]
        held = [s for s in self._shown if s in self._last_on and t - self._last_on[s] <= KEEP_SEC]
        order = ready + [s for s in held if s not in ready]
        self._shown = order[:2]
        return {"visible": True, "hints": list(self._shown), "good": bool(sig.get("upright", {}).get("active")) and not self._shown}

    def summary(self):
        return self.engine.summary()


def hint_label(sid, lang="en"):
    for s in SIGNALS:
        if s["id"] == sid:
            return s[lang]
    return sid
