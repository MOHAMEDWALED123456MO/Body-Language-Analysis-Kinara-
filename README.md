# Kinara — Body Language & Voice Coach

Kinara analyzes a video of you speaking and gives you specific, time-stamped feedback on your posture, gestures, and voice. It runs on your own machine, supports Arabic and English, and works for interviews, presentations, online meetings, and public speeches.

> **Privacy:** video and audio are processed on your own device and are not sent to third parties. If you enable an AI chat engine, only the transcript and measured signals (text only) are sent — never the video.

---

## Features

- **12 body signals** tracked frame by frame: slouch, lean forward/back, shoulder tilt/raise, sway, fidget, freeze, turned away, distance, off-center, upright posture
- **5 voice signals**: voice dropped, flat voice, long pauses, fast/slow speech
- **Personalized calibration** — you perform a few poses and Kinara learns your own thresholds
- **Scenario-aware scoring** for: job interview, presentation, online meeting, public speech, general practice
- **Live hints while recording** — gentle on-screen hints via WebSocket
- **Coach chat** about each analysis — Gemini, Groq, Ollama, or built-in rules (offline)
- **Printable PDF report** with score, priorities, timeline, transcript
- **Bilingual UI** (Arabic / English) with RTL/LTR
- **Admin panel** for users and system logs
- **Multi-database** — SQLite (default), SQL Server, MySQL

---

## Requirements

- **Python 3.11+**
- **Webcam + microphone** (for calibration and recording)
- **ffmpeg** — not required to install system-wide; `imageio-ffmpeg` ships a binary
- **Modern browser** — Chrome, Edge, or Firefox
- A desktop environment for the calibration wizard (it uses `cv2.imshow`)

---

## Quick start

### 1. Clone & install

```bash
git clone https://github.com/MOHAMEDWALED123456MO/Body-Language-Analysis-Kinara-.git
cd Body-Language-Analysis-Kinara-/backend

python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# edit .env and set at least KINARA_SECRET
```

If you want chat with a real AI engine, add `GEMINI_API_KEY` or `GROQ_API_KEY` (both have free tiers). Otherwise the built-in rules answer simple questions.

### 3. Calibrate (first time only)

```bash
python calibrate.py
```

This opens your webcam and walks you through 8 short poses (neutral, lean forward, lean back, slouch, shrug, tilt, turn, talk). It learns **your** personal thresholds and saves them to `engine/profiles/default.json`. Until you do this, the analyze page will refuse uploads with `no_calibration`.

### 4. Run the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000> in your browser. The first registered account becomes the admin.

---

## Environment variables

All variables are optional unless noted. See `.env.example` for a ready-to-edit template.

