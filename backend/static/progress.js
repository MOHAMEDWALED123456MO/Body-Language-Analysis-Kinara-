(() => {
  const $ = (id) => document.getElementById(id);
  const SIG = (window.SIGNALS || []).concat(window.VOICE_SIGNALS || []), SCN = window.SCENARIOS || {};
  const T = (k) => KT.t(k);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const ar = () => KT.lang() === "ar";
  const lab = (o) => (o ? (ar() ? o.ar : o.en) : "");
  const bdi = (t) => { const b = el("bdi", null, t); b.dir = "ltr"; return b; };
  const mmss = (s) => { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const day = (iso) => { try { return new Date(iso).toLocaleDateString(ar() ? "ar-EG-u-nu-latn" : "en-GB", { day: "numeric", month: "short" }); } catch (e) { return ""; } };
  let rows = [], a = 0, b = 0;

  function stats() {
    const box = $("pg-stats"); box.replaceChildren();
    const sc = rows.map((r) => r.overall), best = Math.max(...sc), avg = Math.round(sc.reduce((x, y) => x + y, 0) / sc.length);
    const d = sc[sc.length - 1] - sc[0];
    const card = (l, v, cls) => { const c = el("div", "vcard" + (cls ? " " + cls : "")), x = el("div", "vval"); x.append(bdi(v)); c.append(el("div", "vlab", l), x); return c; };
    box.append(card(T("pg_count"), String(rows.length)), card(T("pg_best"), String(best), "good"), card(T("pg_avg"), String(avg)),
      card(T("pg_change"), rows.length > 1 ? (d > 0 ? "+" : d < 0 ? "−" : "") + Math.abs(d) : "—", d > 0 ? "good" : d < 0 ? "warn" : ""));
  }

  function chart() {
    const box = $("pg-chart"); box.replaceChildren();
    const NS = "http://www.w3.org/2000/svg", W = 640, H = 240, L = 34, R = 26, Tp = 14, B = 30;
    const svg = document.createElementNS(NS, "svg"); svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const mk = (n, at, txt) => { const e = document.createElementNS(NS, n); for (const k in at) e.setAttribute(k, at[k]); if (txt != null) e.textContent = txt; svg.append(e); return e; };
    const y = (v) => Tp + (H - Tp - B) * (1 - v / 100);
    const x = (i) => rows.length === 1 ? (L + W - R) / 2 : L + (W - L - R) * i / (rows.length - 1);
    [0, 25, 50, 75, 100].forEach((v) => { mk("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "g" }); mk("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end", class: "t" }, String(v)); });
    mk("polyline", { class: "ln", points: rows.map((r, i) => x(i) + "," + y(r.overall)).join(" ") });
    rows.forEach((r, i) => {
      const c = mk("circle", { cx: x(i), cy: y(r.overall), r: 6, class: "pt" + (i === a || i === b ? " sel" : "") });
      const t = document.createElementNS(NS, "title"); t.textContent = r.name + " · " + day(r.created) + " · " + r.overall; c.append(t);
      c.addEventListener("click", () => { if (i !== b) { a = Math.min(i, b); b = Math.max(i, b); } compare(); chart(); });
      if (rows.length <= 12 || i % Math.ceil(rows.length / 12) === 0) mk("text", { x: x(i), y: H - 8, "text-anchor": "middle", class: "t" }, day(r.created));
    });
    box.append(svg);
  }

  const goodHigh = (id) => { const s = SIG.find((q) => q.id === id); return s && s.kind === "good"; };
  function delta(parent, d, higherBetter) {
    const good = higherBetter ? d > 0 : d < 0, c = d === 0 ? "flat" : good ? "up" : "down";
    const s = el("span", c); s.append(bdi((d > 0 ? "+" : d < 0 ? "−" : "") + Math.abs(Math.round(d * 10) / 10)));
    s.append(document.createTextNode("  " + (d === 0 ? T("pg_same") : good ? T("pg_better") : T("pg_worse")))); parent.append(s);
  }

  function compare() {
    const box = $("pg-cmp"); box.replaceChildren();
    if (rows.length < 2) { box.append(el("p", "fine", T("pg_one"))); return; }
    const sel = el("div", "pg-sel");
    const mkSel = (labelKey, cur, set) => {
      const l = el("label", null, T(labelKey)), s = el("select");
      rows.forEach((r, i) => { const o = el("option", null, day(r.created) + " · " + r.name + " (" + r.overall + ")"); o.value = i; if (i === cur) o.selected = true; s.append(o); });
      s.addEventListener("change", () => { set(parseInt(s.value, 10)); compare(); chart(); }); l.append(s); return l;
    };
    sel.append(mkSel("pg_a", a, (v) => { a = v; }), mkSel("pg_b", b, (v) => { b = v; }));
    box.append(sel);
    const A = rows[a], B = rows[b], t = el("table", "sig"), hr = el("tr");
    [T("pg_sig"), day(A.created), day(B.created), ""].forEach((h) => hr.append(el("th", null, h)));
    const th = el("thead"); th.append(hr); t.append(th); const tb = el("tbody");
    const line = (name, va, vb, hb, sfx) => {
      if (va == null || vb == null) return;
      const tr = el("tr"), c4 = el("td"); delta(c4, vb - va, hb);
      const c2 = el("td", "num"), c3 = el("td", "num"); c2.append(bdi(va + sfx)); c3.append(bdi(vb + sfx));
      tr.append(el("td", null, name), c2, c3, c4); tb.append(tr);
    };
    line(T("pg_overall"), A.overall, B.overall, true, ""); line(T("sco_body"), A.body, B.body, true, ""); line(T("sco_voice"), A.voice, B.voice, true, "");
    SIG.forEach((s) => { const va = A.signals[s.id], vb = B.signals[s.id]; if ((va || 0) === 0 && (vb || 0) === 0) return; line(lab(s), va || 0, vb || 0, goodHigh(s.id), "%"); });
    t.append(tb); box.append(t, el("p", "fine", T("pg_lowbetter")));
  }

  function list() {
    const box = $("pg-list"); box.className = "pg-list"; box.replaceChildren();
    rows.slice().reverse().forEach((r) => {
      const l = el("a", "row"), left = el("span"), right = el("span");
      l.href = "/results/" + r.id;
      left.append(el("strong", null, r.name), document.createTextNode("  ·  " + day(r.created) + "  ·  " + lab(SCN[r.scenario]) + "  ·  "), bdi(mmss(r.seconds)));
      right.append(bdi(String(r.overall)), document.createTextNode("  " + lab(r.label)));
      l.append(left, right); box.append(l);
    });
  }

  function render() {
    $("pg-empty").hidden = rows.length > 0; $("pg").hidden = !rows.length;
    if (!rows.length) return;
    stats(); chart(); compare(); list();
  }

  fetch("/api/progress").then((r) => r.json()).then((d) => {
    rows = d; b = rows.length - 1; a = Math.max(0, b - 1); render();
  }).catch(() => { rows = []; render(); });
  document.addEventListener("langchange", render);
})();
