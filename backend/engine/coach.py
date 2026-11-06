"""Coach: turns the measured signals into specific, time-stamped advice in Arabic and English.

This part is rule-based on purpose: it is deterministic, instant, works offline and never
invents facts. It only talks about what was measured, as patterns to practice, never as
feelings or honesty. (The chat coach that discusses these results is a separate step.)
"""
from .audio import VOICE_SIGNALS
from .registry import SIGNALS
from .roles import clean_scenario, compute_score, tip_for, weight

LABEL = {s["id"]: {"en": s["en"], "ar": s["ar"]} for s in SIGNALS + VOICE_SIGNALS}
VOICE_IDS = {s["id"] for s in VOICE_SIGNALS}
FRAMING = {"distance", "off_center"}

TIPS = {
    "slouch": ("Your upper back rounded here. Sit or stand tall, lift your chest and keep your head over your shoulders.",
               "ضهرك اتحني هنا. اقعد أو قف مفرود، ارفع صدرك وخلي راسك فوق كتافك."),
    "lean_forward": ("You leaned toward the camera. A small lean shows interest, but holding it can look rushed or tense. Come back to a centered position between points.",
                     "ميّلت ناحية الكاميرا. الميل الخفيف بيدل على اهتمام، بس لو فضل كتير بيبان استعجال أو شد. ارجع لنص الكرسي بين النقاط."),
    "lean_back": ("You leaned back. On camera it can look distant. Bring your weight slightly forward, especially when you make a key point.",
                  "رجعت لورا. قدام الكاميرا ده ممكن يبان بُعد. شيل وزنك لقدام شوية، خصوصاً وانت بتقول نقطة مهمة."),
    "shoulder_tilt": ("One shoulder sat higher than the other. Check your chair or stance and relax both shoulders evenly.",
                      "كتف كان أعلى من التاني. شوف قعدتك أو وقفتك وريّح الكتفين بالتساوي."),
    "shoulder_raise": ("Your shoulders rose toward your ears, a common tension signal. Breathe out slowly and let them drop.",
                       "كتافك طلعت ناحية ودانك، وده بيحصل مع الشد. طلّع نفس بهدوء وسيب كتافك تنزل."),
    "sway": ("Your body swayed from side to side. Plant your feet or settle back into your seat so movement looks deliberate.",
             "جسمك كان بيتمايل يمين وشمال. ثبّت رجلك أو استقر في الكرسي عشان الحركة تبان مقصودة."),
    "fidget": ("You moved a lot here. Choose one or two deliberate gestures and keep the rest of your body settled.",
               "اتحركت كتير هنا. اختار حركة أو اتنين مقصودين وسيب باقي جسمك هادي."),
    "freeze": ("You stayed completely still for a long stretch. Add natural gestures or small head movements to look engaged.",
               "فضلت ثابت تماماً فترة طويلة. زوّد حركات إيد طبيعية أو حركة راس خفيفة عشان تبان متفاعل."),
    "turned_away": ("Your body turned away from the camera. Face it with your shoulders to look open and engaged.",
                    "جسمك لف بعيد عن الكاميرا. واجهها بكتافك عشان تبان مفتوح ومتفاعل."),
    "distance": ("You were often too close or too far from the camera. Keep your head and shoulders filling about a third of the frame.",
                 "كنت كتير قريب أو بعيد عن الكاميرا. خلّي راسك وكتافك ياخدوا حوالي تلت الكادر."),
    "off_center": ("You drifted to the side of the frame. Keep your head and shoulders near the middle.",
                   "ابتعدت عن نص الكادر. خلّي راسك وكتافك قريبين من النص."),
    "quiet_voice": ("Your voice dropped here. Take a breath and finish sentences at the same volume you started them.",
                    "صوتك وطّى هنا. خد نفس وخلّص الجمل بنفس القوة اللي بدأت بيها."),
    "monotone": ("Your pitch stayed flat. Lift your pitch or slow down on the key words so they stand out.",
                 "نغمة صوتك فضلت ثابتة. ارفع النغمة أو بطّئ عند الكلمات المهمة عشان تبرز."),
    "long_pause": ("A long silence here. Short pauses are powerful, but past two seconds they can feel like a lost thread. Breathe and continue, or use a linking phrase.",
                   "سكوت طويل هنا. الوقفة القصيرة قوية، لكن أكتر من ثانيتين ممكن تبان إنك تهت. خد نفس وكمّل، أو استخدم جملة ربط."),
    "fast_speech": ("You sped up here. Slow down on important points and let each sentence land.",
                    "سرّعت هنا. بطّئ عند النقاط المهمة وسيب كل جملة توصل."),
    "slow_speech": ("Your pace dropped here. Speed up slightly to keep the energy.",
                    "سرعتك قلّت هنا. زوّدها شوية عشان تحافظ على الطاقة."),
}

