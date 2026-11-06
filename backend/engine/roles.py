"""Scenario-aware scoring: the same measured signals matter differently for an interview, a
presentation, an online meeting or a speech. The practice score is a transparent heuristic:

  for each signal:  severity = min(share of time / reference, 1)      (reference = 30% of the time, 50% for framing)
  component score = 100 - 100 * sum(weight * severity) / sum(weight)   (weights depend on the scenario)
  overall = body and voice components combined with a scenario-specific split

It is a practice aid for tracking progress, not a verdict on the person.
"""
from .audio import VOICE_SIGNALS
from .registry import SIGNALS

SCENARIOS = {
    "general": {"en": "General practice", "ar": "تدريب عام",
                "desc_en": "No specific situation. Everything is weighted evenly.",
                "desc_ar": "من غير موقف معين. كل حاجة بنفس الأهمية.",
                "voice_share": 0.4,
                "w": {}},
    "interview": {"en": "Job interview", "ar": "مقابلة عمل",
                  "desc_en": "Calm, steady, engaged. Restlessness and slouching count most.",
                  "desc_ar": "هادي وثابت ومتفاعل. الحركة العصبية وانحناء الظهر أهم حاجة.",
                  "voice_share": 0.45,
                  "w": {"slouch": 2, "lean_back": 1.5, "lean_forward": 0.3, "shoulder_tilt": 0.7, "shoulder_raise": 2,
                        "sway": 1.5, "fidget": 2, "freeze": 1, "turned_away": 1.5, "distance": 1, "off_center": 1,
                        "quiet_voice": 2, "monotone": 1.5, "long_pause": 1, "fast_speech": 2, "slow_speech": 1}},
    "presentation": {"en": "Presentation", "ar": "عرض تقديمي",
                     "desc_en": "Energy and voice matter. Purposeful movement and pauses are fine.",
                     "desc_ar": "الطاقة والصوت أهم. الحركة المقصودة والوقفات مقبولة.",
                     "voice_share": 0.5,
                     "w": {"slouch": 1.5, "lean_back": 1, "lean_forward": 0.5, "shoulder_tilt": 0.7, "shoulder_raise": 1,
                           "sway": 0.3, "fidget": 0.8, "freeze": 1.5, "turned_away": 0.8, "distance": 0.7, "off_center": 0.5,
                           "quiet_voice": 2, "monotone": 2.5, "long_pause": 0.5, "fast_speech": 2, "slow_speech": 1}},
    "meeting": {"en": "Online meeting", "ar": "اجتماع أونلاين",
                "desc_en": "Camera framing and a clear, steady voice count most.",
                "desc_ar": "وضعك قدام الكاميرا وصوتك الواضح أهم حاجة.",
                "voice_share": 0.4,
                "w": {"slouch": 1, "lean_back": 1.5, "lean_forward": 0.5, "shoulder_tilt": 0.7, "shoulder_raise": 1,
                      "sway": 1, "fidget": 1, "freeze": 0.7, "turned_away": 1.5, "distance": 2, "off_center": 2,
                      "quiet_voice": 2.5, "monotone": 1.5, "long_pause": 0.7, "fast_speech": 1.5, "slow_speech": 0.7}},
    "speech": {"en": "Public speech", "ar": "خطاب أو كلمة",
               "desc_en": "Vocal variety and presence matter most. Pauses give impact.",
               "desc_ar": "تنوع الصوت وحضورك أهم. الوقفات بتدّي تأثير.",
               "voice_share": 0.55,
               "w": {"slouch": 1.5, "lean_back": 1.5, "lean_forward": 0.3, "shoulder_tilt": 0.7, "shoulder_raise": 1,
                     "sway": 0.5, "fidget": 0.7, "freeze": 1.5, "turned_away": 1, "distance": 0.7, "off_center": 0.5,
                     "quiet_voice": 2, "monotone": 3, "long_pause": 0.3, "fast_speech": 1.5, "slow_speech": 1.5}},
}
DEFAULT = "general"

