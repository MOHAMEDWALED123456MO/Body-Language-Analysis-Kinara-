(() => {
  const $ = (id) => document.getElementById(id);
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  let data = null;
  const fmt = (iso) => { try { return new Date(iso).toLocaleString(KT.lang() === "ar" ? "ar-EG" : "en-GB", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return iso || ""; } };
  function render() {
    if (!data) return;
    const st = $("ad-stats"); st.replaceChildren();
    [[data.stats.users, "ad_n_users"], [data.stats.sessions, "st_sessions"], [data.stats.avg_score ?? "–", "st_avg"]].forEach(([v, k]) => {
      const d = el("div", "stat"); d.append(el("b", null, v), el("span", null, KT.t(k))); st.append(d); });
    const t = $("ad-users"); t.replaceChildren();
    const h = el("tr"); ["ad_name", "ad_email", "ad_role", "st_sessions", "ad_joined"].forEach((k) => h.append(el("th", null, KT.t(k)))); t.append(h);
    data.users.forEach((u) => { const r = el("tr"); [u.name, u.email, u.role, u.sessions, fmt(u.joined)].forEach((v, i) => { const td = el("td", null, v); if (i === 1) td.dir = "ltr"; r.append(td); }); t.append(r); });
    const ul = $("ad-logs"); ul.replaceChildren();
    data.logs.forEach((l) => { const li = el("li", l.level || ""); li.append(el("time", null, fmt(l.time)), el("span", null, l.message)); ul.append(li); });
  }
  fetch("/api/admin/overview").then((r) => (r.ok ? r.json() : null)).then((d) => { data = d; render(); });
  document.addEventListener("langchange", render);
})();
