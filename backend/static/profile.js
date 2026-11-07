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
(() => {
  const $ = (id) => document.getElementById(id);
  const say = (id, key, bad) => { const m = $(id); m.hidden = false; m.textContent = KT.t(key); m.style.color = bad ? "var(--danger,#ff5d6c)" : "var(--cyan)"; };
  const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
  const ph = () => { $("pw-old").placeholder = KT.t("pf_pw_old"); $("pw-new").placeholder = KT.t("pf_pw_new"); $("del-pw").placeholder = KT.t("au_password") !== "au_password" ? KT.t("au_password") : "Password"; };
  ph(); document.addEventListener("langchange", ph);
  $("pw-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await post("/api/account/password", { old: $("pw-old").value, new: $("pw-new").value });
    if (r.ok) { say("pw-msg", "pf_pw_ok"); e.target.reset(); } else say("pw-msg", r.status === 400 ? "pf_pw_weak" : "pf_pw_bad", true);
  });
  $("del-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!confirm(KT.t("pf_del_confirm"))) return;
    const r = await post("/api/account/delete", { password: $("del-pw").value });
    if (r.ok) location.href = "/"; else say("del-msg", r.status === 409 ? "ss_busy" : "pf_pw_bad", true);
  });
})();
