(() => {
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const SC = window.SCENARIOS || {}, lang = () => (KT.lang() === "ar" ? "ar" : "en");
  let rows = [], me = null;
  const stat = (v, k) => { const d = el("div", "stat"); d.append(el("b", null, v), el("span", null, KT.t(k))); return d; };
  function render() {
    if (me) document.getElementById("hello").textContent = KT.t("db_hello").replace("{n}", me.name.split(" ")[0]);
    const scored = rows.filter((r) => r.overall != null), avg = scored.length ? Math.round(scored.reduce((a, r) => a + r.overall, 0) / scored.length) : "–";
    const best = scored.length ? Math.round(Math.max(...scored.map((r) => r.overall))) : "–";
    const box = document.getElementById("stats"); box.replaceChildren(stat(rows.length, "st_sessions"), stat(avg, "st_avg"), stat(best, "st_best"));
    const ul = document.getElementById("recent-list"); ul.replaceChildren();
    if (!rows.length) { const li = el("li", "empty"); li.append(el("div", "ill", "◌"), el("p", null, KT.t("db_empty")), Object.assign(el("a", "btn", KT.t("nav_new")), { href: "/new" })); ul.append(li); }
    rows.slice(0, 5).forEach((r) => {
      const li = el("li"), a = el("a"); a.href = "/results/" + r.id;
      a.append(el("span", null, (SC[r.scenario] || {})[lang()] || r.scenario), el("b", null, r.overall != null ? Math.round(r.overall) : "…"));
      li.append(a); ul.append(li);
    });
    const sp = document.getElementById("spark"); sp.replaceChildren();
    scored.slice(0, 12).reverse().forEach((r) => { const i = el("i"); i.style.height = Math.max(6, r.overall) + "%"; i.title = Math.round(r.overall); sp.append(i); });
  }
  Promise.all([fetch("/api/sessions").then((r) => (r.ok ? r.json() : [])), fetch("/api/me").then((r) => (r.ok ? r.json() : null))])
    .then(([s, m]) => { rows = s; me = m && m.auth ? m : { name: "" }; render(); });
  document.addEventListener("langchange", render);
})();
