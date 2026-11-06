"""Accounts, ownership of analyses, and what gets stored in the database."""
import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from engine import auth, db, jobs


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KINARA_AUTH", "on")
    monkeypatch.setenv("KINARA_LLM", "none")
    monkeypatch.setattr(jobs, "DATA_DIR", tmp_path)
    db.reset("sqlite:///" + str(tmp_path / "t.db"))
    import main
    main._saved.clear(); main._failed.clear(); main._bad_logins.clear()
    yield main
    db.reset()


def client(main):
    return TestClient(main.app, follow_redirects=False)


def signup(c, name="Ali", email="ali@x.com", pw="secret123"):
    return c.post("/api/register", json={"name": name, "email": email, "password": pw})


RESULT = {"total_seconds": 30.0, "visible_seconds": 30.0, "analyzed_fps": 12.5, "voice": None,
          "signals": {"upright": {"percent": 70.0, "seconds": 21.0, "episodes": 1, "longest": 21.0, "spans": [[0, 21]]},
                      "fidget": {"percent": 30.0, "seconds": 9.0, "episodes": 2, "longest": 5.0, "spans": [[2, 7], [10, 14]]}}}


def make_job(jid, owner=None, done=True):
    j = jobs.create(jid, "talk.mp4", ".mp4", {"scenario": "general", "goal": ""})
    if done:
        j.update(status="done", progress=1.0, result=copy.deepcopy(RESULT))
        jobs._touch(j)
    if owner:
        db.create_session(jid, owner, "talk.mp4", j["context"], j["created"])
    return j


def rows(table, **where):
    with db.engine().connect() as c:
        q = select(table)
        for k, v in where.items():
            q = q.where(table.c[k] == v)
        return c.execute(q).fetchall()


def test_pages_and_api_need_login(env):
    c = client(env)
    r = c.get("/analyze")
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert c.get("/progress").status_code == 303
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/login").status_code == 200 and c.get("/privacy").status_code == 200


def test_register_login_logout(env):
    c = client(env)
    assert signup(c).status_code == 200
    assert c.get("/api/me").json()["name"] == "Ali"
    assert c.get("/analyze").status_code == 200
    c.post("/api/logout"); c.cookies.clear()
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/login", json={"email": "ali@x.com", "password": "wrong-pass"}).status_code == 401
    assert c.post("/api/login", json={"email": "ALI@x.com", "password": "secret123"}).status_code == 200
    assert c.get("/api/me").status_code == 200


def test_register_validation_and_hashing(env):
    c = client(env)
    assert signup(c, pw="short").status_code == 400
    assert signup(c, email="not-an-email").status_code == 400
    assert signup(c, name=" ").status_code == 400
    assert signup(c).status_code == 200
    assert signup(client(env)).status_code == 409
    u = db.get_user_by_email("ali@x.com")
    assert u["PasswordHash"].startswith("scrypt$") and "secret123" not in u["PasswordHash"]
    assert [r.RoleName for r in rows(db.UserRole)] == ["user", "admin"]
    assert db.get_user_by_email("ali@x.com")["RoleID"] == 2            # first account is the admin
    c2 = client(env); signup(c2, "Sara", "sara@x.com")
    assert db.get_user_by_email("sara@x.com")["RoleID"] == 1


def test_login_lockout_after_five_failures(env):
    c = client(env); signup(c); c.cookies.clear()
    for _ in range(5):
        assert c.post("/api/login", json={"email": "ali@x.com", "password": "nope-nope"}).status_code == 401
    assert c.post("/api/login", json={"email": "ali@x.com", "password": "secret123"}).status_code == 429


def test_tampered_or_expired_cookie_is_rejected(env):
    uid_token = auth.make_token(1)
    assert auth.read_token(uid_token) == 1
    assert auth.read_token(uid_token[:-2] + "00") is None
    assert auth.read_token(auth.make_token(1, now=0)) is None


