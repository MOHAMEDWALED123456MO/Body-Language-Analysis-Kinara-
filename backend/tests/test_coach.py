from engine import audio
from engine.coach import build_advice
from test_audio import sample


def sig(percent, spans):
    return {"percent": percent, "episodes": len(spans), "longest": max([b - a for a, b in spans], default=0),
            "spans": spans}


def body(**kw):
    base = {"upright": sig(70, [(0, 10)]), "sway": sig(1, [(1, 2)]), "fidget": sig(1, [(1, 2)])}
    base.update(kw)
    return {"signals": base}


def test_priorities_items_and_quotes():
    res = body(lean_back=sig(12, [(26, 32), (3, 4)]), slouch=sig(0.4, [(50, 52)]))
    v = audio.analyze_samples(sample())
    v["transcript"] = {"segments": [{"start": 14, "end": 20, "text": "this part was flat"}]}
    res["voice"] = v
    c = build_advice(res)
    ids = [s["signal"] for s in c["summary"]]
    assert len(ids) == 3 and "lean_back" in ids and ids[0] in ("quiet_voice", "monotone")
    assert all(s["tip"]["ar"] and s["tip"]["en"] for s in c["summary"])
    starts = [i["start"] for i in c["items"]]
    assert starts == sorted(starts)
    mono = next(i for i in c["items"] if i["signal"] == "monotone")
    assert mono["said"] == "this part was flat"
    assert not any(i["signal"] == "slouch" for i in c["items"])          # too small to mention


def test_combined_voice_and_body():
    res = body(lean_back=sig(20, [(24, 34)]))
    res["voice"] = audio.analyze_samples(sample())
    c = build_advice(res)
    assert any(x["voice"] == "quiet_voice" and x["body"] == "lean_back" for x in c["combined"])


def test_strengths_and_empty_cases():
    res = body()
    res["voice"] = {"error": "no_audio"}
    c = build_advice(res)
    assert c["summary"] == [] and not c["has_voice"]
    assert any("upright" in s["en"] for s in c["strengths"])
    c2 = build_advice({"signals": {}})
    assert c2["summary"] == [] and c2["items"] == [] and c2["strengths"] == []