# scenario-specific wording for a flagged signal (falls back to the general tip)
TIP_OVERRIDES = {
    ("interview", "fidget"): ("Interviewers often read restless movement as nerves. Keep your hands calm and use one clear gesture per point.",
                              "المحاور بيقرا الحركة الزايدة كتوتر. خلّي إيديك هادية واستخدم حركة واضحة لكل نقطة."),
    ("interview", "lean_forward"): ("A slight lean forward shows interest in an interview. Just avoid holding it for long.",
                                    "الميل الخفيف لقدام بيبيّن اهتمام في المقابلة. بس متفضلش عليه كتير."),
    ("interview", "shoulder_raise"): ("Raised shoulders read as tension. Breathe out and drop them before you answer.",
                                      "الكتف المرفوع بيبان كتوتر. طلّع نفس ونزّلهم قبل ما تجاوب."),
    ("presentation", "sway"): ("Moving is fine if it is purposeful. Walk to a new spot at a new point, then plant your feet.",
                               "الحركة مقبولة لو مقصودة. امشي لمكان جديد مع نقطة جديدة وبعدين ثبّت رجلك."),
    ("presentation", "long_pause"): ("Pauses can be powerful in a presentation. Keep them short unless you are marking a big point.",
                                     "الوقفة ممكن تكون قوية في العرض. خلّيها قصيرة إلا لو بتشدد على نقطة كبيرة."),
    ("presentation", "monotone"): ("A presentation lives on energy. Change your pitch and pace on the key slide messages.",
                                   "العرض بيعيش على الطاقة. غيّر نغمتك وسرعتك عند الرسايل الأساسية."),
    ("meeting", "distance"): ("On a video call keep your head and shoulders framed like a news presenter, with your eyes near the top third.",
                              "في مكالمة الفيديو خلّي راسك وكتافك في الكادر زي مذيع الأخبار، وعينك قريبة من التلت الأعلى."),
    ("meeting", "off_center"): ("Center yourself in the frame so colleagues see you clearly.",
                                "خلّي نفسك في نص الكادر عشان زمايلك يشوفوك بوضوح."),
    ("meeting", "quiet_voice"): ("On a call a dropping voice gets lost. Keep your volume steady to the end of each sentence.",
                                 "في المكالمة الصوت اللي بيوطّى بيضيع. حافظ على قوة صوتك لآخر الجملة."),
    ("speech", "monotone"): ("A speech lives on vocal variety. Slow down and lower your pitch on key lines, then lift your energy.",
                             "الخطاب بيعيش على تنوع الصوت. بطّئ ونزّل نغمتك عند الجمل المهمة وبعدين ارفع طاقتك."),
    ("speech", "long_pause"): ("A deliberate pause before a key line gives it weight. Make sure it feels chosen, not lost.",
                               "وقفة مقصودة قبل جملة مهمة بتدّيها وزن. اتأكد إنها تبان مختارة مش تايهة."),
}

REF = {"distance": 50, "off_center": 50, "freeze": 40}
DEFAULT_REF = 30.0
BODY_IDS = [s["id"] for s in SIGNALS if s["id"] != "upright"]
VOICE_IDS = [s["id"] for s in VOICE_SIGNALS]
LABEL = {s["id"]: {"en": s["en"], "ar": s["ar"]} for s in SIGNALS + VOICE_SIGNALS}


def clean_scenario(value):
    return value if value in SCENARIOS else DEFAULT


def clean_goal(text):
    return " ".join((text or "").split())[:300]


def weight(scenario, sid):
    return SCENARIOS[clean_scenario(scenario)]["w"].get(sid, 1.0)


def tip_for(scenario, sid, default):
    return TIP_OVERRIDES.get((clean_scenario(scenario), sid), default)


def label_for(score):
    if score >= 85:
        return {"id": "strong", "en": "Strong", "ar": "ممتاز"}
    if score >= 70:
        return {"id": "good", "en": "Good", "ar": "كويس"}
    if score >= 50:
        return {"id": "work", "en": "Needs work", "ar": "محتاج شغل"}
    return {"id": "basics", "en": "Focus on the basics", "ar": "ركّز على الأساسيات"}


def _component(signals, ids, scenario):
    """Returns (score or None, [(signal, severity, weight)])"""
    rows = [(i, signals[i], weight(scenario, i)) for i in ids if signals.get(i)]
    if not rows:
        return None, []
    total_w = sum(w for _, _, w in rows)
    det = []
    for i, d, w in rows:
        sev = min(float(d["percent"]) / REF.get(i, DEFAULT_REF), 1.0)
        det.append((i, sev, w))
    loss = sum(w * sev for _, sev, w in det) / total_w
    return max(0.0, 100.0 * (1.0 - loss)), [(i, sev, w / total_w) for i, sev, w in det]


def compute_score(result, scenario=DEFAULT):
    scenario = clean_scenario(scenario)
    body, body_det = _component(result.get("signals") or {}, BODY_IDS, scenario)
    v = result.get("voice")
    vsig = v.get("signals") if v and not v.get("error") and v.get("overall", {}).get("level_note") != "no_speech" else None
    voice, voice_det = _component(vsig or {}, VOICE_IDS, scenario) if vsig else (None, [])
    if body is None and voice is None:
        return None
    share = SCENARIOS[scenario]["voice_share"] if (voice is not None and body is not None) else (1.0 if body is None else 0.0)
    overall = (body if body is not None else 0.0) * (1 - share) + (voice if voice is not None else 0.0) * share
    lost = []
    for scope, det, s in (("body", body_det, 1 - share), ("voice", voice_det, share)):
        for sid, sev, w in det:
            pts = 100.0 * w * sev * s
            if pts >= 0.5:
                lost.append({"signal": sid, "scope": scope, "label": LABEL[sid], "points": round(pts, 1)})
    lost.sort(key=lambda x: -x["points"])
    return {"overall": round(overall), "body": None if body is None else round(body),
            "voice": None if voice is None else round(voice), "label": label_for(overall),
            "scenario": scenario, "lost": lost[:4]}
