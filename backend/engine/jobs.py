"""Background analysis jobs for the website. No database yet: one JSON file per job."""
import json
import os
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import audio as _audio
from .coach import build_advice
from .roles import DEFAULT as DEFAULT_SCENARIO
from .pose_model import create_landmarker, detect
from .profile import load_profile
from .video_runner import analyze_video

DATA_DIR = Path("data")
PROFILE_PATH = "engine/profiles/default.json"
MODEL_PATH = "models/pose_landmarker_lite.task"
ALLOWED_EXT = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")
MAX_BYTES = 1024 ** 3
ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _default_factory():
    return create_landmarker(MODEL_PATH)


DETECT_FN = detect                      # tests replace these two
LANDMARKER_FACTORY = _default_factory
AUDIO_FN = _audio.analyze_video_audio   # tests replace this too

_run_lock = threading.Lock()            # one analysis at a time
_mem_lock = threading.Lock()
_mem = {}
_landmarker = None


def valid_id(job_id):
    return bool(job_id) and bool(ID_RE.match(job_id))


def _dir(kind):
    p = DATA_DIR / kind
    p.mkdir(parents=True, exist_ok=True)
    return p


def upload_path(job_id, ext):
    return _dir("uploads") / f"{job_id}{ext}"


def video_path(job):
    return upload_path(job["id"], job["ext"])


def _job_file(job_id):
    return _dir("jobs") / f"{job_id}.json"


def _json_default(o):
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"not serializable: {type(o)}")


def _write(job):
    f = _job_file(job["id"])
    tmp = f.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, default=_json_default)
    os.replace(tmp, f)


def _touch(job):
    with _mem_lock:
        _mem[job["id"]] = job
    _write(job)


def reset_memory():
    global _landmarker
    with _mem_lock:
        _mem.clear()
    _landmarker = None


def readiness():
    return {"calibrated": os.path.exists(PROFILE_PATH), "model_ok": os.path.exists(MODEL_PATH)}


def create(job_id, name, ext, context=None):
    job = {"id": job_id, "name": name, "ext": ext, "status": "queued", "progress": 0.0,
           "context": context or {"scenario": DEFAULT_SCENARIO, "goal": ""},
           "created": datetime.now().astimezone().isoformat(timespec="seconds"),
           "error": None, "error_code": None, "result": None}
    _touch(job)
    return job


def get(job_id):
    if not valid_id(job_id):
        return None
    with _mem_lock:
        job = _mem.get(job_id)
    if job is not None:
        return job
    f = _job_file(job_id)
    if not f.exists():
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            job = json.load(fh)
    except (OSError, ValueError):
        return None
    with _mem_lock:
        _mem[job_id] = job
    return job


def list_recent(n=10):
    files = sorted(_dir("jobs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:n]:
        job = get(f.stem)
        if job is None:
            continue
        res = job.get("result") or {}
        out.append({"id": job["id"], "name": job["name"], "status": job["status"],
                    "created": job["created"], "duration": res.get("total_seconds")})
    return out


def delete(job_id):
    job = get(job_id)
    if job is None:
        return "missing"
    if job["status"] in ("queued", "processing"):
        return "busy"
    for p in (video_path(job), _job_file(job_id)):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    with _mem_lock:
        _mem.pop(job_id, None)
    return "ok"


def set_context(job_id, context):
    job = get(job_id)
    if job is None:
        return None
    with _mem_lock:
        job["context"] = context
    _touch(job)
    return job


def add_chat(job_id, messages):
    job = get(job_id)
    if job is None:
        return
    with _mem_lock:
        job.setdefault("chat", []).extend(messages)
    _touch(job)


def clear_chat(job_id):
    job = get(job_id)
    if job is None:
        return
    with _mem_lock:
        job["chat"] = []
    _touch(job)


def recover():
    """After a restart, jobs that were mid-analysis can never finish: mark them failed."""
    for f in _dir("jobs").glob("*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                job = json.load(fh)
        except (OSError, ValueError):
            continue
        if job.get("status") in ("queued", "processing"):
            job.update(status="error", error_code="interrupted", error="server restarted")
            _write(job)
    for p in _dir("uploads").glob("*.part"):
        try:
            os.remove(p)
        except OSError:
            pass


def _get_landmarker():
    global _landmarker
    if _landmarker is None:
        if LANDMARKER_FACTORY is _default_factory and not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(MODEL_PATH)
        _landmarker = LANDMARKER_FACTORY()
    return _landmarker


def _voice(job, progress):
    """Voice never breaks the job: any failure becomes {'error': code} next to the body result."""
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as tmp:
            return AUDIO_FN(str(video_path(job)), tmp, progress=progress)
    except _audio.AudioError as e:
        return {"error": e.code}
    except Exception as e:
        traceback.print_exc()
        return {"error": "internal", "detail": f"{type(e).__name__}: {e}"}


def run_job(job_id):
    job = get(job_id)
    if job is None:
        return
    with _run_lock:
        job["status"] = "processing"
        _touch(job)
        last = [0.0]

        def report(frac):
            job["progress"] = round(float(frac), 3)
            now = time.monotonic()
            if now - last[0] > 0.5 or frac >= 1.0:
                last[0] = now
                _touch(job)

        def progress(p):                 # body analysis = first half of the bar
            job["stage"] = "body"
            report(0.5 * float(p))

        def voice_progress(q):           # voice and transcript = second half
            job["stage"] = "voice"
            report(0.5 + 0.5 * float(q))

        try:
            profile = load_profile(PROFILE_PATH)
            result = analyze_video(str(video_path(job)), _get_landmarker(), profile,
                                   detect_fn=DETECT_FN, progress=progress)
            voice_progress(0.0)
            result["voice"] = _voice(job, voice_progress)
            result["coach"] = build_advice(result, (job.get("context") or {}).get("scenario"))
            job.update(status="done", progress=1.0, stage=None, result=result, error=None, error_code=None)
        except FileNotFoundError as e:
            code = "no_calibration" if not os.path.exists(PROFILE_PATH) else "no_model"
            job.update(status="error", error_code=code, error=str(e))
        except RuntimeError as e:
            job.update(status="error", error_code="bad_video", error=str(e))
        except Exception as e:          # keep the server alive, show details in the terminal
            traceback.print_exc()
            job.update(status="error", error_code="internal", error=f"{type(e).__name__}: {e}")
        _touch(job)