def test_user_cannot_see_someone_elses_analysis(env):
    a, b = client(env), client(env)
    uid_a = signup(a).cookies and db.get_user_by_email("ali@x.com")["UserID"]
    signup(b, "Sara", "sara@x.com")
    make_job("a" * 32, owner=uid_a)
    for path in ("/api/jobs/" + "a" * 32, "/api/jobs/" + "a" * 32 + "/video", "/api/jobs/" + "a" * 32 + "/chat"):
        assert a.get(path).status_code in (200, 404) and b.get(path).status_code == 404
    assert a.get("/api/jobs/" + "a" * 32).status_code == 200
    assert b.get("/results/" + "a" * 32).status_code == 404 and b.get("/report/" + "a" * 32).status_code == 404
    assert b.delete("/api/jobs/" + "a" * 32).status_code == 404
    assert [j["id"] for j in a.get("/api/jobs").json()] == ["a" * 32] and b.get("/api/jobs").json() == []
    assert b.patch("/api/jobs/" + "a" * 32 + "/context", json={"scenario": "interview"}).status_code == 404


def test_finished_analysis_is_stored_in_the_database(env):
    a = client(env); signup(a); uid = db.get_user_by_email("ali@x.com")["UserID"]
    make_job("b" * 32, owner=uid)
    assert a.get("/api/jobs/" + "b" * 32).status_code == 200
    s = rows(db.Session, SessionID="b" * 32)[0]
    assert s.Status == "done" and s.UserID == uid and s.EndTime is not None
    rep = rows(db.Report, SessionID="b" * 32)
    assert len(rep) == 1 and 0 <= rep[0].Score <= 100
    assert {r.SignalType for r in rows(db.SignalResult, SessionID="b" * 32)} >= {"upright", "fidget"}
    assert rows(db.CoachingNote, SessionID="b" * 32)
    assert len(rows(db.SessionModel, SessionID="b" * 32)) == 1          # body model only, no voice
    a.get("/api/jobs/" + "b" * 32)                                      # polling again must not duplicate
    assert len(rows(db.Report, SessionID="b" * 32)) == 1
    before = rep[0].Score
    assert a.patch("/api/jobs/" + "b" * 32 + "/context", json={"scenario": "interview", "goal": "calm"}).status_code == 200
    assert rows(db.Session, SessionID="b" * 32)[0].RoleContext == "interview"
    assert len(rows(db.Report, SessionID="b" * 32)) == 1 and before is not None


def test_chat_is_saved_as_feedback_and_cleared(env):
    a = client(env); signup(a); uid = db.get_user_by_email("ali@x.com")["UserID"]
    make_job("c" * 32, owner=uid)
    r = a.post("/api/jobs/" + "c" * 32 + "/chat", json={"message": "Where do I start?", "lang": "en"})
    assert r.status_code == 200
    fb = rows(db.Feedback, SessionID="c" * 32)
    assert [f.Role for f in fb] == ["user", "coach"]
    a.delete("/api/jobs/" + "c" * 32 + "/chat")
    assert rows(db.Feedback, SessionID="c" * 32) == []


def test_delete_removes_database_rows(env):
    a = client(env); signup(a); uid = db.get_user_by_email("ali@x.com")["UserID"]
    make_job("d" * 32, owner=uid); a.get("/api/jobs/" + "d" * 32)
    assert a.delete("/api/jobs/" + "d" * 32).status_code == 200
    assert rows(db.Session, SessionID="d" * 32) == [] and rows(db.Report, SessionID="d" * 32) == []


def test_progress_only_lists_own_sessions(env):
    a, b = client(env), client(env)
    signup(a); signup(b, "Sara", "sara@x.com")
    ua, ub = (db.get_user_by_email(e)["UserID"] for e in ("ali@x.com", "sara@x.com"))
    make_job("e" * 32, owner=ua); make_job("f" * 32, owner=ub)
    assert [r["id"] for r in a.get("/api/progress").json()] == ["e" * 32]
    assert [r["id"] for r in b.get("/api/progress").json()] == ["f" * 32]


def test_first_account_adopts_older_analyses(env):
    make_job("9" * 32)                                                  # made before accounts existed
    a = client(env); signup(a)
    uid = db.get_user_by_email("ali@x.com")["UserID"]
    assert db.session_owner("9" * 32) == uid
    assert a.get("/api/jobs/" + "9" * 32).status_code == 200
    assert rows(db.Report, SessionID="9" * 32)
