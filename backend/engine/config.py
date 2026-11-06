"""Sensitivity settings. Body-specific limits are NOT here: they come from calibration."""

SMOOTH_ALPHA = 0.35        # smoothing of per-frame metrics (0..1, higher = less smoothing)
MIN_HOLD_SEC = 0.6         # a state must persist this long before it counts as active
MIN_VIS = 0.5              # minimum landmark visibility to trust a point
MIN_VIS_FACE = 0.4         # minimum visibility for ears / nose
WINDOW_SEC = 3.0           # window used for sway and movement energy

EXTREME_FRACTION = 0.5     # threshold = baseline + 50% of the way to the exaggerated pose
MIN_SEPARATION_STD = 2.0   # exaggerated pose must differ from baseline by >= 2 std
MIN_SAMPLES = 20           # minimum frames needed per calibration stage
SETTLE_SEC = 1.0           # first second of every stage is ignored
MIN_TILT_DEG = 3.0         # never flag a shoulder tilt below this angle

FIDGET_FACTOR = 1.5        # fidget if movement > 1.5 x your 90th percentile while talking
FREEZE_FACTOR = 0.3        # freeze if movement < 30% of your average while talking
FREEZE_MIN_SEC = 8.0       # ... for at least this long
SWAY_FACTOR = 1.5          # sway if side-to-side std > 1.5 x your 90th percentile while talking
SWAY_MIN = 0.08            # ... and at least 8% of shoulder width

OFF_CENTER = 0.20          # shoulders more than 20% of frame width from the center
DIST_RANGE = (0.22, 0.50)  # ideal shoulder width / frame width for upper-body framing
