"""Calibration math: turns your recorded stages into personal thresholds."""
import json
import os
from datetime import datetime

import numpy as np

from . import config as C

FLOORS = {"lean_world": 1.0, "lean_proxy": 0.5, "head_fwd": 0.05, "neck": 0.03, "tilt": 1.0, "turn": 0.05}
REQUIRED = {"lean_forward": "lean_forward", "lean_back": "lean_back", "slouch": "slouch_head_fwd",
            "shrug": "shoulder_raise_neck", "tilt": "shoulder_tilt", "turn": "turned_away"}
THRESHOLD_KEYS = ["lean_forward", "lean_back", "slouch_head_fwd", "slouch_neck", "shoulder_raise_neck",
                  "shoulder_tilt", "turned_away", "sway", "fidget", "freeze"]


def _series(samples, key, absval=False):
    out = []
    for s in samples:
        v = s.get(key)
        if v is not None:
            out.append(abs(v) if absval else v)
    return out


def _ms(vals):
    if len(vals) < C.MIN_SAMPLES:
        return None
    a = np.asarray(vals, float)
    return float(a.mean()), float(a.std())


def choose_sources(neutral):
    n = max(len(neutral), 1)
    world = sum(1 for s in neutral if s.get("lean_world") is not None) / n
    ears = sum(1 for s in neutral if s.get("neck_ears") is not None) / n
    return {"lean": "world" if world >= 0.8 else "proxy", "neck": "ears" if ears >= 0.8 else "nose"}


def _thr(base, ext, direction, floor):
    if base is None or ext is None:
        return None
    if (ext[0] - base[0]) * direction < C.MIN_SEPARATION_STD * max(base[1], floor):
        return None
    return base[0] + C.EXTREME_FRACTION * (ext[0] - base[0])


def stage_thresholds(stage, neutral, samples, sources):
    lk = "lean_world" if sources["lean"] == "world" else "lean_proxy"
    nk = "neck_ears" if sources["neck"] == "ears" else "neck_nose"

    def t(key, direction, floor, absval=False):
        return _thr(_ms(_series(neutral, key, absval)), _ms(_series(samples, key, absval)), direction, floor)

    if stage == "lean_forward":
        return {"lean_forward": t(lk, +1, FLOORS[lk])}
    if stage == "lean_back":
        return {"lean_back": t(lk, -1, FLOORS[lk])}
    if stage == "slouch":
        return {"slouch_head_fwd": t("head_fwd", +1, FLOORS["head_fwd"]),
                "slouch_neck": t(nk, -1, FLOORS["neck"])}
    if stage == "shrug":
        return {"shoulder_raise_neck": t(nk, -1, FLOORS["neck"])}
    if stage == "tilt":
        v = t("tilt", +1, FLOORS["tilt"], True)
        return {"shoulder_tilt": None if v is None else max(v, C.MIN_TILT_DEG)}
    if stage == "turn":
        return {"turned_away": t("turn", +1, FLOORS["turn"], True)}
    return {}


def check_stage(stage, neutral, samples, sources):
    """True if this exaggerated pose was distinct enough from your neutral posture."""
    return stage_thresholds(stage, neutral, samples, sources).get(REQUIRED[stage]) is not None


def compute_profile(stage_samples):
    neutral = stage_samples["neutral"]
    sources = choose_sources(neutral)
    th = {k: None for k in THRESHOLD_KEYS}
    for stage in REQUIRED:
        if stage in stage_samples:
            th.update(stage_thresholds(stage, neutral, stage_samples[stage], sources))
    en = _series(stage_samples.get("talk", []), "energy")
    if len(en) >= C.MIN_SAMPLES:
        th["fidget"] = C.FIDGET_FACTOR * float(np.percentile(en, 90))
        th["freeze"] = C.FREEZE_FACTOR * float(np.mean(en))
    sw = _series(stage_samples.get("talk", []), "sway")      # sway while talking, not sitting still
    if len(sw) < C.MIN_SAMPLES:
        sw = _series(neutral, "sway")
    if len(sw) >= C.MIN_SAMPLES:
        th["sway"] = max(C.SWAY_FACTOR * float(np.percentile(sw, 90)), C.SWAY_MIN)
    baseline = {}
    for k in ["w_frac", "w_long", "tilt", "neck_ears", "neck_nose", "head_fwd", "turn", "lean_world", "lean_proxy"]:
        ms = _ms(_series(neutral, k))
        if ms:
            baseline[k] = {"mean": ms[0], "std": ms[1]}
    return {"version": 1, "created": datetime.now().isoformat(timespec="seconds"),
            "sources": sources, "thresholds": th, "baseline": baseline,
            "warnings": [f"{k}: not calibrated" for k, v in th.items() if v is None]}


def save_profile(profile, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def load_profile(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