# voice signal + body signal happening together: (voice, body) -> (en, ar)
COMBINED = {
    ("quiet_voice", "lean_back"): ("Your voice dropped while you leaned back. Posture supports breath: sit tall before the next sentence.",
                                   "صوتك وطّى وانت راجع لورا. الوقفة بتساند النفس: اقعد مفرود قبل الجملة الجاية."),
    ("quiet_voice", "slouch"): ("Your voice dropped while your back rounded. Open your chest to get your volume back.",
                                "صوتك وطّى وضهرك محني. افتح صدرك عشان صوتك يرجع."),
    ("fast_speech", "fidget"): ("You sped up while moving a lot, which can look like rushing. Pause, breathe and slow both down.",
                                "سرّعت كلامك وانت بتتحرك كتير، وده بيبان استعجال. وقّف، خد نفس وهدّي الاتنين."),
    ("fast_speech", "shoulder_raise"): ("You sped up while your shoulders rose. Drop your shoulders and slow your pace together.",
                                        "سرّعت وكتافك طالعة. نزّل كتافك وهدّي سرعتك مع بعض."),
    ("monotone", "freeze"): ("A flat voice together with stillness reads as low energy. Add a gesture and vary your pitch on the next point.",
                             "صوت ثابت مع جمود في الجسم بيبان كطاقة قليلة. زوّد حركة وغيّر نغمتك في النقطة الجاية."),
    ("monotone", "slouch"): ("A flat voice with a rounded back reads as low energy. Sit tall and add emphasis.",
                             "صوت ثابت مع ضهر محني بيبان كطاقة قليلة. اقعد مفرود وزوّد التشديد."),
    ("long_pause", "freeze"): ("You paused and froze together. Keep a small movement or a breath going so the pause looks intentional.",
                               "وقفت عن الكلام وجسمك اتجمد معاه. حافظ على حركة صغيرة أو نفس عشان الوقفة تبان مقصودة."),
    ("long_pause", "turned_away"): ("You paused while turned away from the camera. Face it again before you continue.",
                                    "سكتّ وانت لافف بعيد عن الكاميرا. واجهها تاني قبل ما تكمّل."),
}


def _tip(scenario, sid):
    en, ar = tip_for(scenario, sid, TIPS[sid])
    return {"en": en, "ar": ar}


def _overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])


def _said(segments, span, limit=160):
    out = [s["text"] for s in segments if _overlap((s["start"], s["end"]), span) > 0.3]
    txt = " ".join(out).strip()
    return txt if len(txt) <= limit else txt[:limit].rstrip() + "…"


def _signals(result):
    body = dict(result.get("signals") or {})
    v = result.get("voice")
    voice = dict(v["signals"]) if v and not v.get("error") and v.get("signals") else {}
    return body, voice


def _worth(d):
    return d and d["longest"] >= 2.0 and (d["percent"] >= 2.0 or d["longest"] >= 4.0)


def _priority(d):
    return min(d["percent"], 100) * 0.6 + min(d["longest"], 30) + min(d["episodes"], 10) * 0.5


