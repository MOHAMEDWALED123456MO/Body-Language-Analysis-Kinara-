"""Chat with the coach about one analysis.

The engine is chosen from environment variables, so no code changes are needed:
  GEMINI_API_KEY  -> Google Gemini (free key from aistudio.google.com/apikey)
  GROQ_API_KEY    -> Groq (free key from console.groq.com)
  KINARA_LLM=ollama -> a model running on this computer (Ollama)
  nothing set     -> built-in rules answer simple questions from the measured results
KINARA_LLM can force one of: gemini | groq | ollama | none.

Only text goes to an online engine (the measured results and the transcript), never the video.
"""
import json
import os
import re
import urllib.error
import urllib.request

from .audio import VOICE_SIGNALS
from .registry import SIGNALS
from .roles import SCENARIOS

LABEL = {s["id"]: s for s in SIGNALS + VOICE_SIGNALS}
MAX_MESSAGE = 1000
HISTORY_SENT = 16
TRANSCRIPT_CHARS = 6000
TIMEOUT = 60


class ChatError(Exception):
    """code: no_engine | llm_failed | llm_auth | llm_busy"""

    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code


# ---------------------------------------------------------------- engine selection

def engine_name():
    forced = os.environ.get("KINARA_LLM", "").strip().lower()
    if forced in ("gemini", "groq", "ollama", "none"):
        return forced
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    return "none"


def engine_info():
    n = engine_name()
    online = n in ("gemini", "groq")
    return {"engine": n, "online": online,
            "label": {"gemini": "Google Gemini", "groq": "Groq", "ollama": "Ollama (this computer)",
                      "none": "Built-in rules"}[n]}


# ---------------------------------------------------------------- context given to the model

def _mmss(s):
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def build_context(job):
    """A compact, factual text version of the whole analysis."""
    r = job["result"]
    ctx = job.get("context") or {}
    sc = SCENARIOS.get(ctx.get("scenario"), SCENARIOS["general"])
    out = [f"Video: {job['name']}  Duration: {_mmss(r['total_seconds'])}",
           f"SCENARIO: {sc['en']} ({sc['desc_en']})"]
    if ctx.get("goal"):
        out.append(f"THE USER'S GOAL (their words): {ctx['goal']}")
    sco = r.get("score")
    if sco:
        parts = [f"overall {sco['overall']}/100 ({sco['label']['en']})"]
        if sco.get("body") is not None:
            parts.append(f"body {sco['body']}")
        if sco.get("voice") is not None:
            parts.append(f"voice {sco['voice']}")
        out.append("PRACTICE SCORE for this scenario: " + ", ".join(parts) +
                   ". Biggest point losses: " + "; ".join(f"{x['label']['en']} -{x['points']}" for x in sco["lost"]))
    out.append("\nBODY SIGNALS (share of time, number of episodes, longest episode):")
    for s in SIGNALS:
        d = r["signals"].get(s["id"])
        if d:
            out.append(f"- {s['en']}: {d['percent']}%, {d['episodes']}x, longest {d['longest']}s")
    v = r.get("voice")
    if v and not v.get("error"):
        o = v["overall"]
        out.append("\nVOICE:")
        out.append(f"- loudness {o.get('level_db')} dB ({o.get('level_note')}), speaking {int(o['speech_ratio'] * 100)}% of the time, "
                   f"pace {o.get('wpm')} words/min, pitch range {o.get('pitch_range_st')} semitones (below 2.5 = flat)")
        for s in VOICE_SIGNALS:
            d = v["signals"].get(s["id"])
            if d and d["episodes"]:
                spans = ", ".join(f"{_mmss(a)}-{_mmss(b)}" for a, b in d["spans"][:6])
                out.append(f"- {s['en']}: {d['percent']}%, {d['episodes']}x, at {spans}")
        t = v.get("transcript")
        if t:
            lines = [f"[{_mmss(g['start'])}] {g['text']}" for g in t["segments"]]
            txt = "\n".join(lines)
            out.append(f"\nTRANSCRIPT (language {t.get('language')}):\n" + txt[:TRANSCRIPT_CHARS])
    else:
        out.append("\nVOICE: not analyzed" + (f" ({v['error']})" if v else ""))
    c = r.get("coach")
    if c:
        out.append("\nCOACH FINDINGS (timestamps are m:ss):")
        for s in c["summary"]:
            out.append(f"- priority: {s['label']['en']} first at {_mmss(s['start'])}")
        for i in c["items"]:
            q = f' while saying: "{i["said"]}"' if i.get("said") else ""
            out.append(f"- {_mmss(i['start'])}-{_mmss(i['end'])} {i['label']['en']}{q}")
        for x in c["combined"]:
            out.append(f"- together at {_mmss(x['start'])}-{_mmss(x['end'])}: {x['label']['en']}")
        for s in c["strengths"]:
            out.append(f"- strength: {s['en']}")
    if r.get("baseline_adjust"):
        out.append("\nNOTE: body signals are measured relative to this person's typical posture in this video.")
    return "\n".join(out)


