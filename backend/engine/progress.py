"""Progress history: one compact row per finished analysis, oldest first, for the /progress page."""
from . import jobs
from .audio import VOICE_SIGNALS
from .coach import enrich
from .registry import SIGNALS

LIMIT = 60


def history(limit=LIMIT, only_ids=None):
    files = sorted(jobs._dir("jobs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for f in files:
        if len(rows) >= limit:
            break
        if only_ids is not None and f.stem not in only_ids:
            continue
        job = jobs.get(f.stem)
        if not job or job.get("status") != "done" or not job.get("result"):
            continue
        job = enrich(job)
        res, sc = job["result"], job["result"].get("score")
        if not sc:
            continue
        sigs = dict(res.get("signals") or {})
        v = res.get("voice")
        if v and not v.get("error"):
            sigs.update(v.get("signals") or {})
        rows.append({"id": job["id"], "name": job["name"], "created": job["created"],
                     "scenario": job["context"]["scenario"], "seconds": res.get("total_seconds"),
                     "overall": sc["overall"], "body": sc.get("body"), "voice": sc.get("voice"),
                     "label": sc["label"],
                     "signals": {k: round(d["percent"], 1) for k, d in sigs.items() if d}})
    rows.sort(key=lambda r: r["created"])
    return rows
