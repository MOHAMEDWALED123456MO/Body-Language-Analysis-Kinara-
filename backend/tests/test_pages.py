import json
from fastapi.testclient import TestClient
import main
from engine import db, jobs


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    db.reset("sqlite:///" + str(tmp_path / "t.db"))
    monkeypatch.setenv("KINARA_AUTH", "on")
    return TestClient(main.app, follow_redirects=False)


def signup(c, email="a@b.co"):
    r = c.post("/api/register", json={"name": "Ali Test", "email": email, "password": "secret123"})
    assert r.status_code == 200, r.text


def test_pages_need_login(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    for p in ("/dashboard", "/new", "/sessions", "/profile", "/progress"):
        assert c.get(p).status_code == 303, p
    assert c.get("/").status_code == 200
    assert c.get("/analyze").headers["location"] == "/new"
    signup(c)
    for p in ("/dashboard", "/new", "/sessions", "/profile", "/progress"):
        assert c.get(p).status_code == 200, p
    assert c.get("/api/me").json()["admin"] is True


def test_bulk_delete(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    signup(c)
    ids = []
    for i in range(3):
        jid = f"{i}" * 32
        jobs.create(jid, f"v{i}.mp4", ".mp4")
        db.create_session(jid, 1, f"v{i}.mp4", {"scenario": "general"})
        j = jobs.get(jid); j["status"] = "done"; jobs._touch(j)
        ids.append(jid)
    assert len(c.get("/api/sessions").json()) == 3
    r = c.post("/api/sessions/delete", json={"ids": ids[:1]}).json()
    assert r["deleted"] == 1 and len(c.get("/api/sessions").json()) == 2
    r = c.post("/api/sessions/delete", json={"all": True}).json()
    assert r["deleted"] == 2 and c.get("/api/sessions").json() == []
    assert db.session_owner(ids[0]) is None
