import json
import os
import sys

from engine.pose_model import create_landmarker
from engine.profile import load_profile
from engine.registry import SIGNALS
from engine.video_runner import analyze_video
from engine import config as C

PROFILE = "engine/profiles/default.json"

if len(sys.argv) < 2:
    print('Usage:  python analyze_video.py "path\\to\\video.mp4"')
    sys.exit(1)
try:
    profile = load_profile(PROFILE)
except FileNotFoundError:
    print("No calibration found. Run:  python calibrate.py")
    sys.exit(1)

path = sys.argv[1]
last = [-1]


def show(p):
    pct = int(p * 100) // 10 * 10
    if pct != last[0]:
        last[0] = pct
        print(f"  analyzing... {pct}%")


summary = analyze_video(path, create_landmarker(), profile, progress=show)

print(f"\nVideo: {summary['total_seconds']}s  (analyzed at {summary['analyzed_fps']} fps, "
      f"shoulders visible {summary['visible_seconds']}s)")
if summary["baseline_adjust"]:
    print("Adjusted to this video's own typical posture:", summary["baseline_adjust"])
print(f"{'Signal':30s}{'%time':>7s}{'episodes':>10s}{'longest':>9s}")
for s in SIGNALS:
    d = summary["signals"][s["id"]]
    print(f"{s['en']:30s}{d['percent']:7.1f}{d['episodes']:10d}{d['longest']:8.1f}s")

# ---- diagnostics: what the video looked like compared with your calibration ----
src, th, base, met = profile["sources"], summary["thresholds"], profile["baseline"], summary["metrics"]
lk = "lean_world" if src["lean"] == "world" else "lean_proxy"
nk = "neck_ears" if src["neck"] == "ears" else "neck_nose"


def f(v):
    return "-" if v is None else f"{v:.2f}"


rows = [
    ("shoulder/frame long side", "w_long", "w_long", f"ok range {C.DIST_RANGE[0]}-{C.DIST_RANGE[1]}"),
    ("lean", lk, lk, f"fwd>={f(th['lean_forward'])}  back<={f(th['lean_back'])}"),
    ("neck height", nk, nk, f"slouch<={f(th['slouch_neck'])}  raise<={f(th['shoulder_raise_neck'])}"),
    ("head forward", "head_fwd", "head_fwd", f"slouch>={f(th['slouch_head_fwd'])}"),
    ("shoulder tilt", "tilt", "tilt", f"|x|>={f(th['shoulder_tilt'])}"),
    ("body turn", "turn", "turn", f"|x|>={f(th['turned_away'])}"),
    ("sway", "sway", None, f"sway>={f(th['sway'])}"),
    ("movement", "energy", None, f"fidget>={f(th['fidget'])}  freeze<={f(th['freeze'])}"),
]
print(f"\nDiagnostics   frame {summary['frame_size'][0]}x{summary['frame_size'][1]}   "
      f"distance seconds {summary['distance_seconds']}")
print(f"{'metric':26s}{'video median (p10..p90)':28s}{'calib mean':>11s}   limits (as applied to this video)")
for name, mk, bk, lim in rows:
    m = met.get(mk)
    vid = "-" if not m else f"{m['median']:.2f} ({m['p10']:.2f}..{m['p90']:.2f})"
    cal = f(base[bk]["mean"]) if bk and bk in base else "-"
    print(f"{name:26s}{vid:28s}{cal:>11s}   {lim}")

os.makedirs("reports", exist_ok=True)
out = os.path.join("reports", os.path.splitext(os.path.basename(path))[0] + ".signals.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)
print("\nFull timeline saved:", out)
