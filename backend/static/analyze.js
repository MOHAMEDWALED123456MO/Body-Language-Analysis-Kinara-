(() => {
  const $ = (id) => document.getElementById(id);
  const T = (k, v) => { let s = KT.t(k); for (const a in (v || {})) s = s.replace("{" + a + "}", v[a]); return s; };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const MAX = 1024 * 1024 * 1024, EXT = [".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"];
  const ERR = { bad_type: "err_bad_type", too_big: "err_too_big", bad_video: "err_bad_video", empty: "err_empty",
                no_calibration: "err_no_calibration", no_model: "err_no_model" };
  const drop = $("drop"), file = $("file"), box = $("alert"), up = $("up");
  let ready = true, alertKey = null, pct = null, recent = [];
  const SC = window.SCENARIOS || {};
  let scenario = "general";
  try { const v = localStorage.getItem("scenario"); if (v && SC[v]) scenario = v; } catch (e) {}
  const lang = () => (KT.lang() === "ar" ? "ar" : "en");

  function renderScenarios() {
    const box = $("scn"); box.replaceChildren();
    Object.keys(SC).forEach((id) => {
      const b = el("button", "scard" + (id === scenario ? " on" : ""));
      b.type = "button"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", id === scenario ? "true" : "false");
      b.append(el("strong", null, SC[id][lang()]), el("span", null, SC[id]["desc_" + lang()]));
      b.addEventListener("click", () => { scenario = id; try { localStorage.setItem("scenario", id); } catch (e) {} renderScenarios(); });
      box.append(b);
    });
    $("goal").placeholder = T("goal_ph");
  }

  function showAlert(key, err) { alertKey = key; box.hidden = false; box.className = "alert" + (err ? " err" : ""); box.textContent = T(key); box.scrollIntoView({ block: "center", behavior: "smooth" }); }
  function clearAlert() { alertKey = null; box.hidden = true; }
  function setProgress(p) { pct = Math.round(p * 100); $("upbar").style.width = pct + "%"; $("uptext").textContent = T("uploading", { p: pct }); }

  function fail(key) { up.hidden = true; pct = null; drop.disabled = !ready; showAlert(key, true); }

  function send(f) {
    clearAlert(); up.hidden = false; drop.disabled = true; setProgress(0); up.scrollIntoView({ block: "center", behavior: "smooth" });
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/analyze?filename=" + encodeURIComponent(f.name) + "&scenario=" + encodeURIComponent(scenario) +
             "&goal=" + encodeURIComponent($("goal").value.trim().slice(0, 300)));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) setProgress(e.loaded / e.total); };
    xhr.onerror = () => fail("err_network");
    xhr.onload = () => {
      if (xhr.status === 200) { location.href = "/results/" + JSON.parse(xhr.responseText).id; return; }
      let code = null;
      try { code = JSON.parse(xhr.responseText).detail.code; } catch (e) {}
      fail(ERR[code] || "err_internal");
    };
    xhr.send(f);
  }

  window.KinaraSend = (f) => { if (!ready) { if (alertKey) box.scrollIntoView({ block: "center", behavior: "smooth" }); else showAlert("err_internal", true); return false; } if (!f.size) { showAlert("err_empty", true); return false; } send(f); return true; };

  function pick(f) {
    if (!f || !ready) return;
    const name = f.name.toLowerCase();
    if (!EXT.some((x) => name.endsWith(x))) return showAlert("err_bad_type", true);
    if (f.size > MAX) return showAlert("err_too_big", true);
    if (f.size === 0) return showAlert("err_empty", true);
    send(f);
  }

  drop.addEventListener("click", () => file.click());
  file.addEventListener("change", () => { pick(file.files[0]); file.value = ""; });
  ["dragenter", "dragover"].forEach((n) => drop.addEventListener(n, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((n) => drop.addEventListener(n, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => pick(e.dataTransfer.files[0]));
  ["dragover", "drop"].forEach((n) => window.addEventListener(n, (e) => e.preventDefault()));

  function renderRecent() {
    const ul = $("recent"); ul.replaceChildren();
    if (!recent.length) { const li = el("li", "empty", T("recent_none")); ul.append(li); return; }
    for (const j of recent) {
      const li = el("li"), a = el("a"); a.href = "/results/" + j.id;
      const left = el("span", null, j.name);
      const right = el("span", "when", new Date(j.created).toLocaleString(KT.lang() === "ar" ? "ar-EG" : "en-GB"));
      const badge = el("span", "badge " + j.status, T("badge_" + j.status));
      const side = el("span"); side.style.display = "flex"; side.style.gap = "12px"; side.style.alignItems = "center";
      side.append(right, badge); a.append(left, side); li.append(a); ul.append(li);
    }
  }

  async function load() {
    try {
      const s = await (await fetch("/api/status")).json();
      if (!s.calibrated) { ready = false; showAlert("err_no_calibration"); }
      else if (!s.model_ok) { ready = false; showAlert("err_no_model"); }
      drop.disabled = !ready;
    } catch (e) {}
    try { recent = await (await fetch("/api/jobs")).json(); } catch (e) { recent = []; }
    renderRecent();
  }

  document.addEventListener("langchange", () => {
    if (alertKey) box.textContent = T(alertKey);
    if (pct !== null) $("uptext").textContent = T("uploading", { p: pct });
    renderRecent(); renderScenarios();
  });
  renderScenarios();
  load();
})();
