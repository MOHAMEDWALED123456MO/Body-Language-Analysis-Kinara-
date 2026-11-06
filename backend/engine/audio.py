"""Voice analysis: loudness, pauses, pitch variation and (optionally) speaking pace from the transcript.

Everything here is computed from the audio track itself, so it needs no calibration.
Results use the same shape as the body signals ({percent, episodes, longest, spans}) so the
timeline and the report can treat voice and body together.
"""
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000
FRAME = 480            # 30 ms
HOP = 320              # 20 ms
HOP_SEC = HOP / SR

NOISE_MARGIN_DB = 10.0     # speech = this much above the noise floor
SPEECH_FLOOR_DB = -60.0    # never treat anything quieter than this as speech
MERGE_GAP_SEC = 0.25       # gaps shorter than this inside speech are just between-word pauses
MIN_SPEECH_SEC = 0.15      # shorter blips are noise

LONG_PAUSE_SEC = 2.0
QUIET_DROP_DB = 6.0        # "voice dropped" = this far below your own usual level
QUIET_MIN_SEC = 2.0
MONOTONE_RANGE_ST = 2.5    # p90 - p10 pitch range (semitones) below this = flat delivery
MONOTONE_WIN_SEC = 4.0
MONOTONE_MIN_SEC = 4.0
FAST_WPM, SLOW_WPM = 250.0, 110.0   # words per minute of actual speaking time (pauses excluded)
PACE_WIN_SEC = 10.0
PACE_MIN_SEC = 6.0
WEAK_MIC_DB, LOUD_MIC_DB = -40.0, -10.0

VOICE_SIGNALS = [
    {"id": "quiet_voice", "kind": "attention", "en": "Voice dropped", "ar": "الصوت وطّى"},
    {"id": "monotone", "kind": "attention", "en": "Flat voice", "ar": "صوت رتيب"},
    {"id": "long_pause", "kind": "attention", "en": "Long pause", "ar": "وقفة طويلة"},
    {"id": "fast_speech", "kind": "attention", "en": "Speaking too fast", "ar": "كلام سريع"},
    {"id": "slow_speech", "kind": "attention", "en": "Speaking too slowly", "ar": "كلام بطيء"},
]


class AudioError(Exception):
    """code: no_audio | no_ffmpeg | bad_audio | no_stt"""

    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.code = code


# ---------------------------------------------------------------- extraction