SYSTEM = """You are Kinara, a friendly, honest public-speaking coach. You discuss ONE analysis of a recording of the user speaking.

Rules:
- Use only the analysis data below. If something is not in it, say you can't tell from this analysis. Never invent numbers, quotes or timestamps.
- Refer to moments as m:ss so the user can jump to them in the video.
- The data are measured patterns (posture, movement, voice), not feelings. Never claim to detect lying, honesty, emotions or personality. Say "the signals suggest" or "you tend to".
- Posture signals are relative to the person's own typical posture in the video. Framing signals (too close/far, off-center) describe the camera, not the person.
- Tailor your advice to the SCENARIO and to the user's GOAL when they gave one. Give specific, practical advice: what to do differently and how to practice it. Keep answers short (under 150 words) unless asked for more.
- Reply in the same language the user writes in. If they write Arabic, use simple Egyptian Arabic.

ANALYSIS DATA:
"""


# ---------------------------------------------------------------- online / local engines

def _post(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "Kinara/1.0 (local coaching app)",
                                          "Accept": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        low = body.lower()
        if e.code == 403 and "1010" in low:                      # Cloudflare rejected the client signature
            raise ChatError("llm_failed", f"HTTP 403 blocked before reaching the engine: {body}")
        if e.code in (401, 403) or "api key not valid" in low or "api_key_invalid" in low or "invalid api key" in low:
            raise ChatError("llm_auth", f"HTTP {e.code} {body}")
        if e.code == 429:
            raise ChatError("llm_busy", body)
        raise ChatError("llm_failed", f"HTTP {e.code} {body}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ChatError("llm_failed", str(e))


def _get(url, headers):
    req = urllib.request.Request(url, headers={"User-Agent": "Kinara/1.0 (local coaching app)", **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ChatError("llm_auth" if e.code in (401, 403) else "llm_failed", f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ChatError("llm_failed", str(e))


GROQ_PREFER = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]
GROQ_SKIP = ("whisper", "guard", "tts", "playai", "distil", "orpheus", "embed", "safeguard")
_groq_cache = {}


def groq_models():
    data = _get("https://api.groq.com/openai/v1/models", {"Authorization": "Bearer " + os.environ.get("GROQ_API_KEY", "")})
    return [m["id"] for m in data.get("data", []) if "id" in m]


def _groq_model():
    """GROQ_MODEL if set, otherwise the best chat model this account can use (asked from Groq once)."""
    env = os.environ.get("GROQ_MODEL")
    if env:
        return env
    key = os.environ.get("GROQ_API_KEY", "")
    if key not in _groq_cache:
        ids = groq_models()
        chat_ids = [i for i in ids if not any(w in i.lower() for w in GROQ_SKIP)]
        pick = next((m for m in GROQ_PREFER if m in chat_ids), None) or (chat_ids[0] if chat_ids else None)
        if not pick:
            raise ChatError("llm_failed", "this Groq account has no chat models available")
        _groq_cache[key] = pick
    return _groq_cache[key]


def _gemini_urls(model, key):
    studio = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    vertex = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent"
    # keys that start with "AQ." come from Vertex AI express mode, "AIza..." from Google AI Studio
    return [vertex, studio] if key.startswith("AQ.") else [studio, vertex]


def _gemini(system, history):
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    key = os.environ.get("GEMINI_API_KEY", "")
    payload = {"system_instruction": {"parts": [{"text": system}]},
               "contents": [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["text"]}]} for m in history],
               "generationConfig": {"temperature": 0.5, "maxOutputTokens": 700}}
    first, data = None, None
    for url in _gemini_urls(model, key):
        try:
            data = _post(url, payload, {"x-goog-api-key": key})
            break
        except ChatError as e:
            if e.code == "llm_busy":
                raise
            first = first or e
    if data is None:
        raise first
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except (KeyError, IndexError, TypeError):
        raise ChatError("llm_failed", "empty answer")


def _groq(system, history):
    model = _groq_model()
    msgs = [{"role": "system", "content": system}] + \
           [{"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]} for m in history]
    data = _post("https://api.groq.com/openai/v1/chat/completions",
                 {"model": model, "messages": msgs, "temperature": 0.5, "max_tokens": 700},
                 {"Authorization": "Bearer " + os.environ.get("GROQ_API_KEY", "")})
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise ChatError("llm_failed", "empty answer")


def _ollama(system, history):
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    msgs = [{"role": "system", "content": system}] + \
           [{"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]} for m in history]
    data = _post(host + "/api/chat", {"model": model, "messages": msgs, "stream": False}, {})
    try:
        return data["message"]["content"].strip()
    except (KeyError, TypeError):
        raise ChatError("llm_failed", "empty answer")


ENGINES = {"gemini": _gemini, "groq": _groq, "ollama": _ollama}


# ---------------------------------------------------------------- built-in rules (no AI engine)

def _pick(o, lang):
    return o["ar"] if lang == "ar" else o["en"]


def _rules(job, question, lang):
    c = job["result"].get("coach") or {}
    q = question.lower()
    ar = lang == "ar"

    def has(*words):
        return any(w in q for w in words)

    lines = []
    if has("first", "priority", "improve", "work on", "start", "أول", "ابدأ", "اشتغل", "أحسن", "اتحسن", "نصيح", "نصايح"):
        for s in c.get("summary", []):
            lines.append(f"{_mmss(s['start'])} – {_pick(s['label'], lang)}: {_pick(s['tip'], lang)}")
    elif has("voice", "speak", "pace", "pause", "loud", "tone", "صوت", "كلام", "سرعة", "نغمة"):
        for i in c.get("items", []):
            if i["kind"] == "voice":
                lines.append(f"{_mmss(i['start'])} – {_pick(i['label'], lang)}: {_pick(i['tip'], lang)}")
        v = job["result"].get("voice") or {}
        o = v.get("overall") if not v.get("error") else None
        if o and not lines:
            lines.append(("صوتك كان ثابت من غير مشاكل واضحة." if ar else "Your voice showed no clear problems.") +
                         f" ({o.get('level_db')} dB, {o.get('wpm')} wpm)")
    elif has("posture", "body", "movement", "sway", "lean", "جسم", "وقفة", "جلسة", "حركة", "ضهر"):
        for i in c.get("items", []):
            if i["kind"] == "body":
                lines.append(f"{_mmss(i['start'])} – {_pick(i['label'], lang)}: {_pick(i['tip'], lang)}")
    elif has("good", "strength", "well", "كويس", "حلو", "ممتاز", "مميز"):
        lines = [_pick(s, lang) for s in c.get("strengths", [])]
    if lines:
        return "\n".join(lines[:6])
    if has("hello", "hi", "مرحبا", "اهلا", "أهلا", "ازيك", "سلام"):
        return ("أهلاً! اسألني عن نصايحك الأولى أو عن الصوت أو الجسم أو اللي كان كويس." if ar else
                "Hi! Ask me what to work on first, or about your voice, your body, or what went well.")
    return ("أنا دلوقتي برد من القواعد الجاهزة بس. جرّب: \"أبدأ بإيه؟\" أو \"إيه نصايح الصوت؟\" أو \"إيه اللي كان كويس؟\". "
            "ولو عايز نقاش أعمق، فعّل محرك ذكاء اصطناعي (Gemini مجاني) من إعدادات الجهاز." if ar else
            "I'm answering from built-in rules right now. Try: \"What should I work on first?\", \"Any voice tips?\" or "
            "\"What went well?\". For a deeper conversation, enable an AI engine (a free Gemini key works).")


# ---------------------------------------------------------------- public API

def clean_message(text):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        raise ChatError("empty")
    return text[:MAX_MESSAGE]


def reply(job, message, lang="en"):
    """Returns {'text', 'engine'}. History is job['chat'] (list of {role, text}); the caller stores it."""
    name = engine_name()
    history = [{"role": m["role"], "text": m["text"]} for m in (job.get("chat") or [])][-HISTORY_SENT:]
    history.append({"role": "user", "text": message})
    if name == "none":
        return {"text": _rules(job, message, lang), "engine": "none"}
    system = SYSTEM + build_context(job)
    text = ENGINES[name](system, history)
    if not text:
        raise ChatError("llm_failed", "empty answer")
    return {"text": text, "engine": name}
