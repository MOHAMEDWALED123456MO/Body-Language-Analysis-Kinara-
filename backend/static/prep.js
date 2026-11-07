(() => {
  const $ = (id) => document.getElementById(id);
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const log = $("pp-log"), input = $("pp-input"), err = $("pp-err");
  let hist = [], busy = false;
  const scenario = () => { try { return localStorage.getItem("scenario") || "general"; } catch (e) { return "general"; } };
  const lang = () => (KT.lang() === "ar" ? "ar" : "en");
  function draw() {
    log.replaceChildren();
    hist.forEach((m) => log.append(el("div", "msg " + m.role, m.text)));
    if (busy) log.append(el("div", "msg coach thinking", KT.t("ch_thinking")));
    log.scrollTop = log.scrollHeight;
    input.placeholder = KT.t("pp_ph");
    const chips = $("pp-chips"); chips.replaceChildren();
    if (!hist.length) ["pp_c1", "pp_c2", "pp_c3"].forEach((k) => {
      const b = el("button", "chip", KT.t(k)); b.type = "button"; b.addEventListener("click", () => send(KT.t(k))); chips.append(b);
    });
  }
  async function send(text) {
    text = (text || "").trim(); if (!text || busy) return;
    err.hidden = true; input.value = ""; busy = true;
    const past = hist.slice(); hist.push({ role: "user", text }); draw();
    try {
      const r = await fetch("/api/prep/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenario(), goal: ($("goal").value || "").trim(), message: text, history: past, lang: lang() }) });
      if (!r.ok) throw new Error("bad");
      hist.push({ role: "coach", text: (await r.json()).reply });
    } catch (e) { hist.pop(); err.hidden = false; err.textContent = KT.t("pp_err"); input.value = text; }
    busy = false; draw();
  }
  $("pp-form").addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  window.KinaraPrepSave = (id) => hist.length
    ? fetch("/api/jobs/" + id + "/prep", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: hist }) }).catch(() => {})
    : Promise.resolve();
  document.addEventListener("langchange", draw);
  draw();
})();
