import pytest

from engine import chat, jobs, roles
from engine.coach import build_advice
from test_chat import make_job, no_engine  # noqa: F401
from test_web import client, video_bytes  # noqa: F401


def sig(percent, longest=5.0):
    return {"percent": percent, "episodes": 1 if percent else 0, "longest": longest if percent else 0,
            "spans": [(10.0, 10.0 + longest)] if percent else []}


def clean_body(**kw):
    ids = [s for s in roles.BODY_IDS]
    d = {i: sig(0) for i in ids}
    d.update(kw)
    return {"signals": d}


def test_clean_video_scores_high_and_bands():
    s = roles.compute_score(clean_body(), "general")
    assert s["overall"] == 100 and s["body"] == 100 and s["voice"] is None and s["lost"] == []
    assert [roles.label_for(x)["id"] for x in (95, 75, 55, 20)] == ["strong", "good", "work", "basics"]


def test_scenario_changes_the_score():
    res = clean_body(sway=sig(30))                          # a lot of swaying
    pres = roles.compute_score(res, "presentation")["overall"]
    inter = roles.compute_score(res, "interview")["overall"]
    assert pres > inter + 5                                  # swaying matters less on stage than in an interview
    res2 = clean_body(distance=sig(50), off_center=sig(50))  # bad framing
    assert roles.compute_score(res2, "meeting")["overall"] < roles.compute_score(res2, "presentation")["overall"]


def test_voice_component_and_unusable_voice():
    res = clean_body()
    res["voice"] = {"overall": {"level_note": "ok"}, "signals": {i: sig(0) for i in roles.VOICE_IDS}}
    res["voice"]["signals"]["monotone"] = sig(30)
    s = roles.compute_score(res, "speech")
    assert s["voice"] < 100 and s["body"] == 100 and s["overall"] < 100
    assert s["lost"][0]["signal"] == "monotone" and s["lost"][0]["scope"] == "voice"
    res["voice"] = {"error": "no_audio"}
    assert roles.compute_score(res, "speech")["voice"] is None
    res["voice"] = {"overall": {"level_note": "no_speech"}, "signals": {}}
    assert roles.compute_score(res, "speech")["voice"] is None
    assert roles.compute_score({"signals": {}}, "speech") is None


def test_unknown_scenario_falls_back_and_goal_is_cleaned():
    assert roles.clean_scenario("nope") == "general" and roles.clean_scenario(None) == "general"
    assert roles.clean_goal("  be   calmer \n now ") == "be calmer now"
    assert len(roles.clean_goal("x" * 1000)) == 300


def test_coach_uses_scenario_wording_and_priority():
    res = clean_body(fidget=sig(25, 8), sway=sig(25, 8))
    inter = build_advice(res, "interview")
    assert inter["summary"][0]["signal"] == "fidget"
    assert "Interviewers" in inter["summary"][0]["tip"]["en"]
    pres = build_advice(res, "presentation")
    assert pres["summary"][0]["signal"] == "fidget"
    sway = next(i for i in pres["items"] if i["signal"] == "sway")
    assert "purposeful" in sway["tip"]["en"]


def test_context_through_the_api(client, tmp_path):
    r = client.post("/api/analyze?filename=t.mp4&scenario=interview&goal=" + "be%20calmer", content=video_bytes(tmp_path))
    jid = r.json()["id"]
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["context"] == {"scenario": "interview", "goal": "be calmer"}
    assert job["result"]["score"]["scenario"] == "interview" and 0 <= job["result"]["score"]["overall"] <= 100
    before = job["result"]["score"]["overall"]
    p = client.patch(f"/api/jobs/{jid}/context", json={"scenario": "presentation", "goal": "more energy"})
    assert p.status_code == 200 and p.json()["result"]["score"]["scenario"] == "presentation"
    assert client.get(f"/api/jobs/{jid}").json()["context"]["goal"] == "more energy"
    assert isinstance(before, int)
    bad = client.post("/api/analyze?filename=t2.mp4&scenario=bogus", content=video_bytes(tmp_path)).json()["id"]
    assert client.get(f"/api/jobs/{bad}").json()["context"]["scenario"] == "general"
    assert client.patch("/api/jobs/" + "0" * 32 + "/context", json={"scenario": "speech"}).status_code == 404


def test_chat_knows_the_scenario_goal_and_score(client, tmp_path):
    jid = client.post("/api/analyze?filename=t.mp4&scenario=meeting&goal=sound%20calmer", content=video_bytes(tmp_path)).json()["id"]
    from engine.coach import enrich
    ctx = chat.build_context(enrich(jobs.get(jid)))
    assert "SCENARIO: Online meeting" in ctx and "sound calmer" in ctx and "PRACTICE SCORE" in ctx
