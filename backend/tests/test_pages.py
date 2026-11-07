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


def test_prep_chat_saved_with_session(tmp_path, monkeypatch):
    monkeypatch.setenv("KINARA_LLM", "none")
    c = client(tmp_path, monkeypatch)
    assert c.post("/api/prep/chat", json={"message": "hi"}).status_code == 401
    signup(c)
    r = c.post("/api/prep/chat", json={"scenario": "interview", "goal": "calm", "message": "How do I prepare?", "history": [], "lang": "en"})
    assert r.status_code == 200 and r.json()["reply"]
    assert c.post("/api/prep/chat", json={"message": "  "}).status_code == 400
    jid = "9" * 32
    jobs.create(jid, "v.mp4", ".mp4"); db.create_session(jid, 1, "v.mp4", {"scenario": "interview"})
    msgs = [{"role": "user", "text": "q"}, {"role": "coach", "text": r.json()["reply"]}]
    assert c.post(f"/api/jobs/{jid}/prep", json={"messages": msgs}).json()["saved"] == 2
    assert len(jobs.get(jid)["chat"]) == 2
    assert c.post("/api/jobs/" + "8" * 32 + "/prep", json={"messages": msgs}).status_code == 404


def test_password_delete_admin(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    signup(c)                                  # first account = admin
    assert c.get("/api/admin/overview").json()["stats"]["users"] == 1
    assert c.get("/admin").status_code == 200
    assert c.post("/api/account/password", json={"old": "nope", "new": "newsecret1"}).status_code == 401
    assert c.post("/api/account/password", json={"old": "secret123", "new": "x"}).status_code == 400
    assert c.post("/api/account/password", json={"old": "secret123", "new": "newsecret1"}).status_code == 200
    c2 = client(tmp_path, monkeypatch); c2.cookies.clear()
    assert c2.post("/api/login", json={"email": "a@b.co", "password": "newsecret1"}).status_code == 200
    jid = "6" * 32
    jobs.create(jid, "v.mp4", ".mp4"); db.create_session(jid, 1, "v.mp4", {"scenario": "general"})
    assert c.post("/api/account/delete", json={"password": "newsecret1"}).status_code == 409   # still processing
    j = jobs.get(jid); j["status"] = "done"; jobs._touch(j)
    assert c.post("/api/account/delete", json={"password": "wrong"}).status_code == 401
    assert c.post("/api/account/delete", json={"password": "newsecret1"}).status_code == 200
    assert db.session_owner(jid) is None and db.get_user_by_email("a@b.co") is None


def test_admin_only_for_admin(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    signup(c, "admin@b.co")
    c2 = TestClient(main.app, follow_redirects=False)
    signup(c2, "user@b.co")
    assert c2.get("/api/admin/overview").status_code == 403
    assert c2.get("/admin").status_code == 404
