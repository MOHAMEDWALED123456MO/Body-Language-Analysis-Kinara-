"""Database layer (SQLAlchemy Core). SQL Server in production, SQLite by default so the app also runs without one.

Select the database with the KINARA_DB environment variable, for example (Windows login):
  mssql+pyodbc://@localhost/kinara?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
When KINARA_DB is not set, data/kinara.db (SQLite) is used and created automatically.
Every write here is best effort: a database problem is printed but never breaks an analysis.
"""
import os
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, MetaData, String, Table, Text, create_engine, delete,
                        event, insert, select, update)

_meta = MetaData()
UserRole = Table("UserRole", _meta, Column("RoleID", Integer, primary_key=True), Column("RoleName", String), Column("Description", String))
User = Table("User", _meta, Column("UserID", Integer, primary_key=True), Column("RoleID", Integer), Column("FullName", String),
             Column("Email", String), Column("PasswordHash", String), Column("Contact", String), Column("JoinDate", DateTime))
AIModel = Table("AI_Model", _meta, Column("ModelID", Integer, primary_key=True), Column("Name", String), Column("Version", String),
                Column("BodyPart", String), Column("Accuracy", Float))
Session = Table("Session", _meta, Column("SessionID", String, primary_key=True), Column("UserID", Integer), Column("StartTime", DateTime),
                Column("EndTime", DateTime), Column("VideoPath", String), Column("VideoName", String), Column("RoleContext", String),
                Column("Goal", String), Column("Status", String))
Report = Table("Report", _meta, Column("ReportID", Integer, primary_key=True), Column("SessionID", String), Column("Score", Integer),
               Column("BodyScore", Integer), Column("VoiceScore", Integer), Column("ImprovementTips", Text), Column("DateGenerated", DateTime))
Feedback = Table("Feedback", _meta, Column("FeedbackID", Integer, primary_key=True), Column("SessionID", String), Column("Role", String),
                 Column("Message", Text), Column("FeedbackTime", DateTime))
SessionModel = Table("SessionModel", _meta, Column("SessionID", String, primary_key=True), Column("ModelID", Integer, primary_key=True),
                     Column("ProcessingTime", Float))
SignalResult = Table("SignalResult", _meta, Column("SignalID", Integer, primary_key=True), Column("SessionID", String), Column("SignalType", String),
                     Column("Category", String), Column("Percent", Float), Column("Episodes", Integer), Column("Longest", Float))
CoachingNote = Table("CoachingNote", _meta, Column("CoachingID", Integer, primary_key=True), Column("SessionID", String), Column("Stage", String),
                     Column("AtSecond", Float), Column("Message", Text))
SystemLog = Table("SystemLog", _meta, Column("LogID", Integer, primary_key=True), Column("UserID", Integer), Column("LogLevel", String),
                  Column("Message", Text), Column("LogTime", DateTime))

SQL_DIR = Path(__file__).resolve().parent.parent / "db"
MODELS = [("MediaPipe Pose Landmarker (lite)", "1", "body"), ("faster-whisper", "1", "voice")]
_engine = None
_lock = threading.Lock()


def now():
    return datetime.now().replace(microsecond=0)


def engine():
    global _engine
    with _lock:
        if _engine is None:
            url = os.environ.get("KINARA_DB")
            if not url:
                Path("data").mkdir(exist_ok=True)
                url = "sqlite:///" + str(Path("data") / "kinara.db")
            _engine = create_engine(url, future=True, pool_pre_ping=True)
            if _engine.dialect.name == "sqlite":
                event.listen(_engine, "connect", lambda c, _r: c.execute("PRAGMA foreign_keys=ON"))
            _init(_engine)
        return _engine


def reset(url=None):
    """Forget the engine (tests, or switching database)."""
    global _engine
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
    if url is not None:
        os.environ["KINARA_DB"] = url


