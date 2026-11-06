"""Tests the AI engine from the terminal and prints the exact reason if it fails (never prints your key)."""
import os
import sys

from engine import chat

info = chat.engine_info()
print("Engine:", info["label"])
if info["engine"] == "none":
    print("No engine is configured. Set GEMINI_API_KEY (or GROQ_API_KEY) in this same window first.")
    sys.exit(1)
key = {"gemini": os.environ.get("GEMINI_API_KEY", ""), "groq": os.environ.get("GROQ_API_KEY", "")}.get(info["engine"], "")
print("Key starts with:", key[:4] + "…", "| length:", len(key))
if info["engine"] == "groq":
    try:
        ids = chat.groq_models()
        print("Models available to this key:", ", ".join(ids[:20]))
        print("Model that will be used:", chat._groq_model())
    except chat.ChatError as e:
        print("Could not list models:", e.code, str(e)[:300])
try:
    out = chat.ENGINES[info["engine"]]("Answer in one short sentence.", [{"role": "user", "text": "Say hello to Kinara."}])
    print("OK, the engine answered:", out)
except chat.ChatError as e:
    print("FAILED:", e.code)
    print("Details:", str(e)[:600].replace(key, "***") if key else str(e)[:600])