def build_advice(result, scenario="general"):
    scenario = clean_scenario(scenario)
    body, voice = _signals(result)
    allsig = {**body, **voice}
    v = result.get("voice") or {}
    segments = ((v.get("transcript") or {}).get("segments")) or []

    issues = []
    for sid, tip in TIPS.items():
        d = allsig.get(sid)
        if sid in ("upright",) or not _worth(d):
            continue
        spans = sorted([s for s in d["spans"] if s[1] - s[0] >= 2.0], key=lambda s: s[0] - s[1])
        if not spans:
            continue
        issues.append({"signal": sid, "kind": "voice" if sid in VOICE_IDS else "body",
                       "percent": d["percent"], "episodes": d["episodes"], "longest": d["longest"],
                       "priority": _priority(d) * (0.3 if sid in FRAMING else 1.0) * max(weight(scenario, sid), 0.2),
                       "spans": spans})
    issues.sort(key=lambda i: -i["priority"])

    summary = []
    for i in issues[:3]:
        a, b = i["spans"][0]
        summary.append({"signal": i["signal"], "kind": i["kind"], "label": LABEL[i["signal"]],
                        "tip": _tip(scenario, i["signal"]),
                        "percent": i["percent"], "episodes": i["episodes"], "longest": i["longest"],
                        "start": round(a, 1)})

    items = []
    for i in issues:
        if i["signal"] in FRAMING:
            continue
        for a, b in i["spans"][:2]:
            items.append({"signal": i["signal"], "kind": i["kind"], "label": LABEL[i["signal"]],
                          "tip": _tip(scenario, i["signal"]),
                          "start": round(a, 1), "end": round(b, 1), "said": _said(segments, (a, b))})
    items = sorted(sorted(items, key=lambda x: x["start"] - x["end"])[:12], key=lambda x: x["start"])

    combined, seen = [], set()
    for (vs, bs), (en, ar) in COMBINED.items():
        dv, db = voice.get(vs), body.get(bs)
        if not dv or not db:
            continue
        best = None
        for sv in dv["spans"]:
            for sb in db["spans"]:
                o = _overlap(sv, sb)
                if o >= 2.0 and (best is None or o > best[0]):
                    best = (o, max(sv[0], sb[0]), min(sv[1], sb[1]))
        if best and (vs, bs) not in seen:
            seen.add((vs, bs))
            combined.append({"voice": vs, "body": bs, "label": {"en": f"{LABEL[vs]['en']} + {LABEL[bs]['en']}",
                             "ar": f"{LABEL[vs]['ar']} + {LABEL[bs]['ar']}"}, "tip": {"en": en, "ar": ar},
                             "start": round(best[1], 1), "end": round(best[2], 1),
                             "said": _said(segments, (best[1], best[2]))})
    combined.sort(key=lambda c: c["start"] - c["end"])
    combined = combined[:4]

    strengths = []
    up = body.get("upright")
    if up and up["percent"] >= 60:
        p = round(up["percent"])
        strengths.append({"en": f"You kept an upright posture about {p}% of the time.",
                          "ar": f"حافظت على وقفة أو جلسة مستقيمة حوالي {p}% من الوقت."})
    if body and all(body.get(k) and body[k]["percent"] < 5 for k in ("sway", "fidget")):
        strengths.append({"en": "Your body stayed settled, with little sway or restless movement.",
                          "ar": "جسمك فضل هادي، من غير تمايل أو حركة عصبية تُذكر."})
    ov = v.get("overall") if v and not v.get("error") else None
    if ov and ov.get("level_note") == "ok" and not (voice.get("quiet_voice") or {}).get("episodes"):
        strengths.append({"en": "Your voice stayed steady and at a good level.",
                          "ar": "صوتك فضل ثابت وبمستوى كويس."})
    if ov and ov.get("pitch_range_st") is not None and ov["pitch_range_st"] >= 4:
        strengths.append({"en": "Your voice was expressive, with good pitch variation.",
                          "ar": "صوتك كان معبّر وفيه تنوع كويس في النغمة."})
    if ov and ov.get("wpm") and 110 <= ov["wpm"] <= 250 and not (voice.get("fast_speech") or {}).get("episodes", 0) > 3:
        strengths.append({"en": "Your speaking pace was comfortable.", "ar": "سرعة كلامك كانت مريحة."})

    return {"summary": summary, "items": items, "combined": combined, "strengths": strengths,
            "has_voice": bool(voice)}


def enrich(job):
    """A copy of the job whose result carries the coach advice and the practice score for the job's scenario."""
    res = job.get("result")
    if not res:
        return job
    ctx = job.get("context") or {}
    sc = clean_scenario(ctx.get("scenario"))
    return {**job, "context": {"scenario": sc, "goal": ctx.get("goal", "")},
            "result": {**res, "coach": build_advice(res, sc), "score": compute_score(res, sc)}}