def _init(eng):
    if eng.dialect.name == "sqlite":
        raw = eng.raw_connection()
        try:
            has = raw.execute("SELECT 1 FROM sqlite_master WHERE name='User'").fetchone()
            if not has:
                raw.executescript((SQL_DIR / "schema_sqlite.sql").read_text(encoding="utf-8"))
            elif any(r[1] == "Timestamp" for r in raw.execute("PRAGMA table_info(SystemLog)")):   # older file: align the column name
                raw.execute("ALTER TABLE SystemLog RENAME COLUMN Timestamp TO LogTime")
                raw.commit()
        finally:
            raw.close()
    with eng.begin() as c:
        try:
            c.execute(select(UserRole.c.RoleID).limit(1)).first()
        except Exception as e:
            raise RuntimeError("The Kinara tables were not found. Run db/schema_sqlserver.sql (or schema_mysql.sql) first.") from e
        have = {r[0] for r in c.execute(select(UserRole.c.RoleName))}
        for name, desc in (("user", "Practices and reviews own sessions"), ("admin", "Manages users and system logs")):
            if name not in have:
                c.execute(insert(UserRole).values(RoleName=name, Description=desc))
        names = {r[0] for r in c.execute(select(AIModel.c.Name))}
        for n, v, part in MODELS:
            if n not in names:
                c.execute(insert(AIModel).values(Name=n, Version=v, BodyPart=part))


def _safe(fn):
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:
            print(f"[db] {fn.__name__} failed: {e}")
            return None
    wrap.__name__ = fn.__name__
    return wrap


# ---------- users
def _row(r):
    return dict(r._mapping) if r is not None else None


def count_users():
    with engine().connect() as c:
        return c.execute(select(User.c.UserID)).fetchall().__len__()


def get_user(uid):
    with engine().connect() as c:
        return _row(c.execute(select(User).where(User.c.UserID == uid)).first())


def role_name(role_id):
    with engine().connect() as c:
        return c.execute(select(UserRole.c.RoleName).where(UserRole.c.RoleID == role_id)).scalar()


def get_user_by_email(email):
    with engine().connect() as c:
        return _row(c.execute(select(User).where(User.c.Email == email)).first())


def create_user(name, email, pw_hash, first_is_admin=True):
    with engine().begin() as c:
        n = len(c.execute(select(User.c.UserID)).fetchall())
        role = "admin" if (n == 0 and first_is_admin) else "user"
        rid = c.execute(select(UserRole.c.RoleID).where(UserRole.c.RoleName == role)).scalar_one()
        c.execute(insert(User).values(RoleID=rid, FullName=name, Email=email, PasswordHash=pw_hash, JoinDate=now()))
        return _row(c.execute(select(User).where(User.c.Email == email)).first())


# ---------- sessions
def session_owner(job_id):
    with engine().connect() as c:
        return c.execute(select(Session.c.UserID).where(Session.c.SessionID == job_id)).scalar()


def user_session_ids(uid):
    with engine().connect() as c:
        return [r[0] for r in c.execute(select(Session.c.SessionID).where(Session.c.UserID == uid))]


@_safe
def create_session(job_id, uid, name, ctx, created=None, status="queued"):
    with engine().begin() as c:
        if c.execute(select(Session.c.SessionID).where(Session.c.SessionID == job_id)).first():
            return
        start = datetime.fromisoformat(created).replace(tzinfo=None) if created else now()
        c.execute(insert(Session).values(SessionID=job_id, UserID=uid, StartTime=start, VideoName=name, VideoPath=None,
                                         RoleContext=(ctx or {}).get("scenario", "general"), Goal=(ctx or {}).get("goal", ""), Status=status))


def _advice_text(coach):
    out = []
    for s in (coach or {}).get("summary", []):
        out.append(f"- {s['label']['en']}: {s['tip']['en']}")
    return "\n".join(out)


