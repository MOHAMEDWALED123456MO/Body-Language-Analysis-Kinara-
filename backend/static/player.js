(() => {
  const vid = document.getElementById("vid"), pl = document.getElementById("pl");
  if (!vid || !pl) return;
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const mmss = (s) => { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const big = el("button", "bigplay"); big.type = "button"; big.setAttribute("aria-label", "play"); big.innerHTML = "<i></i>";
  const bar = el("div", "ctrl");
  const play = el("button", "play"); play.type = "button"; play.setAttribute("aria-label", "play/pause"); play.innerHTML = "<i></i>";
  const time = el("span", "time", "0:00 / 0:00"); time.dir = "ltr";
  const seek = el("div", "seek"); seek.setAttribute("role", "slider"); seek.tabIndex = 0; seek.dir = "ltr";
  const fill = el("i", "fill"), knob = el("b", "knob"), marks = el("div", "marks");
  seek.append(marks, fill, knob);
  const speed = el("button", "cbtn", "1×"); speed.type = "button"; speed.setAttribute("aria-label", "speed");
  const mute = el("button", "cbtn", "🔊"); mute.type = "button"; mute.setAttribute("aria-label", "mute");
  const full = el("button", "cbtn", "⛶"); full.type = "button"; full.setAttribute("aria-label", "fullscreen");
  bar.append(play, seek, time, speed, mute, full);
  pl.append(big, bar);

  const dur = () => (isFinite(vid.duration) && vid.duration > 0 ? vid.duration : (window.__total || 0));
  const toggle = () => (vid.paused ? vid.play() : vid.pause());
  function paint() {
    const d = dur(), f = d ? Math.min(100, (vid.currentTime / d) * 100) : 0;
    fill.style.width = f + "%"; knob.style.left = f + "%";
    time.textContent = mmss(vid.currentTime) + " / " + mmss(d);
    seek.setAttribute("aria-valuenow", Math.round(f));
    pl.classList.toggle("playing", !vid.paused);
  }
  ["timeupdate", "play", "pause", "loadedmetadata", "durationchange", "ended"].forEach((e) => vid.addEventListener(e, paint));
  [big, play].forEach((b) => b.addEventListener("click", toggle));
  vid.addEventListener("click", toggle);
  const at = (ev) => { const r = seek.getBoundingClientRect(); return Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)) * dur(); };
  let drag = false;
  seek.addEventListener("pointerdown", (e) => { drag = true; seek.setPointerCapture(e.pointerId); vid.currentTime = at(e); paint(); });
  seek.addEventListener("pointermove", (e) => { if (drag) { vid.currentTime = at(e); paint(); } });
  seek.addEventListener("pointerup", () => { drag = false; });
  seek.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") vid.currentTime += 5; else if (e.key === "ArrowLeft") vid.currentTime -= 5; else if (e.key === " ") { e.preventDefault(); toggle(); } else return;
    paint();
  });
  const rates = [1, 1.25, 1.5, 2, 0.75];
  speed.addEventListener("click", () => { const i = (rates.indexOf(vid.playbackRate) + 1) % rates.length; vid.playbackRate = rates[i]; speed.textContent = rates[i] + "×"; });
  mute.addEventListener("click", () => { vid.muted = !vid.muted; mute.textContent = vid.muted ? "🔇" : "🔊"; });
  full.addEventListener("click", () => { document.fullscreenElement ? document.exitFullscreen() : pl.requestFullscreen && pl.requestFullscreen(); });
  document.addEventListener("kinara:job", (e) => {
    const j = e.detail, r = j.result || {}; window.__total = r.total_seconds || 0;
    marks.replaceChildren();
    const items = (r.coach && r.coach.items) || [];
    items.forEach((x) => { const m = el("u", x.kind || ""); m.style.left = (window.__total ? (x.start / window.__total) * 100 : 0) + "%"; marks.append(m); });
    paint();
  });
  paint();
})();
