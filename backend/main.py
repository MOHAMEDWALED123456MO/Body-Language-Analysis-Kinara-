import os
import re
import uuid
from pathlib import Path

import cv2
from pydantic import BaseModel
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from engine import chat, jobs
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


# ---------- pages ----------
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/analyze")
def analyze_page(request: Request):
    return templates.TemplateResponse(request, "analyze.html", {"scenarios": SCENARIOS})


@app.get("/results/{job_id}")
def results_page(request: Request, job_id: str):
    if jobs.get(job_id) is None:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "results.html", {"job_id": job_id, "signals": SIGNALS, "voice_signals": VOICE_SIGNALS,
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
    if not _readable(final):
        final.unlink()
        _fail(422, "bad_video")

    jobs.create(job_id, _display_name(filename), ext,
                {"scenario": clean_scenario(scenario), "goal": clean_goal(goal)})
    background.add_task(jobs.run_job, job_id)
    return {"id": job_id}


@app.get("/api/jobs")
def api_jobs():
    return jobs.list_recent(10)


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        _fail(404, "not_found")
    return enrich(job)             # coach advice and score always follow the current scenario


class ContextIn(BaseModel):
    scenario: str = "general"
    goal: str = ""


@app.patch("/api/jobs/{job_id}/context")
def api_context(job_id: str, body: ContextIn):
    ctx = {"scenario": clean_scenario(body.scenario), "goal": clean_goal(body.goal)}
    job = jobs.set_context(job_id, ctx)
    if job is None:
        _fail(404, "not_found")
    return enrich(job)


class ChatIn(BaseModel):
    message: str
    lang: str = "en"


def _chat_job(job_id):
    job = jobs.get(job_id)
    if job is None:
        _fail(404, "not_found")
    if job["status"] != "done" or not job.get("result"):
        _fail(409, "not_ready")
    return enrich(job)


@app.get("/api/jobs/{job_id}/chat")
def api_chat_history(job_id: str):
    job = _chat_job(job_id)
    return {"messages": job.get("chat") or [], "engine": chat.engine_info()}


@app.post("/api/jobs/{job_id}/chat")
def api_chat(job_id: str, body: ChatIn):
    job = _chat_job(job_id)
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
    jobs.add_chat(job_id, [{"role": "user", "text": msg}, {"role": "coach", "text": out["text"]}])
    return {"reply": out["text"], "engine": chat.engine_info()}


@app.delete("/api/jobs/{job_id}/chat")
def api_chat_clear(job_id: str):
    if jobs.get(job_id) is None:
        _fail(404, "not_found")
    jobs.clear_chat(job_id)
    return {"ok": True}


@app.get("/api/jobs/{job_id}/video")
def api_video(job_id: str):
    job = jobs.get(job_id)
    path = jobs.video_path(job) if job else None
    if path is None or not path.exists():
        _fail(404, "not_found")
    return FileResponse(path, media_type=MEDIA.get(job["ext"], "application/octet-stream"))


@app.delete("/api/jobs/{job_id}")
def api_delete(job_id: str):
    outcome = jobs.delete(job_id)
    if outcome == "missing":
        _fail(404, "not_found")
    if outcome == "busy":
        _fail(409, "busy")
    return {"ok": True}
