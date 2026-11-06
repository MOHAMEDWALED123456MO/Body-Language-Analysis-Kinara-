"""Signals registry: every pose signal with its type and labels (used by reports and UI)."""

SIGNALS = [
    {"id": "upright",        "kind": "good",      "en": "Upright posture",          "ar": "وقفة/جلسة مستقيمة"},
    {"id": "slouch",         "kind": "attention", "en": "Slouching",                "ar": "انحناء الظهر"},
    {"id": "lean_forward",   "kind": "attention", "en": "Leaning forward",          "ar": "ميل لقدام"},
    {"id": "lean_back",      "kind": "attention", "en": "Leaning back",             "ar": "ميل لورا"},
    {"id": "shoulder_tilt",  "kind": "attention", "en": "Uneven shoulders",         "ar": "ميل الكتفين"},
    {"id": "shoulder_raise", "kind": "attention", "en": "Raised shoulders (tension)", "ar": "رفع الكتفين (توتر)"},
    {"id": "sway",           "kind": "attention", "en": "Body sway",                "ar": "تمايل الجسم"},
    {"id": "fidget",         "kind": "attention", "en": "Excess movement",          "ar": "حركة عصبية زايدة"},
    {"id": "freeze",         "kind": "attention", "en": "Frozen / too still",       "ar": "جمود تام"},
    {"id": "turned_away",    "kind": "attention", "en": "Body turned from camera",  "ar": "الجسم مدار عن الكاميرا"},
    {"id": "distance",       "kind": "attention", "en": "Too close / too far",      "ar": "بُعد أو قُرب من الكاميرا"},
    {"id": "off_center",     "kind": "attention", "en": "Off-center in frame",      "ar": "بعيد عن منتصف الكادر"},
]
IDS = [s["id"] for s in SIGNALS]
ATTENTION_POSTURE = ["slouch", "lean_forward", "lean_back", "shoulder_raise",
                     "shoulder_tilt", "turned_away"]