def _ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def extract_audio(video_path, wav_path):
    """Writes 16 kHz mono PCM wav. Raises AudioError('no_audio') if the video has no sound."""
    cmd = [_ffmpeg_exe(), "-y", "-v", "error", "-i", str(video_path), "-vn", "-ac", "1",
           "-ar", str(SR), "-c:a", "pcm_s16le", str(wav_path)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except FileNotFoundError:
        raise AudioError("no_ffmpeg", "ffmpeg not found")
    except subprocess.TimeoutExpired:
        raise AudioError("bad_audio", "audio extraction timed out")
    wp = Path(wav_path)
    if p.returncode != 0 or not wp.exists() or wp.stat().st_size < 1000:
        err = (p.stderr or "").lower()
        if "does not contain any stream" in err or "output file #0 does not contain" in err or \
                (p.returncode == 0 and (not wp.exists() or wp.stat().st_size < 1000)):
            raise AudioError("no_audio", "this video has no audio track")
        raise AudioError("bad_audio", (p.stderr or "")[-300:])


def load_wav(path):
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise AudioError("bad_audio", "expected 16 kHz mono 16-bit wav")
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


# ---------------------------------------------------------------- frame features

def _frames(x):
    n = 1 + max(0, (len(x) - FRAME) // HOP)
    if len(x) < FRAME:
        x = np.pad(x, (0, FRAME - len(x)))
        n = 1
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    return x[idx]


def frame_db(fr):
    rms = np.sqrt(np.mean(fr ** 2, axis=1))
    return np.maximum(20 * np.log10(rms + 1e-9), -90.0)


def pitch_track(fr, speech):
    """Autocorrelation pitch for speech frames. Returns Hz per frame, NaN where unvoiced."""
    f0 = np.full(len(fr), np.nan)
    ids = np.where(speech)[0]
    lo, hi = int(SR / 400), int(SR / 70)
    win = np.hanning(FRAME).astype(np.float32)
    for s in range(0, len(ids), 2000):
        b = ids[s:s + 2000]
        seg = (fr[b] - fr[b].mean(axis=1, keepdims=True)) * win
        spec = np.fft.rfft(seg, n=1024, axis=1)
        acf = np.fft.irfft(np.abs(spec) ** 2, axis=1)
        acf = acf / (acf[:, :1] + 1e-9)
        band = acf[:, lo:hi]
        lag = band.argmax(axis=1) + lo
        peak = band.max(axis=1)
        ok = peak > 0.4
        f0[b[ok]] = SR / lag[ok]
    return f0


# ---------------------------------------------------------------- helpers on boolean tracks

def _runs(mask):
    """[(start_idx, end_idx_exclusive)] of True runs."""
    m = np.concatenate(([False], np.asarray(mask, bool), [False])).astype(np.int8)
    d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _clean_speech(mask):
    gap = int(MERGE_GAP_SEC / HOP_SEC)
    out = np.asarray(mask, bool).copy()
    for a, b in _runs(~out):                      # fill short gaps between speech
        if a > 0 and b < len(out) and (b - a) <= gap:
            out[a:b] = True
    blip = int(MIN_SPEECH_SEC / HOP_SEC)
    for a, b in _runs(out):                       # drop tiny blips
        if (b - a) < blip:
            out[a:b] = False
    return out


def _stat(spans, total):
    spans = [(round(float(a), 2), round(float(b), 2)) for a, b in spans]
    secs = sum(b - a for a, b in spans)
    return {"percent": round(100 * secs / total, 1) if total else 0.0, "seconds": round(secs, 2),
            "episodes": len(spans), "longest": round(max([b - a for a, b in spans], default=0.0), 2),
            "spans": spans[:300]}


def _per_second_spans(flags, min_len, total):
    sp = [(a, min(b, total)) for a, b in _runs(flags) if (b - a) >= min_len]
    return sp


# ---------------------------------------------------------------- main analysis

def analyze_samples(x, words=None):
    """x: float32 mono 16 kHz. words: optional [{'word','start','end'}] from the transcript."""
    total = len(x) / SR
    if total < 1.0:
        raise AudioError("bad_audio", "audio too short")
    fr = _frames(x)
    db = frame_db(fr)
    floor = float(np.percentile(db, 10))
    thr = max(floor + NOISE_MARGIN_DB, SPEECH_FLOOR_DB)
    speech = _clean_speech(db > thr)
    n = len(db)
    speech_sec = float(speech.sum() * HOP_SEC)
    sec_n = int(np.ceil(total))
    t_frame = np.arange(n) * HOP_SEC

    overall = {"duration": round(total, 2), "speech_seconds": round(speech_sec, 1),
               "speech_ratio": round(speech_sec / total, 3), "noise_floor_db": round(floor, 1)}
    signals = {s["id"]: _stat([], total) for s in VOICE_SIGNALS}
    if speech_sec < 2.0:
        overall.update(level_db=None, level_note="no_speech", pitch_range_st=None, wpm=None)
        return {"overall": overall, "signals": signals, "timeline": {"level_db": [], "pitch_hz": []}}

    level = float(np.median(db[speech]))
    overall["level_db"] = round(level, 1)
    overall["level_note"] = "low" if level < WEAK_MIC_DB else "loud" if level > LOUD_MIC_DB else "ok"

    # per-second loudness while speaking (centered 3 s window), and pitch
    f0 = pitch_track(fr, speech)
    lvl_sec = np.full(sec_n, np.nan)
    pitch_sec = np.full(sec_n, np.nan)
    for s in range(sec_n):
        m = speech & (t_frame >= s - 1.0) & (t_frame < s + 2.0)
        if m.sum() >= 10:
            lvl_sec[s] = np.median(db[m])
        v = f0[(t_frame >= s) & (t_frame < s + 1)]
        v = v[~np.isnan(v)]
        if len(v) >= 5:
            pitch_sec[s] = np.median(v)

    # quiet voice: below your own usual level
    ref = float(np.nanmedian(lvl_sec))
    quiet = np.nan_to_num(lvl_sec, nan=ref) < ref - QUIET_DROP_DB
    signals["quiet_voice"] = _stat(_per_second_spans(quiet, QUIET_MIN_SEC, total), total)

    # long pauses: silence between speech, not the lead-in or the tail
    idx = np.where(speech)[0]
    first, last = idx[0], idx[-1]
    pauses = [(a * HOP_SEC, b * HOP_SEC) for a, b in _runs(~speech)
              if a > first and b <= last and (b - a) * HOP_SEC >= LONG_PAUSE_SEC]
    signals["long_pause"] = _stat(pauses, total)

    # monotone: narrow pitch range over a sliding window
    voiced = ~np.isnan(f0)
    st = np.full(n, np.nan)
    st[voiced] = 12 * np.log2(f0[voiced] / 100.0)
    flat = np.zeros(sec_n, bool)
    half = MONOTONE_WIN_SEC / 2
    ranges = []
    for s in range(sec_n):
        w = st[(t_frame >= s + 0.5 - half) & (t_frame < s + 0.5 + half)]
        w = w[~np.isnan(w)]
        if len(w) >= 40:
            r = float(np.percentile(w, 90) - np.percentile(w, 10))
            ranges.append(r)
            flat[s] = r < MONOTONE_RANGE_ST
    signals["monotone"] = _stat(_per_second_spans(flat, MONOTONE_MIN_SEC, total), total)
    overall["pitch_range_st"] = round(float(np.median(ranges)), 1) if ranges else None

    # pace (needs a transcript)
    overall["wpm"] = None
    if words:
        starts = np.array([w["start"] for w in words])
        overall["wpm"] = round(60.0 * len(words) / max(speech_sec, 1.0), 0)
        fast = np.zeros(sec_n, bool)
        slow = np.zeros(sec_n, bool)
        hw = PACE_WIN_SEC / 2
        for s in range(sec_n):
            a, b = s + 0.5 - hw, s + 0.5 + hw
            sp_in = float(speech[(t_frame >= a) & (t_frame < b)].sum() * HOP_SEC)
            if sp_in < 4.0:
                continue
            wpm = 60.0 * int(((starts >= a) & (starts < b)).sum()) / sp_in
            fast[s] = wpm > FAST_WPM
            slow[s] = wpm < SLOW_WPM
        signals["fast_speech"] = _stat(_per_second_spans(fast, PACE_MIN_SEC, total), total)
        signals["slow_speech"] = _stat(_per_second_spans(slow, PACE_MIN_SEC, total), total)

    tl = {"level_db": [None if np.isnan(v) else round(float(v), 1) for v in lvl_sec],
          "pitch_hz": [None if np.isnan(v) else round(float(v), 0) for v in pitch_sec]}
    return {"overall": overall, "signals": signals, "timeline": tl}


# ---------------------------------------------------------------- transcription

_models = {}


def _stt_model(size):
    from faster_whisper import WhisperModel
    if size not in _models:
        _models[size] = WhisperModel(size, device="cpu", compute_type="int8")
    return _models[size]


def transcribe(wav_path, progress=None, model_size=None, language=None):
    """Speech-to-text with faster-whisper (free, runs on this computer, Arabic and English).
    Returns {'language', 'text', 'words': [{'word','start','end'}], 'segments': [{'start','end','text'}]}."""
    # KINARA_STT_MODEL = small (default, fast) | medium (better Arabic) | large-v3 (best, slow)
    # KINARA_STT_LANG  = ar | en | ... (optional: skip auto-detection)
    model_size = model_size or os.environ.get("KINARA_STT_MODEL", "small")
    language = language or os.environ.get("KINARA_STT_LANG") or None
    try:
        model = _stt_model(model_size)
    except ImportError:
        raise AudioError("no_stt", "faster-whisper is not installed")
    segs, info = model.transcribe(str(wav_path), language=language, word_timestamps=True,
                                  vad_filter=True, beam_size=1)
    words, out = [], []
    dur = float(getattr(info, "duration", 0) or 0)
    for s in segs:
        if progress and dur > 0:
            progress(min(float(s.end) / dur, 1.0))
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        for w in (s.words or []):
            words.append({"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)})
    return {"language": info.language, "text": " ".join(s["text"] for s in out), "words": words, "segments": out}


def analyze_video_audio(video_path, work_dir, stt=transcribe, with_text=True, progress=None):
    """Full voice pipeline for one video. stt is injectable for tests."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    wav = work_dir / "audio.wav"
    extract_audio(video_path, wav)
    x = load_wav(wav)
    text, note = None, None
    if with_text:
        try:
            text = stt(wav, progress)
        except AudioError as e:
            if e.code != "no_stt":
                raise
            note = "no_stt"
    res = analyze_samples(x, text["words"] if text else None)
    res["transcript"] = text
    res["stt_note"] = note
    return res
