(() => {
  const $ = (id) => document.getElementById(id);
  const open = $("rec-open"); if (!open) return;
  const T = (k) => KT.t(k);
  const MAX_S = 600;
  const vid = $("rec-vid"), box = $("rec"), note = $("rec-note"), timeEl = $("rec-time");
  const show = (id, on) => { $(id).hidden = !on; };
  let stream = null, rec = null, chunks = [], t0 = 0, tick = null, blob = null, noteKey = null, noteErr = false;
  const mmss = (s) => Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  const setNote = (k, err) => { noteKey = k; noteErr = !!err; note.textContent = k ? T(k) : ""; note.className = err ? "alert err" : "fine"; };

  function mime() {
    if (!window.MediaRecorder) return null;
    return ["video/mp4;codecs=avc1", "video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"].find((m) => MediaRecorder.isTypeSupported(m)) || "";
  }
  function stopStream() { if (stream) stream.getTracks().forEach((t) => t.stop()); stream = null; vid.srcObject = null; }
  function ui(state) {
    show("rec-start", state === "ready"); show("rec-stop", state === "recording");
    show("rec-use", state === "done"); show("rec-retake", state === "done");
  }

  async function camera() {
    if (!navigator.mediaDevices || mime() === null) return setNote("rec_err_unsupported", true), ui("none");
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
                                                           audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      setNote(e && (e.name === "NotFoundError" || e.name === "OverconstrainedError") ? "rec_err_none" : "rec_err_denied", true); ui("none"); return;
    }
    vid.controls = false; vid.muted = true; vid.removeAttribute("src"); vid.srcObject = stream; vid.play().catch(() => {});
    setNote("rec_ready"); ui("ready"); timeEl.textContent = "0:00";
  }

  // ---- live hints (optional; recording never depends on them)
  const hintEl = $("live-hint"), liveBox = $("live-on");
  let gotReady = false, ws = null, liveTimer = null, waiting = false, liveOn = false, canvas = null, t0live = 0;
  const showHint = (txt, good) => { hintEl.textContent = txt || ""; hintEl.hidden = !txt; hintEl.classList.toggle("good", !!good); };
  function liveStop() { liveOn = false; gotReady = true; clearTimeout(liveTimer); if (ws) { try { ws.close(); } catch (e) {} } ws = null; showHint(""); }
  function liveStart() {
    if (!liveBox || !liveBox.checked || !window.WebSocket) return;
    try { ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/live"); } catch (e) { return; }
    ws.binaryType = "arraybuffer"; waiting = false; gotReady = false; t0live = performance.now();
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.error) { setNote("live_err_" + m.error, true); liveStop(); return; }
      if (m.ready) { gotReady = true; liveOn = true; setNote("live_ready"); loop(); return; }
      waiting = false;
      if (!m.visible) showHint(T("live_novis"));
      else if (m.hints && m.hints.length) showHint(m.hints.map((h) => T("h_" + h)).join("  ·  "));
      else showHint(m.good ? T("live_good") : "", true);
    };
    ws.onclose = () => { if (!gotReady || liveOn) setNote("live_err_net", true); liveOn = false; showHint(""); };
    ws.onerror = () => { if (!gotReady) setNote("live_err_net", true); };
  }
  function loop() {
    if (!liveOn || !ws || ws.readyState !== 1) return;
    const began = performance.now();
    if (!waiting && vid.videoWidth) {
      const k = Math.min(1, 640 / Math.max(vid.videoWidth, vid.videoHeight));
      canvas = canvas || document.createElement("canvas");
      canvas.width = Math.round(vid.videoWidth * k); canvas.height = Math.round(vid.videoHeight * k);
      canvas.getContext("2d").drawImage(vid, 0, 0, canvas.width, canvas.height);
      waiting = true;
      canvas.toBlob(async (blob) => {
        if (!blob || !liveOn || !ws || ws.readyState !== 1) { waiting = false; return; }
        const head = new ArrayBuffer(8); new DataView(head).setFloat64(0, performance.now() - t0live, false);
        ws.send(new Blob([head, blob]));
      }, "image/jpeg", 0.6);
    }
    liveTimer = setTimeout(loop, Math.max(60, 250 - (performance.now() - began)));
  }

  function start() {
    if (!stream) return;
    blob = null; chunks = [];
    try { rec = new MediaRecorder(stream, mime() ? { mimeType: mime() } : undefined); } catch (e) { return setNote("rec_err_failed", true); }
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onerror = () => { setNote("rec_err_failed", true); clearInterval(tick); ui("ready"); };
    rec.onstop = finish;
    rec.start(1000); t0 = Date.now(); ui("recording"); setNote("rec_going"); liveStart();
    tick = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000); timeEl.textContent = mmss(s);
      if (s >= MAX_S) { stop(); setNote("rec_max"); }
    }, 250);
  }
  function stop() { liveStop(); clearInterval(tick); if (rec && rec.state !== "inactive") rec.stop(); }

  function finish() {
    const type = (rec && rec.mimeType) || "video/webm";
    blob = new Blob(chunks, { type }); stopStream();
    if (!blob.size) { setNote("rec_err_failed", true); ui("none"); return; }
    vid.srcObject = null; vid.src = URL.createObjectURL(blob); vid.muted = false; vid.controls = true;
    ui("done"); if (noteKey !== "rec_max") setNote("rec_done");
  }

  function use() {
    if (!blob) return;
    const ext = /mp4/.test(blob.type) ? ".mp4" : ".webm";
    const name = "recording-" + new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-") + ext;
    const f = new File([blob], name, { type: blob.type });
    if (!window.KinaraSend) return setNote("rec_err_failed", true);
    if (window.KinaraSend(f)) close(true);
  }
  function close(keepVideo) {
    liveStop(); clearInterval(tick); if (rec && rec.state !== "inactive") { rec.onstop = null; rec.stop(); }
    stopStream(); if (!keepVideo) { vid.removeAttribute("src"); blob = null; }
    box.hidden = true; open.hidden = false;
  }

  open.addEventListener("click", () => { open.hidden = true; box.hidden = false; camera(); });
  $("rec-start").addEventListener("click", start);
  $("rec-stop").addEventListener("click", stop);
  $("rec-use").addEventListener("click", use);
  $("rec-retake").addEventListener("click", () => { if (vid.src) URL.revokeObjectURL(vid.src); vid.removeAttribute("src"); camera(); });
  $("rec-close").addEventListener("click", () => close(false));
  document.addEventListener("langchange", () => { if (noteKey) setNote(noteKey, noteErr); });
  window.addEventListener("beforeunload", stopStream);
})();