@_safe
def save_result(job):
    """Store the finished analysis (idempotent): status, report, signals, advice notes and the models used."""
    res, jid = job["result"], job["id"]
    sc, coach = res.get("score"), res.get("coach") or {}
    with engine().begin() as c:
        if not c.execute(select(Session.c.SessionID).where(Session.c.SessionID == jid)).first():
            return
        c.execute(update(Session).where(Session.c.SessionID == jid).values(
            Status="done", EndTime=now(), RoleContext=job["context"]["scenario"], Goal=job["context"].get("goal", ""),
            VideoPath=f"data/uploads/{jid}{job.get('ext', '')}"))
        for t in (Report, SignalResult, CoachingNote, SessionModel):
            c.execute(delete(t).where(t.c.SessionID == jid))
        if sc:
            c.execute(insert(Report).values(SessionID=jid, Score=sc["overall"], BodyScore=sc.get("body"), VoiceScore=sc.get("voice"),
                                            ImprovementTips=_advice_text(coach), DateGenerated=now()))
        sigs = [(k, "body", d) for k, d in (res.get("signals") or {}).items()]
        v = res.get("voice")
        if v and not v.get("error"):
            sigs += [(k, "voice", d) for k, d in (v.get("signals") or {}).items()]
        for k, cat, d in sigs:
            c.execute(insert(SignalResult).values(SessionID=jid, SignalType=k, Category=cat, Percent=d["percent"],
                                                  Episodes=d["episodes"], Longest=d["longest"]))
        for s in coach.get("summary", []):
            c.execute(insert(CoachingNote).values(SessionID=jid, Stage="priority", AtSecond=s.get("start"), Message=s["tip"]["en"]))
        for x in coach.get("items", []):
            c.execute(insert(CoachingNote).values(SessionID=jid, Stage="moment", AtSecond=x.get("start"), Message=x["tip"]["en"]))
        for x in coach.get("strengths", []):
            c.execute(insert(CoachingNote).values(SessionID=jid, Stage="strength", AtSecond=None, Message=x["en"]))
        for mid, part in c.execute(select(AIModel.c.ModelID, AIModel.c.BodyPart)).fetchall():
            if part == "body" or (part == "voice" and v and not v.get("error")):
                c.execute(insert(SessionModel).values(SessionID=jid, ModelID=mid))


@_safe
def mark_error(job_id):
    with engine().begin() as c:
        c.execute(update(Session).where(Session.c.SessionID == job_id).values(Status="error", EndTime=now()))


@_safe
def add_feedback(job_id, msgs):
    with engine().begin() as c:
        for m in msgs:
            c.execute(insert(Feedback).values(SessionID=job_id, Role="user" if m["role"] == "user" else "coach", Message=m["text"], FeedbackTime=now()))


@_safe
def clear_feedback(job_id):
    with engine().begin() as c:
        c.execute(delete(Feedback).where(Feedback.c.SessionID == job_id))


@_safe
def delete_session(job_id):
    with engine().begin() as c:
        for t in (Report, SignalResult, CoachingNote, SessionModel, Feedback):
            c.execute(delete(t).where(t.c.SessionID == job_id))
        c.execute(delete(Session).where(Session.c.SessionID == job_id))


@_safe
def log(level, message, uid=None):
    with engine().begin() as c:
        c.execute(insert(SystemLog).values(UserID=uid, LogLevel=level, Message=str(message)[:2000], LogTime=now()))


# ---------- account + admin
@_safe
def set_password(uid, pw_hash):
    with engine().begin() as c:
        c.execute(update(User).where(User.c.UserID == uid).values(PasswordHash=pw_hash))


@_safe
def delete_user(uid):
    """Removes the account. Its sessions must already be deleted; log rows keep their text but lose the user."""
    with engine().begin() as c:
        c.execute(update(SystemLog).where(SystemLog.c.UserID == uid).values(UserID=None))
        c.execute(delete(User).where(User.c.UserID == uid))


def overview(log_limit=40):
    """Admin numbers: totals, every user with a session count, and the latest log lines."""
    with engine().connect() as c:
        roles = {r[0]: r[1] for r in c.execute(select(UserRole.c.RoleID, UserRole.c.RoleName))}
        counts = {}
        for (uid,) in c.execute(select(Session.c.UserID)):
            counts[uid] = counts.get(uid, 0) + 1
        users = [{"id": u.UserID, "name": u.FullName, "email": u.Email, "role": roles.get(u.RoleID, "user"),
                  "joined": u.JoinDate.isoformat() if u.JoinDate else None, "sessions": counts.get(u.UserID, 0)}
                 for u in c.execute(select(User).order_by(User.c.UserID))]
        logs = [{"level": r.LogLevel, "message": r.Message, "time": r.LogTime.isoformat() if r.LogTime else None, "user": r.UserID}
                for r in c.execute(select(SystemLog).order_by(SystemLog.c.LogID.desc()).limit(log_limit))]
        nsess = sum(counts.values())
        scores = [r[0] for r in c.execute(select(Report.c.Score)) if r[0] is not None]
    return {"stats": {"users": len(users), "sessions": nsess, "avg_score": round(sum(scores) / len(scores)) if scores else None},
            "users": users, "logs": logs}
