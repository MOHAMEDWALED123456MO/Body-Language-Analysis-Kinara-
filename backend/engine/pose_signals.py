"""Pose signals: per-frame metrics -> calibrated thresholds -> debounced signal states."""
import math
from collections import deque

import numpy as np

from . import config as C
from .registry import IDS, ATTENTION_POSTURE

NOSE, L_EAR, R_EAR = 0, 7, 8
L_SH, R_SH, L_ELB, R_ELB, L_WR, R_WR, L_HIP, R_HIP = 11, 12, 13, 14, 15, 16, 23, 24
TRACKED = [NOSE, L_SH, R_SH, L_ELB, R_ELB, L_WR, R_WR]
LOG_KEYS = ["w_frac", "tilt", "neck_ears", "neck_nose", "head_fwd", "turn", "lean_world",
            "lean_proxy", "mid_x", "sway", "energy", "w_long"]


def _vis(p):
    v = getattr(p, "visibility", None)
    return 1.0 if v is None else v


class MetricTracker:
    """Turns landmarks into normalized metrics. Everything is measured in shoulder-width
    units, so the numbers do not depend on how close you sit to the camera."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._sm = {}
        self._prev = None
        self._energy = deque()
        self._sway = deque()

    def _smooth(self, key, val):
        if val is None:
            return None
        prev = self._sm.get(key)
        new = val if prev is None else prev + C.SMOOTH_ALPHA * (val - prev)
        self._sm[key] = new
        return new

    def process(self, lm, wlm, fw, fh, t):
        ls, rs = lm[L_SH], lm[R_SH]
        if _vis(ls) < C.MIN_VIS or _vis(rs) < C.MIN_VIS:
            self._prev = None
            return None
        xl, yl, xr, yr = ls.x * fw, ls.y * fh, rs.x * fw, rs.y * fh
        W = math.hypot(xl - xr, yl - yr)
        if W < 1:
            return None
        w_frac = W / fw
        dx, dy = xl - xr, yl - yr
        if dx < 0:
            dx, dy = -dx, -dy
        tilt = math.degrees(math.atan2(dy, dx))
        mid_y = (yl + yr) / 2
        mid_x = (ls.x + rs.x) / 2

        neck_ears = None
        if _vis(lm[L_EAR]) >= C.MIN_VIS_FACE and _vis(lm[R_EAR]) >= C.MIN_VIS_FACE:
            neck_ears = (mid_y - (lm[L_EAR].y + lm[R_EAR].y) / 2 * fh) / W
        nose = lm[NOSE]
        nose_ok = _vis(nose) >= C.MIN_VIS_FACE
        neck_nose = (mid_y - nose.y * fh) / W if nose_ok else None
        head_fwd = ((ls.z + rs.z) / 2 - nose.z) / w_frac if nose_ok else None
        turn = (ls.z - rs.z) / w_frac

        lean_world = None
        if wlm is not None and _vis(lm[L_HIP]) >= C.MIN_VIS and _vis(lm[R_HIP]) >= C.MIN_VIS:
            ys = (wlm[L_SH].y + wlm[R_SH].y) / 2
            yh = (wlm[L_HIP].y + wlm[R_HIP].y) / 2
            zs = (wlm[L_SH].z + wlm[R_SH].z) / 2
            zh = (wlm[L_HIP].z + wlm[R_HIP].z) / 2
            if yh - ys > 0.05:
                lean_world = math.degrees(math.atan2(zh - zs, yh - ys))

        cur = {i: (lm[i].x * fw, lm[i].y * fh) for i in TRACKED if _vis(lm[i]) >= C.MIN_VIS}
        if self._prev:
            common = [i for i in cur if i in self._prev]
            if common:
                d = np.mean([math.hypot(cur[i][0] - self._prev[i][0],
                                        cur[i][1] - self._prev[i][1]) for i in common]) / W
                self._energy.append((t, float(d)))
        self._prev = cur
        self._sway.append((t, mid_x * fw / W))
        for dq in (self._energy, self._sway):
            while dq and t - dq[0][0] > C.WINDOW_SEC:
                dq.popleft()

        energy = None
        if len(self._energy) >= 3:
            span = self._energy[-1][0] - self._energy[0][0]
            if span >= 1.0:
                energy = sum(d for _, d in self._energy) / span
        sway = None
        if len(self._sway) >= 10 and self._sway[-1][0] - self._sway[0][0] >= 1.5:
            sway = float(np.std([x for _, x in self._sway]))

        return {
            "t": t,
            "w_frac": self._smooth("w_frac", w_frac),
            "w_long": self._smooth("w_long", W / max(fw, fh)),
            "tilt": self._smooth("tilt", tilt),
            "neck_ears": self._smooth("neck_ears", neck_ears),
            "neck_nose": self._smooth("neck_nose", neck_nose),
            "head_fwd": self._smooth("head_fwd", head_fwd),
            "turn": self._smooth("turn", turn),
            "lean_world": self._smooth("lean_world", lean_world),
            "lean_proxy": self._smooth("lean_proxy", w_frac * 100.0),
            "mid_x": self._smooth("mid_x", mid_x),
            "energy": energy,
            "sway": sway,
        }


class PoseSignalEngine:
    def __init__(self, profile, adjust=None):
        """adjust re-centers thresholds on a video's own typical posture when the camera setup
        differs from calibration: lean_scale (multiplies the lean thresholds, used when lean
        comes from shoulder width), neck_shift and head_fwd_shift (added to those thresholds)."""
        self.p = profile
        self.th = dict(profile["thresholds"])
        adj = adjust or {}
        if adj.get("lean_scale") and profile["sources"]["lean"] == "proxy":
            for k in ("lean_forward", "lean_back"):
                if self.th.get(k) is not None:
                    self.th[k] *= adj["lean_scale"]
        for key, names in (("neck_shift", ("slouch_neck", "shoulder_raise_neck")),
                           ("head_fwd_shift", ("slouch_head_fwd",))):
            if adj.get(key):
                for k in names:
                    if self.th.get(k) is not None:
                        self.th[k] += adj[key]
        src = profile["sources"]
        self.lean_key = "lean_world" if src["lean"] == "world" else "lean_proxy"
        self.neck_key = "neck_ears" if src["neck"] == "ears" else "neck_nose"
        self.tracker = MetricTracker()
        self.reset()

    def reset(self):
        self.tracker.reset()
        self._since = {}
        self._was = {s: False for s in IDS}
        self._start = {}
        self._stats = {s: {"seconds": 0.0, "episodes": 0, "longest": 0.0, "spans": []} for s in IDS}
        self._visible = 0.0
        self._total = 0.0
        self._last_t = None
        self._log = {k: [] for k in LOG_KEYS}
        self._dist_sec = {"too_close": 0.0, "too_far": 0.0, "ok": 0.0}

    def _raw(self, m):
        th = self.th
        lean, neck, hf = m.get(self.lean_key), m.get(self.neck_key), m.get("head_fwd")
        raw, vals = {}, {}

        def has(k):
            return th.get(k) is not None

        raw["lean_forward"] = has("lean_forward") and lean is not None and lean >= th["lean_forward"]
        raw["lean_back"] = has("lean_back") and lean is not None and lean <= th["lean_back"]
        vals["lean_forward"] = vals["lean_back"] = lean

        slouch = (has("slouch_head_fwd") and hf is not None and hf >= th["slouch_head_fwd"]
                  and (not has("slouch_neck") or (neck is not None and neck <= th["slouch_neck"])))
        raw["slouch"] = slouch
        vals["slouch"] = hf
        raw["shoulder_raise"] = (has("shoulder_raise_neck") and neck is not None
                                 and neck <= th["shoulder_raise_neck"] and not slouch)
        vals["shoulder_raise"] = neck

        raw["shoulder_tilt"] = has("shoulder_tilt") and abs(m["tilt"]) >= th["shoulder_tilt"]
        vals["shoulder_tilt"] = m["tilt"]
        raw["turned_away"] = has("turned_away") and abs(m["turn"]) >= th["turned_away"]
        vals["turned_away"] = m["turn"]

        off = m["mid_x"] - 0.5
        raw["off_center"] = abs(off) >= C.OFF_CENTER
        vals["off_center"] = off
        lo, hi = C.DIST_RANGE
        # measured against the frame's long side, so portrait and landscape videos compare fairly
        wl = m["w_long"]
        raw["distance"] = wl > hi or wl < lo
        self._dist_state = "too_close" if wl > hi else "too_far" if wl < lo else "ok"
        vals["distance"] = wl

        # a small (far) subject makes landmark jitter look like motion, so motion signals are skipped there
        small = wl < lo
        raw["sway"] = has("sway") and not small and m["sway"] is not None and m["sway"] >= th["sway"]
        vals["sway"] = m["sway"]
        e = m["energy"]
        raw["fidget"] = has("fidget") and not small and e is not None and e >= th["fidget"]
        raw["freeze"] = has("freeze") and not small and e is not None and e <= th["freeze"]
        vals["fidget"] = vals["freeze"] = e
        return raw, vals

    def _track(self, sid, active, t, dt):
        st = self._stats[sid]
        if active and not self._was[sid]:
            self._start[sid] = self._since[sid]
            st["episodes"] += 1
            st["seconds"] += t - self._since[sid]
        elif active:
            st["seconds"] += dt
        elif self._was[sid]:
            self._close(sid, t)
        self._was[sid] = active

    def _close(self, sid, t):
        st = self._stats[sid]
        start = self._start.pop(sid, t)
        st["longest"] = max(st["longest"], t - start)
        if len(st["spans"]) < 300:
            st["spans"].append((round(start, 2), round(t, 2)))

    def update(self, lm, wlm, fw, fh, t):
        dt = 0.0 if self._last_t is None else min(t - self._last_t, 0.5)
        self._last_t = t
        self._total += dt
        m = self.tracker.process(lm, wlm, fw, fh, t) if lm is not None else None
        if m is None:
            self._since.clear()
            for sid in IDS:
                self._track(sid, False, t, dt)
            return {"visible": False, "signals": {}}
        self._visible += dt
        raw, vals = self._raw(m)
        for k in LOG_KEYS:
            v = m.get(k)
            if v is not None and len(self._log[k]) < 50000:
                self._log[k].append(v)
        self._dist_sec[self._dist_state] += dt
        out = {}
        for sid in IDS:
            if sid == "upright":
                continue
            if raw.get(sid):
                self._since.setdefault(sid, t)
            else:
                self._since.pop(sid, None)
            hold = C.FREEZE_MIN_SEC if sid == "freeze" else C.MIN_HOLD_SEC
            active = bool(raw.get(sid)) and (t - self._since[sid]) >= hold
            self._track(sid, active, t, dt)
            state = self._dist_state if sid == "distance" else None
            out[sid] = {"active": active, "value": vals.get(sid), "state": state}
        upright = not any(out[s]["active"] for s in ATTENTION_POSTURE)
        if upright:
            self._since.setdefault("upright", t)
        else:
            self._since.pop("upright", None)
        self._track("upright", upright, t, dt)
        out["upright"] = {"active": upright, "value": None, "state": None}
        return {"visible": True, "signals": out}

    def summary(self):
        """Per-signal totals for the whole session (feeds scoring and reports)."""
        for sid in IDS:                       # close episodes that are still running
            if self._was[sid] and sid in self._start:
                self._close(sid, self._last_t)
                self._start[sid] = self._last_t
        vis = max(self._visible, 1e-9)
        res = {"total_seconds": round(self._total, 2), "visible_seconds": round(self._visible, 2),
               "signals": {}}
        res["thresholds"] = {k: (None if v is None else round(float(v), 3)) for k, v in self.th.items()}
        res["metrics"] = {}
        for k, vals in self._log.items():
            if len(vals) >= 5:
                a = np.asarray(vals, float)
                res["metrics"][k] = {"median": float(np.median(a)),
                                     "p10": float(np.percentile(a, 10)),
                                     "p90": float(np.percentile(a, 90))}
        res["distance_seconds"] = {k: round(v, 1) for k, v in self._dist_sec.items()}
        for sid, st in self._stats.items():
            res["signals"][sid] = {"seconds": round(st["seconds"], 2),
                                   "percent": round(100 * st["seconds"] / vis, 1),
                                   "episodes": st["episodes"],
                                   "longest": round(st["longest"], 2),
                                   "spans": list(st["spans"])}
        return res
