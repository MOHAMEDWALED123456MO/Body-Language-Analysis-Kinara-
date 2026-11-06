import subprocess
import wave

import numpy as np
import pytest

from engine import audio as A

SR = A.SR


def voiced(dur, f0_fn, level_db, am_hz=4.0):
    t = np.arange(int(dur * SR)) / SR
    f0 = f0_fn(t)
    ph = 2 * np.pi * np.cumsum(f0) / SR
    sig = sum(np.sin(k * ph) / k for k in (1, 2, 3, 4))
    sig *= 0.6 + 0.4 * np.abs(np.sin(np.pi * am_hz * t * 0.5))      # syllable-like pulsing
    sig = sig / np.sqrt(np.mean(sig ** 2)) * 10 ** (level_db / 20)
    return sig.astype(np.float32)


def silence(dur, rng):
    return (rng.standard_normal(int(dur * SR)) * 10 ** (-65 / 20)).astype(np.float32)


def sample():
    rng = np.random.default_rng(1)
    vary = lambda t: 160 + 45 * np.sin(2 * np.pi * 0.5 * t)
    flat = lambda t: np.full_like(t, 140.0)
    parts = [silence(2, rng), voiced(10, vary, -20), silence(3.5, rng), voiced(9.5, flat, -20),
             voiced(10, vary, -32), silence(1, rng)]
    return np.concatenate(parts)           # speech 2-12, pause 12-15.5, flat 15.5-25, quiet 25-35


def write_wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def inside(spans, a, b, slack=1.5):
    return any(s >= a - slack and e <= b + slack for s, e in spans)


def test_voice_signals_land_where_they_should():
    r = A.analyze_samples(sample())
    s = r["signals"]
    assert r["overall"]["level_note"] == "ok"
    assert s["long_pause"]["episodes"] == 1 and inside(s["long_pause"]["spans"], 12, 15.5)
    assert s["monotone"]["spans"] and inside(s["monotone"]["spans"], 15.5, 25)
    assert not any(a < 11 for a, _ in s["monotone"]["spans"])
    assert s["quiet_voice"]["spans"] and inside(s["quiet_voice"]["spans"], 25, 36)
    assert s["quiet_voice"]["percent"] < 45
    assert r["overall"]["wpm"] is None and s["fast_speech"]["episodes"] == 0
    assert 0.6 < r["overall"]["speech_ratio"] < 0.95
    assert len(r["timeline"]["level_db"]) == 36


def test_pace_from_words():
    words = [{"word": "w", "start": 2 + i / 6.0, "end": 2.1 + i / 6.0} for i in range(60)]        # 360 wpm, 2-12
    words += [{"word": "w", "start": 25 + i * 1.5, "end": 25.2 + i * 1.5} for i in range(6)]      # 40 wpm, 25-34
    words += [{"word": "w", "start": 15.5 + i / 2.5, "end": 15.7 + i / 2.5} for i in range(23)]   # 150 wpm, 15.5-25
    words.sort(key=lambda w: w["start"])
    r = A.analyze_samples(sample(), words)
    s = r["signals"]
    assert s["fast_speech"]["spans"] and inside(s["fast_speech"]["spans"], 2, 12, slack=5)
    assert s["slow_speech"]["spans"] and inside(s["slow_speech"]["spans"], 25, 35, slack=3)


def test_silence_and_short_audio():
    rng = np.random.default_rng(2)
    r = A.analyze_samples(silence(5, rng))
    assert r["overall"]["level_note"] == "no_speech" and r["signals"]["long_pause"]["episodes"] == 0
    with pytest.raises(A.AudioError) as e:
        A.analyze_samples(np.zeros(100, np.float32))
    assert e.value.code == "bad_audio"


def make_video(path, with_audio, wav=None):
    cmd = [A._ffmpeg_exe(), "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=12:r=10"]
    if with_audio:
        cmd += ["-i", str(wav), "-shortest"]
    cmd += ["-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


def test_extract_from_video_and_pipeline(tmp_path):
    wav = tmp_path / "s.wav"
    write_wav(wav, sample()[: 12 * SR])
    vid = tmp_path / "v.mp4"
    make_video(vid, True, wav)
    fake_stt = lambda p, pr=None: {"language": "ar", "text": "ازيك", "segments": [], "words": [{"word": "ازيك", "start": 3.0, "end": 3.4}]}
    r = A.analyze_video_audio(vid, tmp_path / "w", stt=fake_stt)
    assert r["transcript"]["language"] == "ar" and r["overall"]["speech_seconds"] > 3

    def missing(p, pr=None):
        raise A.AudioError("no_stt")
    r2 = A.analyze_video_audio(vid, tmp_path / "w2", stt=missing)
    assert r2["transcript"] is None and r2["stt_note"] == "no_stt"
    assert r2["overall"]["wpm"] is None


def test_video_without_audio(tmp_path):
    vid = tmp_path / "mute.mp4"
    make_video(vid, False)
    with pytest.raises(A.AudioError) as e:
        A.analyze_video_audio(vid, tmp_path / "w", stt=lambda p, pr=None: None)
    assert e.value.code == "no_audio"
