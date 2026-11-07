(() => {
  const $ = (id) => document.getElementById(id);
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  let rows = [], me = { name: "", email: "" };
  const BADGES = [["ac_first", "①", (s) => s.n >= 1], ["ac_five", "⑤", (s) => s.n >= 5], ["ac_ten", "⑩", (s) => s.n >= 10],
                  ["ac_70", "★", (s) => s.best >= 70], ["ac_85", "✦", (s) => s.best >= 85]];
  function render() {
    const sc = rows.filter((r) => r.overall != null), n = rows.length, best = sc.length ? Math.round(Math.max(...sc.map((r) => r.overall))) : 0;
    const avg = sc.length ? Math.round(sc.reduce((a, r) => a + r.overall, 0) / sc.length) : 0;
    const xp = n * 50 + Math.round(sc.reduce((a, r) => a + r.overall, 0)), lvl = Math.floor(xp / 200) + 1;
    $("avatar").textContent = (me.name || "?").trim().charAt(0).toUpperCase(); $("p-name").textContent = me.name; $("p-mail").textContent = me.email || "";
    $("p-lvl").textContent = KT.t("pf_level") + " " + lvl; $("p-bar").style.width = ((xp % 200) / 2) + "%"; $("p-xp").textContent = (xp % 200) + " / 200 XP";
    const st = $("p-stats"); st.replaceChildren();
    [[n, "st_sessions"], [avg || "–", "st_avg"], [best || "–", "st_best"]].forEach(([v, k]) => { const d = el("div", "stat"); d.append(el("b", null, v), el("span", null, KT.t(k))); st.append(d); });
    const box = $("ach"); box.replaceChildren(); const s = { n, best };
    BADGES.forEach(([k, ic, ok]) => { const d = el("div", "badge" + (ok(s) ? " on" : "")); d.append(el("i", null, ic), el("span", null, KT.t(k))); box.append(d); });
  }
  Promise.all([fetch("/api/sessions").then((r) => (r.ok ? r.json() : [])), fetch("/api/me").then((r) => (r.ok ? r.json() : null))])
    .then(([s, m]) => { rows = s; if (m && m.auth) me = m; render(); });
  document.addEventListener("langchange", render);
})();
