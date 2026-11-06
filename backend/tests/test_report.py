"""The printable report page: route, template wiring, and the link from the results page."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import jobs


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    import main
    return TestClient(main.app)


def _done_job():
    jid = "d" * 32
    j = jobs.create(jid, "talk.mp4", ".mp4", {"scenario": "interview", "goal": "calmer"})
    j.update(status="done", progress=1.0, result={"total_seconds": 30.0, "visible_seconds": 30.0, "analyzed_fps": 12.5,
                                                  "signals": {}, "voice": None})
    jobs._touch(j)
    return jid


def test_report_page_served_for_known_job(client):
    jid = _done_job()
    r = client.get(f"/report/{jid}")
    assert r.status_code == 200
    assert f'window.JOB_ID = "{jid}"' in r.text
    assert "/static/report.js" in r.text and "/static/report.css" in r.text
    assert "window.SIGNALS" in r.text and "window.SCENARIOS" in r.text


def test_report_404_for_unknown_or_malformed_id(client):
    assert client.get("/report/" + "7" * 32).status_code == 404
    assert client.get("/report/not-an-id").status_code == 404


def test_report_assets_exist(client):
    for path in ("/static/report.js", "/static/report.css"):
        assert client.get(path).status_code == 200


def test_results_page_links_to_report(client):
    jid = _done_job()
    html = client.get(f"/results/{jid}").text
    assert f'href="/report/{jid}"' in html
    assert "res_report" in Path("static/i18n_app.js").read_text(encoding="utf-8")


def test_report_has_print_rules():
    css = Path("static/report.css").read_text(encoding="utf-8")
    assert "@media print" in css and "@page" in css and "print-color-adjust" in css


def _seed(n):
    import copy
    base = {"total_seconds": 30.0, "visible_seconds": 30.0, "analyzed_fps": 12.5, "voice": None,
            "signals": {"upright": {"percent": 70.0, "seconds": 21.0, "episodes": 1, "longest": 21.0, "spans": [[0, 21]]},
                        "fidget": {"percent": 30.0, "seconds": 9.0, "episodes": 2, "longest": 5.0, "spans": [[2, 7], [10, 14]]}}}
    ids = []
    for i in range(n):
        jid = f"{i:x}" * 32 if i < 16 else "f" * 32
        j = jobs.create(jid, f"s{i}.mp4", ".mp4", {"scenario": "general", "goal": ""})
        r = copy.deepcopy(base); r["signals"]["fidget"]["percent"] = 30.0 - 10 * i
        j.update(status="done", progress=1.0, result=r); j["created"] = f"2026-11-0{i + 1}T10:00:00+02:00"; jobs._touch(j)
        ids.append(jid)
    jobs.create("9" * 32, "pending.mp4", ".mp4")
    return ids


def test_progress_api_lists_done_sessions_oldest_first(client):
    _seed(3)
    rows = client.get("/api/progress").json()
    assert [r["name"] for r in rows] == ["s0.mp4", "s1.mp4", "s2.mp4"]     # the pending job is left out
    assert rows[0]["overall"] <= rows[2]["overall"]                       # less fidgeting scores higher
    assert rows[0]["signals"]["fidget"] == 30.0 and 0 <= rows[1]["overall"] <= 100


def test_progress_api_empty_and_page(client):
    assert client.get("/api/progress").json() == []
    r = client.get("/progress")
    assert r.status_code == 200 and "/static/progress.js" in r.text


def test_recording_is_remuxed_and_stays_readable(tmp_path):
    import shutil, subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    import main
    src = tmp_path / "rec.webm"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10",
                    "-t", "1", "-c:v", "libvpx", str(src)], check=True)
    before = src.stat().st_size
    main._remux(src)
    assert src.exists() and src.stat().st_size > 0 and main._readable(src)
    assert not list(tmp_path.glob("*.fixed*"))             # no leftovers
    assert before > 0


def test_remux_ignores_unsupported_types(tmp_path):
    import main
    f = tmp_path / "x.avi"; f.write_bytes(b"123")
    main._remux(f)
    assert f.read_bytes() == b"123"
