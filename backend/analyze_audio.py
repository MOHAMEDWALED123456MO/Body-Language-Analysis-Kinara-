import sys
import tempfile

from engine import audio as A

if len(sys.argv) < 2:
    print('Usage:  python analyze_audio.py "path\\to\\video.mp4"  [--no-text]')
    sys.exit(1)

path = sys.argv[1]
with_text = "--no-text" not in sys.argv
if with_text:
    print("Transcribing (first run downloads the speech model, ~500 MB, be patient)...")

try:
    with tempfile.TemporaryDirectory() as tmp:
        res = A.analyze_video_audio(path, tmp, with_text=with_text)
except A.AudioError as e:
    msgs = {"no_audio": "This video has no audio track.",
            "no_ffmpeg": "ffmpeg is missing. Run:  pip install imageio-ffmpeg",
            "bad_audio": "Could not read the audio: " + str(e)}
    print(msgs.get(e.code, str(e)))
    sys.exit(1)

o = res["overall"]
print(f"\nAudio: {o['duration']}s   speaking {o['speech_seconds']}s ({int(o['speech_ratio'] * 100)}%)")
if o["level_note"] == "no_speech":
    print("No speech detected.")
    sys.exit(0)
note = {"ok": "ok", "low": "LOW - mic is weak or you are far from it", "loud": "very loud / may be clipping"}[o["level_note"]]
print(f"Loudness: {o['level_db']} dB ({note})   Noise floor: {o['noise_floor_db']} dB")
print(f"Pitch variation (typical range): {o['pitch_range_st']} semitones   (below {A.MONOTONE_RANGE_ST} = flat)")
print("Speaking pace:", f"{int(o['wpm'])} words/min" if o["wpm"] else "n/a (no transcript)")

print(f"\n{'Signal':26s}{'%time':>7s}{'episodes':>10s}{'longest':>9s}")
for s in A.VOICE_SIGNALS:
    d = res["signals"][s["id"]]
    print(f"{s['en']:26s}{d['percent']:>6.1f}%{d['episodes']:>10d}{d['longest']:>8.1f}s")

for s in A.VOICE_SIGNALS:
    d = res["signals"][s["id"]]
    if d["spans"]:
        top = sorted(d["spans"], key=lambda x: x[0] - x[1])[:3]
        print(f"  {s['en']}: " + ", ".join(f"{a:.0f}s-{b:.0f}s" for a, b in top))

t = res["transcript"]
if t:
    print(f"\nLanguage: {t['language']}   words: {len(t['words'])}")
    print("Transcript start:", t["text"][:400])
elif res["stt_note"] == "no_stt":
    print("\n(No transcript: run  pip install faster-whisper  to add speech-to-text.)")
