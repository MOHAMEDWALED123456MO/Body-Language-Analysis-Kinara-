import pytest

from engine import chat, jobs
from test_web import client, video_bytes  # noqa: F401  (pytest fixture + helper)


def make_job(client, tmp_path):
    r = client.post("/api/analyze?filename=talk.mp4", content=video_bytes(tmp_path))
    return r.json()["id"]


@pytest.fixture(autouse=True)
def no_engine(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "KINARA_LLM", "GEMINI_MODEL", "GROQ_MODEL", "OLLAMA_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_rules_engine_and_memory(client, tmp_path):
    jid = make_job(client, tmp_path)
    r = client.post(f"/api/jobs/{jid}/chat", json={"message": "What should I work on first?", "lang": "en"})
    assert r.status_code == 200 and r.json()["engine"]["engine"] == "none"
    assert ":" in r.json()["reply"] and len(r.json()["reply"]) > 20
    r2 = client.post(f"/api/jobs/{jid}/chat", json={"message": "ايه اللي كان كويس؟", "lang": "ar"})
    assert r2.status_code == 200
    h = client.get(f"/api/jobs/{jid}/chat").json()
    assert [m["role"] for m in h["messages"]] == ["user", "coach", "user", "coach"]
    assert client.delete(f"/api/jobs/{jid}/chat").json() == {"ok": True}
    assert client.get(f"/api/jobs/{jid}/chat").json()["messages"] == []


def test_history_survives_restart(client, tmp_path):
    jid = make_job(client, tmp_path)
    client.post(f"/api/jobs/{jid}/chat", json={"message": "hi", "lang": "en"})
    jobs.reset_memory()
    assert len(client.get(f"/api/jobs/{jid}/chat").json()["messages"]) == 2


def test_gemini_gets_context_history_and_key(client, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    seen = []

    def fake_post(url, payload, headers):
        seen.append((url, payload, headers))
        return {"candidates": [{"content": {"parts": [{"text": "Try slowing down at 0:12."}]}}]}
    monkeypatch.setattr(chat, "_post", fake_post)
    jid = make_job(client, tmp_path)
    r = client.post(f"/api/jobs/{jid}/chat", json={"message": "How was my pace?", "lang": "en"})
    assert r.json()["reply"] == "Try slowing down at 0:12." and r.json()["engine"]["online"]
    client.post(f"/api/jobs/{jid}/chat", json={"message": "And my posture?", "lang": "en"})
    url, payload, headers = seen[-1]
    assert "gemini" in url and headers["x-goog-api-key"] == "secret-key" and "secret-key" not in url
    system = payload["system_instruction"]["parts"][0]["text"]
    assert "ANALYSIS DATA" in system and "hello" in system and "Leaning forward" in system
    roles = [c["role"] for c in payload["contents"]]
    assert roles == ["user", "model", "user"]
    assert payload["contents"][-1]["parts"][0]["text"] == "And my posture?"


def test_groq_and_ollama_shapes(client, tmp_path, monkeypatch):
    jid = make_job(client, tmp_path)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("GROQ_MODEL", "some-model")
    monkeypatch.setattr(chat, "_post", lambda u, p, h: {"choices": [{"message": {"content": "groq says hi"}}]})
    assert client.post(f"/api/jobs/{jid}/chat", json={"message": "x"}).json()["reply"] == "groq says hi"
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.setenv("KINARA_LLM", "ollama")
    monkeypatch.setattr(chat, "_post", lambda u, p, h: {"message": {"content": "local says hi"}})
    r = client.post(f"/api/jobs/{jid}/chat", json={"message": "y"}).json()
    assert r["reply"] == "local says hi" and not r["engine"]["online"]


@pytest.mark.parametrize("code,status", [("llm_auth", 502), ("llm_failed", 502), ("llm_busy", 429)])
def test_engine_errors_are_reported_and_not_saved(client, tmp_path, monkeypatch, code, status):
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    def boom(*a):
        raise chat.ChatError(code, "details")
    monkeypatch.setattr(chat, "_post", boom)
    jid = make_job(client, tmp_path)
    r = client.post(f"/api/jobs/{jid}/chat", json={"message": "hello"})
    assert r.status_code == status and r.json()["detail"]["code"] == code
    assert client.get(f"/api/jobs/{jid}/chat").json()["messages"] == []


def test_validation(client, tmp_path):
    jid = make_job(client, tmp_path)
    assert client.post(f"/api/jobs/{jid}/chat", json={"message": "   "}).status_code == 400
    assert client.post("/api/jobs/" + "0" * 32 + "/chat", json={"message": "hi"}).status_code == 404
    job = jobs.create("a" * 32, "q.mp4", ".mp4")
    assert client.post(f"/api/jobs/{job['id']}/chat", json={"message": "hi"}).status_code == 409
    long = client.post(f"/api/jobs/{jid}/chat", json={"message": "x" * 5000}).status_code
    assert long == 200
    assert len(client.get(f"/api/jobs/{jid}/chat").json()["messages"][-2]["text"]) == chat.MAX_MESSAGE


def test_context_has_the_facts(client, tmp_path):
    jid = make_job(client, tmp_path)
    ctx = chat.build_context(jobs.get(jid))
    assert "BODY SIGNALS" in ctx and "VOICE" in ctx and "TRANSCRIPT" in ctx and "COACH FINDINGS" in ctx


def test_requests_carry_a_client_name(monkeypatch):
    import io
    import urllib.request
    seen = {}

    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        seen.update({k.lower(): v for k, v in req.header_items()})
        return R(b'{"ok": 1}')
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert chat._post("https://example.invalid/x", {"a": 1}, {"Authorization": "Bearer k"}) == {"ok": 1}
    assert seen["user-agent"].startswith("Kinara/") and seen["authorization"] == "Bearer k"


def test_requests_carry_a_custom_user_agent(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": 1}'

    def fake_urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        seen["auth"] = req.get_header("Authorization")
        return Resp()
    monkeypatch.setattr(chat.urllib.request, "urlopen", fake_urlopen)
    assert chat._post("https://example.test/x", {"a": 1}, {"Authorization": "Bearer k"}) == {"ok": 1}
    assert seen["ua"].startswith("Kinara/") and seen["auth"] == "Bearer k"


def test_groq_picks_an_available_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    chat._groq_cache.clear()
    listing = {"data": [{"id": "whisper-large-v3"}, {"id": "meta-llama/llama-guard-4"}, {"id": "llama-3.1-8b-instant"},
                        {"id": "openai/gpt-oss-20b"}]}
    monkeypatch.setattr(chat, "_get", lambda u, h: listing)
    assert chat._groq_model() == "openai/gpt-oss-20b"
    sent = {}
    monkeypatch.setattr(chat, "_post", lambda u, p, h: sent.update(p) or {"choices": [{"message": {"content": "hi"}}]})
    assert chat._groq("sys", [{"role": "user", "text": "q"}]) == "hi" and sent["model"] == "openai/gpt-oss-20b"
    monkeypatch.setenv("GROQ_MODEL", "my-model")
    assert chat._groq_model() == "my-model"
    chat._groq_cache.clear()
    monkeypatch.delenv("GROQ_MODEL")
    monkeypatch.setattr(chat, "_get", lambda u, h: {"data": [{"id": "whisper-large-v3"}]})
    with pytest.raises(chat.ChatError):
        chat._groq_model()
    chat._groq_cache.clear()
