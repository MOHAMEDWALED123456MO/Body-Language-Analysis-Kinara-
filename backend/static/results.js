(() => {
  const $ = (id) => document.getElementById(id);
  const JOB = window.JOB_ID, SIG = window.SIGNALS, VSIG = window.VOICE_SIGNALS || [];
  const T = (k, v) => { let s = KT.t(k); for (const a in (v || {})) s = s.replace("{" + a + "}", v[a]); return s; };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const mmss = (s) => { s = Math.max(0, Math.round(s)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const lab = (s) => (KT.lang() === "ar" ? s.ar : s.en);
  const vid = $("vid");
  const voice = () => { const v = job && job.result && job.result.voice; return v && !v.error ? v : null; };
  const sdata = (s) => job.result.signals[s.id] || (voice() && voice().signals[s.id]) || null;
  let job = null, total = 1, playheads = [], playerReady = false, timer = null;

  function errText(j) {
    const k = "err_" + (j.error_code || "internal"), s = KT.t(k);
    return s === k ? (j.error || "") : s;
  }
  function newLink() { const a = el("a", "btn ghost", T("res_new")); a.href = "/new"; return a; }

  function renderState() {
    const box = $("state"); box.replaceChildren(); $("view").hidden = true;
    if (job.status === "error") {
      box.append(el("div", "alert err", errText(job)), newLink());
      return;
    }
    const p = Math.round((job.progress || 0) * 100);
    const wrap = el("div", "prog"), track = el("div", "track"), bar = el("i");
    bar.style.width = p + "%"; track.append(bar);
    wrap.append(track, el("p", null, job.status === "queued" ? T("st_queued") : T(job.stage === "voice" ? "st_voice" : "st_processing", { p })), el("p", "fine", T("st_hint")));
    box.append(wrap);
  }

  function seek(t) {
    if (vid.hidden) return;
    vid.currentTime = Math.max(0, t);
    vid.scrollIntoView({ block: "nearest" });
  }

  function updatePlayheads() {
    const f = Math.min((vid.currentTime || 0) / total, 1) * 100;
    playheads.forEach((p) => { p.style.left = f + "%"; p.style.visibility = f > 0 ? "visible" : "hidden"; });
  }

  function renderMeta() {
    const r = job.result, m = $("meta"); m.replaceChildren();
    $("title").textContent = job.name;
    const vis = r.total_seconds ? Math.round(100 * r.visible_seconds / r.total_seconds) : 0;
    const dur = el("span", null, T("meta_dur") + ": "); const d = el("bdi", null, mmss(r.total_seconds)); dur.append(d);
    const vs = el("span", null, T("meta_vis") + ": "); vs.append(el("bdi", null, vis + "%"));
    m.append(dur, vs, el("span", null, T("meta_fps", { n: r.analyzed_fps })));
  }

  function renderMoments() {
    const box = $("moments"); box.replaceChildren();
    const items = [];
    for (const s of SIG.concat(voice() ? VSIG : [])) {
      if (s.kind !== "attention" || s.id === "distance" || s.id === "off_center") continue;
      const d = sdata(s); if (!d) continue;
      d.spans.map(([a, b]) => ({ s, a, len: b - a })).filter((x) => x.len >= 1)
        .sort((x, y) => y.len - x.len).slice(0, 2).forEach((x) => items.push(x));
    }
    items.sort((x, y) => y.len - x.len);
    const top = items.slice(0, 8);
    if (!top.length) { box.append(el("li", "empty", T("res_none_moments"))); return; }
    for (const x of top) {
      const li = el("li"), b = el("button"); b.type = "button";
      b.append(el("time", null, mmss(x.a)), el("span", null, lab(x.s)), el("span", "dur", x.len.toFixed(1) + T("unit_s")));
      b.addEventListener("click", () => seek(x.a));
      li.append(b); box.append(li);
    }
  }

  function renderTimeline() {
    const box = $("timeline"); box.replaceChildren(); playheads = [];
    total = Math.max(job.result.total_seconds, 1);
    const axis = el("div", "tl-axis");
    [0, 0.25, 0.5, 0.75, 1].forEach((f) => axis.append(el("span", null, mmss(total * f))));
    const ax = el("div", "tl-row"); ax.append(el("span"), axis); box.append(ax);
    const rows = SIG.map((s) => [s, "body"]).concat(voice() ? VSIG.map((s) => [s, "voice"]) : []);
    let group = null;
    for (const [s, g] of rows) {
      const d = sdata(s); if (!d) continue;
      if (voice() && g !== group) { group = g; const h = el("div", "tl-row tl-group"); h.append(el("span", "tl-gname", T("tl_" + g))); box.append(h); }
      const row = el("div", "tl-row"), track = el("div", "tl-track");
      row.append(el("span", "tl-label", lab(s)));
      for (const [a, b] of d.spans) {
        const seg = el("i", "tl-seg" + (s.kind === "good" ? " good" : ""));
        seg.style.left = (a / total * 100) + "%";
        seg.style.width = Math.max((b - a) / total * 100, 0.4) + "%";
        seg.title = mmss(a) + " – " + mmss(b);
        track.append(seg);
      }
      const ph = el("b", "tl-ph"); track.append(ph); playheads.push(ph);
      track.addEventListener("click", (ev) => { const r = track.getBoundingClientRect(); seek((ev.clientX - r.left) / r.width * total); });
      row.append(track); box.append(row);
    }
    updatePlayheads();
  }

  function renderTable() {
    const box = $("table"); box.replaceChildren();
    const t = el("table", "sig"), hr = el("tr");
    ["col_signal", "col_time", "col_times", "col_longest"].forEach((k) => hr.append(el("th", null, T(k))));
    const head = el("thead"); head.append(hr); t.append(head);
    const body = el("tbody");
    let group = null;
    for (const [s, g] of SIG.map((x) => [x, "body"]).concat(voice() ? VSIG.map((x) => [x, "voice"]) : [])) {
      const d = sdata(s); if (!d) continue;
      if (voice() && g !== group) {
        group = g; const gr = el("tr", "grp"), c = el("td", null, T("tl_" + g)); c.colSpan = 4; gr.append(c); body.append(gr);
      }
      const tr = el("tr"), share = el("td");
      const bar = el("span", "bar" + (s.kind === "good" ? " good" : "")), fill = el("i");
      fill.style.width = Math.min(d.percent, 100) + "%"; bar.append(fill);
      share.append(bar, document.createTextNode(" "), el("span", "pct", d.percent.toFixed(1) + "%"));
      tr.append(el("td", null, lab(s)), share, el("td", "num", String(d.episodes)), el("td", "num", d.longest.toFixed(1) + T("unit_s")));
      body.append(tr);
    }
    t.append(body); box.append(t);
  }

  const pick = (o) => (o ? (KT.lang() === "ar" ? o.ar : o.en) : "");

  function goBtn(t) {
    const b = el("button", "go"); b.type = "button"; b.textContent = T("co_goto", { t: mmss(t) });
    b.addEventListener("click", () => seek(t)); return b;
  }

  function adviceRow(label, tip, start, said, stat) {
    const r = el("div", "arow"), head = el("div", "ahead");
    head.append(el("strong", null, label));
    if (stat) head.append(el("span", "astat", stat));
    r.append(head, el("p", "atip", tip));
    if (said) { const q = el("p", "asaid"); q.append(el("span", null, T("co_said") + ": "), el("q", null, said)); r.append(q); }
    if (start != null) r.append(goBtn(start));
    return r;
  }

  function renderCoach() {
    const box = $("coach"); box.replaceChildren();
    const c = job.result.coach;
    if (!c) return;
    if (!c.summary.length && !c.strengths.length) { box.append(el("div", "alert", T("co_none"))); return; }
    if (c.summary.length) {
      box.append(el("h3", null, T("co_priorities")));
      const g = el("div", "agrid");
      c.summary.forEach((s, i) => {
        const card = adviceRow(lab(s.label), pick(s.tip), s.start, "", T("co_stat", { p: Math.round(s.percent), n: s.episodes, l: Math.round(s.longest) }));
        card.classList.add("prio", s.kind); card.prepend(el("span", "anum", String(i + 1))); g.append(card);
      });
      box.append(g);
    } else box.append(el("div", "alert", T("co_none")));
    if (c.combined.length) {
      box.append(el("h3", null, T("co_together")));
      const l = el("div", "alist");
      c.combined.forEach((x) => l.append(adviceRow(pick(x.label), pick(x.tip), x.start, x.said)));
      box.append(l);
    }
    if (c.items.length) {
      box.append(el("h3", null, T("co_moments")));
      const l = el("div", "alist");
      c.items.forEach((x) => { const r = adviceRow(mmss(x.start) + "  ·  " + lab(x.label), pick(x.tip), x.start, x.said); r.classList.add(x.kind); l.append(r); });
      box.append(l);
    }
    if (c.strengths.length) {
      box.append(el("h3", null, T("co_strong")));
      const ul = el("ul", "astrong");
      c.strengths.forEach((x) => ul.append(el("li", null, pick(x))));
      box.append(ul);
    }
    box.append(el("p", "fine", T("co_note")));
  }

  // ---- practice score
  const SCN = window.SCENARIOS || {};
  const sl = (o) => (o ? (KT.lang() === "ar" ? o.ar : o.en) : "");
  const CIRC = 2 * Math.PI * 52;

  function dial(score, id) {
    const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 120 120"); svg.setAttribute("class", "dial " + id);
    const mk = (cls, extra) => { const c = document.createElementNS(NS, "circle"); c.setAttribute("cx", 60); c.setAttribute("cy", 60); c.setAttribute("r", 52); c.setAttribute("class", cls); Object.entries(extra || {}).forEach(([k, v]) => c.setAttribute(k, v)); return c; };
    svg.append(mk("d-bg"), mk("d-fg", { "stroke-dasharray": (CIRC * score / 100).toFixed(1) + " " + CIRC.toFixed(1), transform: "rotate(-90 60 60)" }));
    const t = document.createElementNS(NS, "text"); t.setAttribute("x", 60); t.setAttribute("y", 70); t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "d-num"); t.textContent = String(score);
    svg.append(t); return svg;
  }

  function renderScore() {
    const box = $("score"); box.replaceChildren();
    const sc = job.result.score, ctx = job.context || { scenario: "general", goal: "" };
    if (!sc) return;
    box.append(el("h2", null, T("res_score")));
    const top = el("div", "sc-top");
    const left = el("div", "sc-dial"); left.append(dial(sc.overall, sc.label.id), el("div", "sc-label " + sc.label.id, sl(sc.label)));
    const subs = el("div", "sc-subs");
    [["sco_body", sc.body], ["sco_voice", sc.voice]].forEach(([k, v]) => { if (v != null) { const d = el("div", "sc-sub"); d.append(el("span", null, T(k)), el("strong", null, String(v))); subs.append(d); } });
    left.append(subs);
    const right = el("div", "sc-ctx");
    const lab = el("label", null, T("sco_for")); lab.htmlFor = "sc-sel";
    const sel = el("select"); sel.id = "sc-sel";
    Object.keys(SCN).forEach((id) => { const o = el("option", null, SCN[id][KT.lang() === "ar" ? "ar" : "en"]); o.value = id; if (id === ctx.scenario) o.selected = true; sel.append(o); });
    const desc = el("p", "fine", SCN[ctx.scenario] ? SCN[ctx.scenario]["desc_" + (KT.lang() === "ar" ? "ar" : "en")] : "");
    const glab = el("label", null, T("sco_goal")); glab.htmlFor = "sc-goal";
    const goal = el("input"); goal.id = "sc-goal"; goal.type = "text"; goal.maxLength = 300; goal.value = ctx.goal || "";
    const upd = el("button", "btn ghost", T("sco_update")); upd.type = "button";
    const row = el("div", "sc-goalrow"); row.append(goal, upd);
    const err = el("div", "alert err", T("sco_error")); err.hidden = true;
    const apply = async () => {
      err.hidden = true; upd.disabled = sel.disabled = true;
      try {
        const r = await fetch("/api/jobs/" + JOB + "/context", { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario: sel.value, goal: goal.value.trim() }) });
        if (!r.ok) throw new Error("bad");
        job = await r.json(); renderScore(); renderCoach();
      } catch (e) { err.hidden = false; upd.disabled = sel.disabled = false; }
    };
    sel.addEventListener("change", apply); upd.addEventListener("click", apply);
    goal.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); apply(); } });
    right.append(lab, sel, desc, glab, row, err);
    top.append(left, right); box.append(top);
    box.append(el("h3", null, T("sco_lost")));
    if (!sc.lost.length) box.append(el("p", "fine", T("sco_none")));
    else { const ul = el("ul", "sc-lost"); sc.lost.forEach((x) => { const li = el("li"); const pts = el("strong"), num = el("bdi", null, "\u2212" + x.points); num.dir = "ltr"; pts.append(num, document.createTextNode(" " + T("sco_pts"))); li.append(el("span", null, sl(x.label)), pts); ul.append(li); }); box.append(ul); }
    box.append(el("p", "fine", T("sco_note")));
  }

  // ---- chat
  let chatMsgs = [], chatEngine = null, chatBusy = false, chatLoaded = false;
  const TS = /\b(\d{1,2}):([0-5]\d)\b/g;

  function inline(parent, text) {                 // **bold** and m:ss links, built as DOM nodes (no innerHTML)
    text.split(/\*\*(.+?)\*\*/g).forEach((part, i) => {
      if (!part) return;
      const host = i % 2 ? parent.appendChild(el("strong")) : parent;
      let last = 0, m; TS.lastIndex = 0;
      while ((m = TS.exec(part))) {
        if (m.index > last) host.append(document.createTextNode(part.slice(last, m.index)));
        const t = parseInt(m[1], 10) * 60 + parseInt(m[2], 10), btn = el("button", "tsl", m[0]);
        btn.type = "button"; btn.addEventListener("click", () => seek(t)); host.append(btn);
        last = m.index + m[0].length;
      }
      host.append(document.createTextNode(part.slice(last)));
    });
  }

  function bubble(role, text) {
    const b = el("div", "msg " + role);
    if (role === "coach") inline(b, text.replace(/^#{1,6}\s*/gm, "").replace(/^\s*[*-]\s+/gm, "• ")); else b.textContent = text;
    return b;
  }

  function renderChat() {
    const log = $("ch-log"); log.replaceChildren();
    log.append(bubble("coach", T("ch_hello")));
    chatMsgs.forEach((m) => log.append(bubble(m.role, m.text)));
    if (chatBusy) log.append(el("div", "msg coach thinking", T("ch_thinking")));
    log.scrollTop = log.scrollHeight;
    const chips = $("ch-chips"); chips.replaceChildren();
    if (!chatMsgs.length) ["ch_chip1", "ch_chip2", "ch_chip3", "ch_chip4"].forEach((k) => {
      const c = el("button", "chip", T(k)); c.type = "button"; c.addEventListener("click", () => sendChat(T(k))); chips.append(c);
    });
    $("ch-input").placeholder = T("ch_placeholder");
    const e = $("ch-engine"); e.replaceChildren();
    if (chatEngine) {
      e.append(el("strong", null, T("ch_engine", { e: chatEngine.label })));
      e.append(document.createTextNode("  ·  " + (chatEngine.online ? T("ch_online", { e: chatEngine.label }) : chatEngine.engine === "none" ? T("ch_rules") : "")));
    }
    $("ch-send").disabled = chatBusy;
  }

  function chatError(code) {
    const a = $("ch-alert"), k = "ch_err_" + code, s = KT.t(k);
    a.textContent = s === k ? T("ch_err_llm_failed") : s; a.hidden = false;
  }

  async function loadChat() {
    if (chatLoaded) { renderChat(); return; }
    try {
      const r = await fetch("/api/jobs/" + JOB + "/chat");
      if (r.ok) { const d = await r.json(); chatMsgs = d.messages; chatEngine = d.engine; chatLoaded = true; }
    } catch (e) { /* the chat just stays empty */ }
    renderChat();
  }

  async function sendChat(text) {
    text = (text || "").trim();
    if (!text || chatBusy) return;
    $("ch-alert").hidden = true; $("ch-input").value = "";
    chatMsgs.push({ role: "user", text }); chatBusy = true; renderChat();
    try {
      const r = await fetch("/api/jobs/" + JOB + "/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, lang: KT.lang() }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { chatMsgs.pop(); chatError((d.detail && d.detail.code) || "llm_failed"); }
      else { chatMsgs.push({ role: "coach", text: d.reply }); chatEngine = d.engine; }
    } catch (e) { chatMsgs.pop(); chatError("network"); }
    chatBusy = false; renderChat();
  }

  $("ch-form").addEventListener("submit", (ev) => { ev.preventDefault(); sendChat($("ch-input").value); });
  $("ch-clear").addEventListener("click", async () => {
    if (!chatMsgs.length || !confirm(T("ch_confirm_clear"))) return;
    const r = await fetch("/api/jobs/" + JOB + "/chat", { method: "DELETE" });
    if (r.ok) { chatMsgs = []; $("ch-alert").hidden = true; renderChat(); }
  });

  function card(label, value, unit, note, cls) {
    const c = el("div", "vcard" + (cls ? " " + cls : ""));
    const v = el("div", "vval"); v.append(el("bdi", null, value));
    if (unit) v.append(el("small", null, " " + unit));
    c.append(el("div", "vlab", label), v, el("div", "vnote", note));
    return c;
  }

  function renderVoice() {
    const box = $("voice"); box.replaceChildren();
    const raw = job.result.voice;
    if (!raw) return;
    if (raw.error) { box.append(el("div", "alert", T("vo_err_" + raw.error))); return; }
    const o = raw.overall;
    if (o.level_note === "no_speech") { box.append(el("div", "alert", T("vo_no_speech"))); return; }
    const grid = el("div", "vgrid");
    const lv = o.level_note;
    grid.append(card(T("vo_level"), String(o.level_db), "dB", T("vo_level_" + lv), lv === "ok" ? "good" : "warn"));
    const w = o.wpm;
    const wk = w == null ? "na" : w > 250 ? "fast" : w < 110 ? "slow" : "ok";
    grid.append(card(T("vo_pace"), w == null ? "—" : String(Math.round(w)), w == null ? "" : T("vo_wpm"), T("vo_pace_" + wk), wk === "ok" ? "good" : wk === "na" ? "" : "warn"));
    const pr = o.pitch_range_st, flat = pr != null && pr < 2.5;
    grid.append(card(T("vo_pitch"), pr == null ? "—" : String(pr), pr == null ? "" : T("vo_st"), pr == null ? "" : T(flat ? "vo_pitch_flat" : "vo_pitch_ok"), pr == null ? "" : flat ? "warn" : "good"));
    grid.append(card(T("vo_share"), Math.round(o.speech_ratio * 100) + "%", "", mmss(o.speech_seconds), ""));
    box.append(grid, el("p", "fine", T("vo_note")));
    if (raw.stt_note === "no_stt") box.append(el("div", "alert", T("vo_no_stt")));
  }

  let segEls = [];
  function renderTranscript() {
    const wrap = $("transcript-box"), list = $("transcript"); list.replaceChildren(); segEls = [];
    const v = voice(), t = v && v.transcript;
    wrap.hidden = !t;
    if (!t) return;
    $("tr-meta").textContent = T("tr_lang", { l: (t.language || "").toUpperCase() });
    if (!t.segments.length) { list.append(el("li", "empty", T("tr_empty"))); return; }
    for (const g of t.segments) {
      const li = el("li"), b = el("button"); b.type = "button";
      b.append(el("time", null, mmss(g.start)), el("span", "tx", g.text));
      b.addEventListener("click", () => seek(g.start));
      li.append(b); list.append(li); segEls.push([g, li]);
    }
  }

  function markTranscript() {
    const t = vid.currentTime || 0;
    for (const [g, li] of segEls) li.classList.toggle("now", t >= g.start && t < g.end);
  }

  function renderDone() {
    $("state").replaceChildren(); $("view").hidden = false;
    if (!playerReady) {
      vid.src = "/api/jobs/" + JOB + "/video";
      vid.addEventListener("error", () => { vid.hidden = true; $("pl").hidden = true; $("vidnote").hidden = false; });
      vid.addEventListener("timeupdate", () => { updatePlayheads(); markTranscript(); });
      playerReady = true;
    }
    $("vidnote").textContent = T("res_novideo");
    renderMeta(); renderScore(); renderCoach(); renderMoments(); renderTimeline(); renderTable(); renderVoice(); renderTranscript(); loadChat();
    document.dispatchEvent(new CustomEvent("kinara:job", { detail: job }));
    $("adj").textContent = Object.keys(job.result.baseline_adjust || {}).length ? T("adj_note") : "";
  }

  function render() { if (job.status === "done") renderDone(); else renderState(); }

  function fatal(key) {
    const box = $("state"); box.replaceChildren(); $("view").hidden = true;
    box.append(el("div", "alert err", T(key)), newLink());
  }

  async function poll() {
    try {
      const r = await fetch("/api/jobs/" + JOB);
      if (r.status === 404) return fatal("err_notfound");
      job = await r.json();
    } catch (e) { timer = setTimeout(poll, 2000); return; }
    render();
    if (job.status === "queued" || job.status === "processing") timer = setTimeout(poll, 1000);
  }

  $("del").addEventListener("click", async () => {
    if (!confirm(T("res_confirm"))) return;
    const r = await fetch("/api/jobs/" + JOB, { method: "DELETE" });
    if (r.ok) location.href = "/sessions";
  });
  document.addEventListener("langchange", () => { if (job) render(); });
  poll();
})();
