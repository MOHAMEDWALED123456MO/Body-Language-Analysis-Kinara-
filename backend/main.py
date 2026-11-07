import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import cv2
from pydantic import BaseModel
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from engine import auth, chat, db, jobs, live, progress
from engine.coach import enrich
from engine.roles import SCENARIOS, clean_goal, clean_scenario
from engine.audio import VOICE_SIGNALS
from engine.registry import SIGNALS

app = FastAPI(title="Kinara")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
jobs.recover()

MEDIA = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
         ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo"}


def _fail(status, code):
    raise HTTPException(status, {"code": code})


_saved, _failed, _bad_logins = set(), set(), {}


def _user(request):
    if not auth.enabled():
        return None
    uid = auth.read_token(request.cookies.get(auth.COOKIE, ""))
    return db.get_user(uid) if uid else None


def _need_user(request):
    """The signed-in user for an API call (None when accounts are switched off)."""
    if not auth.enabled():
        return None
    user = _user(request)
    if user is None:
        _fail(401, "login_required")
    return user


def _owned(request, job_id):
    """API guard: the job must belong to the signed-in user. Someone else's job looks like a missing one."""
    user = _need_user(request)
    if user is not None and db.session_owner(job_id) != user["UserID"]:
        _fail(404, "not_found")
    return user


def _page_guard(request, job_id=None):
    """Page guard: a redirect to the login page, a 404 for someone else's job, or None when all is well."""
    if not auth.enabled():
        return None
    user = _user(request)
    if user is None:
        return RedirectResponse("/login?next=" + request.url.path, status_code=303)
    if job_id is not None and db.session_owner(job_id) != user["UserID"]:
        raise HTTPException(404)
    return None


def _sync(job):
    """Mirror a finished or failed analysis into the database once (progress polling calls this)."""
    if job["status"] == "done" and job.get("result") and job["id"] not in _saved:
        _saved.add(job["id"])
        db.save_result(job)
    elif job["status"] == "error" and job["id"] not in _failed:
        _failed.add(job["id"])
        db.mark_error(job["id"])


def _display_name(filename):
    name = re.sub(r"[\x00-\x1f\x7f]", "", os.path.basename(filename or "")).strip()
    return (name or "video")[:80]


def _readable(path):
    cap = cv2.VideoCapture(str(path))
    try:
        ok, _ = cap.read()
        return bool(ok)
    finally:
        cap.release()


def _remux(path):
    """Browser recordings (MediaRecorder) have no duration or seek index; a stream copy through ffmpeg adds them."""
    ff = shutil.which("ffmpeg")
    if not ff or path.suffix.lower() not in (".webm", ".mp4"):
        return
    tmp = path.with_name(path.stem + ".fixed" + path.suffix)
    try:
        subprocess.run([ff, "-y", "-v", "error", "-i", str(path), "-c", "copy", str(tmp)], check=True, timeout=300)
        if tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, path)
    except (subprocess.SubprocessError, OSError):
        pass
    finally:
        if tmp.exists():
            tmp.unlink()


# ---------- pages ----------
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/analyze")
def analyze_legacy():
    return RedirectResponse("/new", status_code=303)


@app.get("/new")
def new_page(request: Request):
    if (g := _page_guard(request)):
        return g
    return templates.TemplateResponse(request, "analyze.html", {"scenarios": SCENARIOS})


def _simple_page(name):
    def page(request: Request):
        if (g := _page_guard(request)):
            return g
        return templates.TemplateResponse(request, name + ".html", {"scenarios": SCENARIOS})
    return page


for _p in ("dashboard", "sessions", "profile"):
    app.get("/" + _p, name="page_" + _p)(_simple_page(_p))


@app.get("/results/{job_id}")
def results_page(request: Request, job_id: str):
    if (g := _page_guard(request, job_id)):
        return g
    if jobs.get(job_id) is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "results.html", {"job_id": job_id, "signals": SIGNALS, "voice_signals": VOICE_SIGNALS,
                                          "scenarios": SCENARIOS})


@app.get("/report/{job_id}")
def report_page(request: Request, job_id: str):
    if (g := _page_guard(request, job_id)):
        return g
    if jobs.get(job_id) is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "report.html", {"job_id": job_id, "signals": SIGNALS, "voice_signals": VOICE_SIGNALS,
                                          "scenarios": SCENARIOS})