| Variable | Default | Purpose |
|---|---|---|
| `KINARA_AUTH` | `on` | `on` = require login; `off` = open access (single-user mode) |
| `KINARA_SECRET` | random, saved to `data/secret.key` | HMAC key for signing session cookies. **Set this in production.** |
| `KINARA_DB` | `sqlite:///data/kinara.db` | SQLAlchemy URL. Examples below. |
| `KINARA_LLM` | auto-detected | Force one of: `gemini`, `groq`, `ollama`, `none` |
| `GEMINI_API_KEY` | — | Google AI Studio key (<https://aistudio.google.com/apikey>) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any Gemini model name |
| `GROQ_API_KEY` | — | Groq key (<https://console.groq.com>) |
| `GROQ_MODEL` | auto-picked from available chat models | Override the model id |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Local model name |
| `KINARA_STT_MODEL` | `small` | Whisper model size: `small` / `medium` / `large-v3` |
| `KINARA_STT_LANG` | auto-detect | Force `ar` / `en` / etc. |

### Loading `.env` automatically

The app reads from `os.environ` directly. To load a `.env` file:

**Option A — shell:**
```bash
set -a; source .env; set +a
uvicorn main:app --reload
```

**Option B — python-dotenv (recommended):**
```bash
pip install python-dotenv
```
Then add at the very top of `main.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

**Option C — direnv:** install direnv, then `cp .env.example .envrc` and edit.

---

## Database

**SQLite (default, zero config):** a file at `data/kinara.db` is auto-created on first run.

**SQL Server** (run `db/schema_sqlserver.sql` in SSMS first):
```
KINARA_DB=mssql+pyodbc://@localhost/kinara?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
```

**MySQL** (run `db/schema_mysql.sql` first):
```
KINARA_DB=mysql+pymysql://user:pass@localhost/kinara
```

Verify the connection:
```bash
python check_db.py
```

---

## LLM engines for the coach chat

The coach can discuss your analysis with one of four engines. Only the transcript and measured signals (text) are sent — never the video.

| Engine | Setup | Online? |
|---|---|---|
| **Built-in rules** (default) | Nothing | No — fully offline |
| **Google Gemini** | `GEMINI_API_KEY=...` | Yes |
| **Groq** | `GROQ_API_KEY=...` | Yes |
| **Ollama** | Install Ollama locally, `KINARA_LLM=ollama` | No — local |

Test the engine from the terminal:
```bash
python check_llm.py
```

---

## CLI tools

| Command | What it does |
|---|---|
| `python calibrate.py` | Interactive webcam calibration wizard |
| `python analyze_video.py "talk.mp4"` | Analyze one video (body only) and print diagnostics |
| `python analyze_audio.py "talk.mp4"` | Analyze audio + transcript of one video |
| `python live_pose.py` | Live pose signals in a desktop window |
| `python check_db.py` | Verify DB connection and list tables |
| `python check_llm.py` | Verify the AI engine is reachable and answers |

---

## Project layout

```
backend/
├── main.py              # FastAPI app — all routes
├── calibrate.py         # Webcam calibration wizard (CLI)
├── analyze_video.py     # CLI: body analysis of one video
├── analyze_audio.py     # CLI: voice analysis of one video
├── live_pose.py         # Live pose signals in a desktop window
├── check_db.py          # DB connection check
├── check_llm.py         # LLM engine check
├── pose_test.py         # Quick pose detector sanity test (needs webcam)
├── test_camera.py       # Quick webcam sanity test
├── requirements.txt     # Python dependencies
├── .env.example         # Copy to .env and edit
│
├── engine/              # Core logic (no FastAPI imports here)
│   ├── config.py        # Sensitivity constants
│   ├── pose_model.py    # MediaPipe wrapper
│   ├── pose_signals.py  # Per-frame metrics → debounced signals
│   ├── video_runner.py  # Run the engine on a video file
│   ├── audio.py         # Voice analysis + faster-whisper
│   ├── profile.py       # Calibration math → thresholds
│   ├── calibration.py   # The interactive wizard
│   ├── roles.py         # Scenario definitions + scoring
│   ├── coach.py         # Rule-based advice (deterministic)
│   ├── chat.py          # LLM chat (Gemini/Groq/Ollama + rules)
│   ├── live.py          # WebSocket live hints during recording
│   ├── jobs.py          # Background analysis jobs (JSON files)
│   ├── progress.py      # History for the progress page
│   ├── auth.py          # scrypt + HMAC signed cookies
│   ├── db.py            # SQLAlchemy Core layer
│   └── registry.py      # Signal definitions
│
├── static/              # Frontend (vanilla JS, no build step)
├── templates/           # Jinja2 HTML
├── db/                  # SQL schemas: sqlite / sqlserver / mysql
├── models/              # pose_landmarker_lite.task (MediaPipe model)
├── tests/               # pytest suite (12 files)
│
├── data/                # auto-created (gitignored): uploads, jobs, sqlite db
└── reports/             # auto-created: JSON dumps from analyze_video.py
```

---

## Testing

```bash
pytest
```

The suite covers pose signals, voice analysis, chat (all engines), accounts & ownership, the full upload→analyze→delete flow, WebSocket live hints, the printable report, and edge cases (corrupt video, missing calibration, server restart mid-analysis, etc.).

Tests run with `KINARA_AUTH=off` and a throwaway SQLite DB by default (see `tests/conftest.py`).

---

## Privacy & data

- Your recordings stay on the machine running the server (under `data/uploads/`).
- The SQLite database (`data/kinara.db`) stores accounts, sessions, scores, and chat messages.
- You can delete any session from the **My sessions** page, or your entire account from **Profile → Delete account**.
- The session cookie is HMAC-signed with `KINARA_SECRET`. Set a stable secret in production so users don't get logged out on restart.
- Passwords are hashed with **scrypt** (N=2¹⁴, r=8, p=1, dklen=32, 16-byte salt).

---

## Notes & limitations

- **Calibration requires a desktop** (uses `cv2.imshow`). On a headless server, calibrate on your laptop first, then copy `engine/profiles/default.json` to the server.
- **Arabic dialects**: speech-to-text accuracy is higher on Modern Standard Arabic than on Egyptian colloquial.
- **One analysis at a time** — the job runner uses a single in-process lock. Fine for single-user or low-traffic use; for many concurrent users, swap `BackgroundTasks` for a real queue (RQ / Celery / Dramatiq).
- **Kinara reports signals, not verdicts.** It does not detect lying, emotions, or personality. The score is a practice aid, not a judgment.

---

## License

You own this project — set your own license in `LICENSE` if you plan to publish.
