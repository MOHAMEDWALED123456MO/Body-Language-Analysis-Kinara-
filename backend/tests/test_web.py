import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
from engine import jobs
from engine import profile as prof
from engine import audio
from test_audio import sample as voice_sample
from test_pose_signals import FH, FW, build_profile, make, world


def fake_detect_factory(fps=15, lean_from=3.0):
    count = [0]

    def detect(_lm, _frame):
        t = count[0] / fps
        count[0] += 1
        return make(), world(15 if t >= lean_from else 0)
    return detect


def video_bytes(tmp_path, seconds=6, fps=30, name="v.mp4"):
    p = tmp_path / name
    vw = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), fps, (FW, FH))
    for i in range(int(seconds * fps)):
        vw.write(np.full((FH, FW, 3), i % 200, np.uint8))
    vw.release()
    return p.read_bytes()


def fake_audio(path, work_dir, progress=None):
    if progress:
        progress(0.5); progress(1.0)
    res = audio.analyze_samples(voice_sample())
    res["transcript"] = {"language": "en", "text": "hello", "words": [],
                         "segments": [{"start": 2.0, "end": 4.0, "text": "hello"}]}
    res["stt_note"] = None
    return res


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path / "data")
    pp = tmp_path / "profile.json"
    prof.save_profile(build_profile(), str(pp))
    mp = tmp_path / "model.task"
    mp.write_bytes(b"x")
    monkeypatch.setattr(jobs, "PROFILE_PATH", str(pp))
    monkeypatch.setattr(jobs, "MODEL_PATH", str(mp))
    monkeypatch.setattr(jobs, "LANDMARKER_FACTORY", lambda: None)
    monkeypatch.setattr(jobs, "DETECT_FN", fake_detect_factory())
    monkeypatch.setattr(jobs, "AUDIO_FN", fake_audio)
    jobs.reset_memory()
    return TestClient(main.app)


def test_status_and_pages(client):
    assert client.get("/api/status").json() == {"calibrated": True, "model_ok": True}
    for path in ("/", "/privacy", "/analyze", "/health"):
        assert client.get(path).status_code == 200
    assert "analyze.js" in client.get("/analyze").text
    assert client.get("/results/" + "0" * 32).status_code == 404
    assert client.get("/results/not-an-id").status_code == 404


def test_full_flow(client, tmp_path):
    r = client.post("/api/analyze?filename=talk.mp4", content=video_bytes(tmp_path))
    assert r.status_code == 200
    jid = r.json()["id"]
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "done" and job["name"] == "talk.mp4"
    sig = job["result"]["signals"]
    assert sig["lean_forward"]["episodes"] == 1 and sig["lean_forward"]["spans"]
    assert job["result"]["thresholds"]["lean_forward"] is not None

    page = client.get(f"/results/{jid}")
    assert page.status_code == 200 and jid in page.text and "lean_forward" in page.text

    lst = client.get("/api/jobs").json()
    assert lst[0]["id"] == jid and lst[0]["status"] == "done" and lst[0]["duration"] > 5

    v = client.get(f"/api/jobs/{jid}/video")
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    rng = client.get(f"/api/jobs/{jid}/video", headers={"Range": "bytes=0-99"})
    assert rng.status_code == 206 and len(rng.content) == 100

    assert client.delete(f"/api/jobs/{jid}").json() == {"ok": True}
    assert client.get(f"/api/jobs/{jid}").status_code == 404
    assert client.get(f"/api/jobs/{jid}/video").status_code == 404
    assert not list((tmp_path / "data" / "uploads").glob("*"))


def test_rejections(client, tmp_path, monkeypatch):
    def code(r):
        return r.json()["detail"]["code"]
    r = client.post("/api/analyze?filename=x.exe", content=b"abc")
    assert r.status_code == 415 and code(r) == "bad_type"
    r = client.post("/api/analyze?filename=x.mp4", content=b"")
    assert r.status_code == 400 and code(r) == "empty"
    r = client.post("/api/analyze?filename=x.mp4", content=b"this is not a video" * 50)
    assert r.status_code == 422 and code(r) == "bad_video"
    monkeypatch.setattr(jobs, "MAX_BYTES", 1000)
    r = client.post("/api/analyze?filename=x.mp4", content=b"a" * 5000)
    assert r.status_code == 413 and code(r) == "too_big"
    assert not list((tmp_path / "data" / "uploads").glob("*"))      # nothing left behind


def test_no_calibration_blocks_upload(client, monkeypatch, tmp_path):
    monkeypatch.setattr(jobs, "PROFILE_PATH", str(tmp_path / "missing.json"))
    assert client.get("/api/status").json()["calibrated"] is False
    r = client.post("/api/analyze?filename=x.mp4", content=b"abc")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_calibration"


def test_filename_is_sanitized(client, tmp_path):
    r = client.post("/api/analyze?filename=..%2F..%2Fsecret%0Aname.mp4", content=video_bytes(tmp_path, 3))
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert "/" not in job["name"] and "\n" not in job["name"]
    assert all(".." not in str(p) for p in (tmp_path / "data").rglob("*"))


def test_recover_marks_interrupted(client, tmp_path):
    job = jobs.create("a" * 32, "x.mp4", ".mp4")
    job["status"] = "processing"
    jobs._touch(job)
    jobs.reset_memory()
    jobs.recover()
    got = client.get("/api/jobs/" + "a" * 32).json()
    assert got["status"] == "error" and got["error_code"] == "interrupted"
    assert client.delete("/api/jobs/" + "a" * 32).status_code == 200


def test_internal_error_does_not_kill_server(client, tmp_path, monkeypatch):
    def boom(*_a):
        raise ValueError("boom")
    monkeypatch.setattr(jobs, "DETECT_FN", boom)
    r = client.post("/api/analyze?filename=x.mp4", content=video_bytes(tmp_path, 3))
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "error" and job["error_code"] == "internal"
    assert client.get("/health").status_code == 200


def _analyze(client, tmp_path):
    r = client.post("/api/analyze?filename=talk.mp4", content=video_bytes(tmp_path))
    assert r.status_code == 200
    return client.get(f"/api/jobs/{r.json()['id']}").json()


def test_voice_is_part_of_the_result(client, tmp_path):
    job = _analyze(client, tmp_path)
    v = job["result"]["voice"]
    assert job["status"] == "done" and "error" not in v
    assert v["signals"]["long_pause"]["episodes"] == 1
    assert v["transcript"]["segments"][0]["text"] == "hello"
    assert job["result"]["coach"]["summary"]
    page = client.get(f"/results/{job['id']}")
    assert "long_pause" in page.text and "monotone" in page.text


def test_voice_failure_does_not_break_the_job(client, tmp_path, monkeypatch):
    def no_audio(path, work_dir, progress=None):
        raise audio.AudioError("no_audio")
    monkeypatch.setattr(jobs, "AUDIO_FN", no_audio)
    job = _analyze(client, tmp_path)
    assert job["status"] == "done" and job["result"]["voice"] == {"error": "no_audio"}
    assert job["result"]["signals"]["lean_forward"]["episodes"] == 1

    def boom(path, work_dir, progress=None):
        raise ValueError("x")
    monkeypatch.setattr(jobs, "AUDIO_FN", boom)
    job = _analyze(client, tmp_path)
    assert job["status"] == "done" and job["result"]["voice"]["error"] == "internal"