@app.get("/progress")
def progress_page(request: Request):
    if (g := _page_guard(request)):
        return g
    return templates.TemplateResponse(request, "progress.html", {"signals": SIGNALS, "voice_signals": VOICE_SIGNALS,
                                                                 "scenarios": SCENARIOS})


@app.get("/health")
def health():
    return {"message": "Kinara is running"}


# ---------- API ----------
@app.get("/api/status")
def api_status():
    return jobs.readiness()


@app.post("/api/analyze")
async def api_analyze(request: Request, background: BackgroundTasks, filename: str = "video.mp4",
                      scenario: str = "general", goal: str = ""):
    user = _need_user(request)
    ready = jobs.readiness()
    if not ready["calibrated"]:
        _fail(409, "no_calibration")
    if not ready["model_ok"]:
        _fail(409, "no_model")
    ext = Path(filename).suffix.lower()
    if ext not in jobs.ALLOWED_EXT:
        _fail(415, "bad_type")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > jobs.MAX_BYTES:
        _fail(413, "too_big")

    job_id = uuid.uuid4().hex
    part = jobs.upload_path(job_id, ".part")
    final = jobs.upload_path(job_id, ext)
    size = 0
    try:
        with open(part, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > jobs.MAX_BYTES:
                    _fail(413, "too_big")
                f.write(chunk)
        if size == 0:
            _fail(400, "empty")
        os.replace(part, final)
    finally:
        if part.exists():
            part.unlink()
    if filename.lower().startswith("recording-"):
        _remux(final)
    if not _readable(final):
        final.unlink()
        _fail(422, "bad_video")

    job = jobs.create(job_id, _display_name(filename), ext,
                      {"scenario": clean_scenario(scenario), "goal": clean_goal(goal)})
    if user is not None:
        db.create_session(job_id, user["UserID"], job["name"], job["context"], job["created"])
    background.add_task(jobs.run_job, job_id)
    return {"id": job_id}


@app.get("/api/progress")
def api_progress(request: Request):
    user = _need_user(request)
    return progress.history(only_ids=None if user is None else set(db.user_session_ids(user["UserID"])))


def _my_ids(user):
    return None if user is None else set(db.user_session_ids(user["UserID"]))


@app.get("/api/sessions")
def api_sessions(request: Request):
    """Every session of the signed-in user, newest first, with its score when it has one."""
    user = _need_user(request)
    mine = _my_ids(user)
    scored = {r["id"]: r for r in progress.history(limit=100000, only_ids=mine)}
    out = []
    for r in jobs.list_recent(100000):
        if mine is not None and r["id"] not in mine:
            continue
        sc = scored.get(r["id"])
        out.append({**r, "scenario": sc["scenario"] if sc else (jobs.get(r["id"]) or {}).get("context", {}).get("scenario", "general"),
                    "overall": sc["overall"] if sc else None, "label": sc["label"] if sc else None})
    return out


class DeleteIn(BaseModel):
    ids: list[str] = []
    all: bool = False


@app.post("/api/sessions/delete")
def api_sessions_delete(request: Request, body: DeleteIn):
    """Delete chosen sessions (or all of them): the video file, the job and the database rows."""
    user = _need_user(request)
    mine = _my_ids(user)
    ids = [r["id"] for r in jobs.list_recent(100000)] if body.all else body.ids
    deleted, busy = 0, 0
    for jid in ids:
        if mine is not None and jid not in mine:
            continue
        outcome = jobs.delete(jid)
        if outcome == "busy":
            busy += 1
            continue
        db.delete_session(jid)
        _saved.discard(jid)
        deleted += outcome != "missing"
    return {"deleted": deleted, "busy": busy}


@app.get("/api/jobs")
def api_jobs(request: Request):
    user = _need_user(request)
    rows = jobs.list_recent(200 if user is not None else 10)
    if user is not None:
        mine = set(db.user_session_ids(user["UserID"]))
        rows = [r for r in rows if r["id"] in mine][:10]
    return rows


@app.get("/api/jobs/{job_id}")
def api_job(request: Request, job_id: str):
    _owned(request, job_id)
    job = jobs.get(job_id)
    if job is None:
        _fail(404, "not_found")
    out = enrich(job)
    _sync(out)
    return out             # coach advice and score always follow the current scenario


class ContextIn(BaseModel):
    scenario: str = "general"
    goal: str = ""


@app.patch("/api/jobs/{job_id}/context")
def api_context(request: Request, job_id: str, body: ContextIn):
    _owned(request, job_id)
    ctx = {"scenario": clean_scenario(body.scenario), "goal": clean_goal(body.goal)}
    job = jobs.set_context(job_id, ctx)
    if job is None:
        _fail(404, "not_found")
    out = enrich(job)
    _saved.discard(job_id)
    _sync(out)
    return out


class ChatIn(BaseModel):
    message: str
    lang: str = "en"


def _chat_job(request, job_id):
    _owned(request, job_id)
    job = jobs.get(job_id)
    if job is None:
        _fail(404, "not_found")
    if job["status"] != "done" or not job.get("result"):
        _fail(409, "not_ready")
    return enrich(job)


class PrepIn(BaseModel):
    scenario: str = "general"
    goal: str = ""
    message: str
    history: list[dict] = []
    lang: str = "en"


@app.post("/api/prep/chat")
def api_prep_chat(request: Request, body: PrepIn):
    """Coach chat before a session exists (nothing is stored until the session is created)."""
    _need_user(request)
    try:
        msg = chat.clean_message(body.message)
    except chat.ChatError:
        _fail(400, "empty")
    try:
        out = chat.prep_reply(clean_scenario(body.scenario), body.goal, body.history, msg, "ar" if body.lang == "ar" else "en")
    except chat.ChatError as e:
        print(f"[chat] {e.code}: {e}")
        _fail(502 if e.code != "llm_busy" else 429, e.code)
    return {"reply": out["text"], "engine": chat.engine_info()}


class PrepSaveIn(BaseModel):
    messages: list[dict] = []


@app.post("/api/jobs/{job_id}/prep")
def api_prep_save(request: Request, job_id: str, body: PrepSaveIn):
    """Attach the pre-session chat to the new session (job history + Feedback rows)."""
    _owned(request, job_id)
    if jobs.get(job_id) is None:
        _fail(404, "not_found")
    msgs = [{"role": "user" if m.get("role") == "user" else "coach", "text": str(m.get("text", ""))[:2000]}
            for m in body.messages[:30] if str(m.get("text", "")).strip()]
    if msgs:
        jobs.add_chat(job_id, msgs)
        db.add_feedback(job_id, msgs)
    return {"saved": len(msgs)}


@app.get("/api/jobs/{job_id}/chat")
def api_chat_history(request: Request, job_id: str):
    job = _chat_job(request, job_id)
    return {"messages": job.get("chat") or [], "engine": chat.engine_info()}


@app.post("/api/jobs/{job_id}/chat")
def api_chat(request: Request, job_id: str, body: ChatIn):
    job = _chat_job(request, job_id)
    try:
        msg = chat.clean_message(body.message)
    except chat.ChatError:
        _fail(400, "empty")
    lang = "ar" if body.lang == "ar" else "en"
    try:
        out = chat.reply(job, msg, lang)
    except chat.ChatError as e:
        print(f"[chat] {e.code}: {e}")
        _fail(502 if e.code != "llm_busy" else 429, e.code)
    turn = [{"role": "user", "text": msg}, {"role": "coach", "text": out["text"]}]
    jobs.add_chat(job_id, turn)
    db.add_feedback(job_id, turn)
    return {"reply": out["text"], "engine": chat.engine_info()}


@app.delete("/api/jobs/{job_id}/chat")
def api_chat_clear(request: Request, job_id: str):
    _owned(request, job_id)
    if jobs.get(job_id) is None:
        _fail(404, "not_found")
    jobs.clear_chat(job_id)
    db.clear_feedback(job_id)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/video")
def api_video(request: Request, job_id: str):
    _owned(request, job_id)
    job = jobs.get(job_id)
    path = jobs.video_path(job) if job else None
    if path is None or not path.exists():
        _fail(404, "not_found")
    return FileResponse(path, media_type=MEDIA.get(job["ext"], "application/octet-stream"))


@app.delete("/api/jobs/{job_id}")
def api_delete(request: Request, job_id: str):
    _owned(request, job_id)
    outcome = jobs.delete(job_id)
    if outcome == "missing":
        _fail(404, "not_found")
    if outcome == "busy":
        _fail(409, "busy")
    db.delete_session(job_id)
    _saved.discard(job_id)
    return {"ok": True}


# ---------- accounts
class RegisterIn(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""


def _is_admin(user):
    return user is not None and db.role_name(user["RoleID"]) == "admin"


def _signed_in(user):
    res = JSONResponse({"ok": True, "name": user["FullName"]})
    res.set_cookie(auth.COOKIE, auth.make_token(user["UserID"]), max_age=auth.MAX_AGE, httponly=True, samesite="lax")
    return res


@app.get("/login")
def login_page(request: Request, next: str = "/dashboard"):
    if auth.enabled() and _user(request) is not None:
        return RedirectResponse(next if next.startswith("/") and not next.startswith("//") else "/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"next": next if next.startswith("/") and not next.startswith("//") else "/dashboard"})


@app.post("/api/register")
def api_register(body: RegisterIn):
    name, email = body.name.strip()[:120], auth.clean_email(body.email)
    if not name:
        _fail(400, "bad_name")
    if not email:
        _fail(400, "bad_email")
    if not auth.password_ok(body.password):
        _fail(400, "weak_password")
    if db.get_user_by_email(email):
        _fail(409, "email_taken")
    first = db.count_users() == 0
    user = db.create_user(name, email, auth.hash_password(body.password))
    if first:                                   # analyses made before accounts existed go to the first account
        for j in jobs.list_recent(1000):
            full = jobs.get(j["id"])
            if full:
                db.create_session(j["id"], user["UserID"], full["name"], full.get("context"), full.get("created"),
                                  "done" if full["status"] == "done" else full["status"] if full["status"] in ("error",) else "queued")
                if full["status"] == "done" and full.get("result"):
                    _saved.add(j["id"]); db.save_result(enrich(full))
    db.log("info", f"registered {email}", user["UserID"])
    return _signed_in(user)


@app.post("/api/login")
def api_login(body: LoginIn):
    email = auth.clean_email(body.email) or ""
    import time
    fails = [t for t in _bad_logins.get(email, []) if t > time.time() - 600]
    if len(fails) >= 5:
        _fail(429, "too_many")
    user = db.get_user_by_email(email) if email else None
    if user is None or not auth.verify_password(body.password, user["PasswordHash"]):
        _bad_logins[email] = fails + [time.time()]
        db.log("warning", f"failed login for {email[:80]}")
        _fail(401, "bad_login")
    _bad_logins.pop(email, None)
    return _signed_in(user)


@app.post("/api/logout")
def api_logout():
    res = JSONResponse({"ok": True})
    res.delete_cookie(auth.COOKIE)
    return res


@app.get("/api/me")
def api_me(request: Request):
    if not auth.enabled():
        return {"auth": False}
    user = _user(request)
    if user is None:
        _fail(401, "login_required")
    return {"auth": True, "name": user["FullName"], "email": user["Email"], "admin": _is_admin(user)}


# ---------- live hints while recording
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    if auth.enabled():
        uid = auth.read_token(ws.cookies.get(auth.COOKIE, ""))
        if not uid or db.get_user(uid) is None:
            await ws.close(code=4401)
            return
    await ws.accept()
    try:
        session = live.LiveSession()
    except live.LiveUnavailable as e:
        await ws.send_json({"error": e.code})
        await ws.close()
        return
    await ws.send_json({"ready": True})
    import asyncio
    try:
        while True:
            data = await ws.receive_bytes()
            try:
                out = await asyncio.to_thread(session.process, data)
            except live.LiveUnavailable as e:
                await ws.send_json({"error": e.code})
                break
            except ValueError:
                out = {"visible": False, "hints": [], "good": False, "skipped": True}
            await ws.send_json(out)
    except WebSocketDisconnect:
        pass
    except Exception as e:                       # a live-hint problem must never take the server down
        print("[live] stopped:", e)
        try:
            await ws.close()
        except Exception:
            pass
