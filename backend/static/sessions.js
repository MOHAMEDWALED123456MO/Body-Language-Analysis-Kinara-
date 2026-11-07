(() => {
  const $ = (id) => document.getElementById(id);
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const SC = window.SCENARIOS || {}, lang = () => (KT.lang() === "ar" ? "ar" : "en");
  let rows = []; const sel = new Set();
  const fmt = (iso) => { try { return new Date(iso).toLocaleString(lang() === "ar" ? "ar-EG" : "en-GB", { dateStyle: "medium", timeStyle: "short" }); } catch (e) { return iso; } };
  function sync() { $("del-sel").disabled = !sel.size; $("pick-all").checked = rows.length > 0 && sel.size === rows.length; }
  function render() {
    const ul = $("slist"); ul.replaceChildren();
    if (!rows.length) { const li = el("li", "empty"); li.append(el("div", "ill", "◌"), el("p", null, KT.t("db_empty")), Object.assign(el("a", "btn", KT.t("nav_new")), { href: "/new" })); ul.append(li); }
    rows.forEach((r) => {
      const li = el("li"), cb = el("input"); cb.type = "checkbox"; cb.checked = sel.has(r.id);
      cb.addEventListener("change", () => { cb.checked ? sel.add(r.id) : sel.delete(r.id); sync(); });
      const a = el("a", "s-main"); a.href = "/results/" + r.id;
      a.append(el("strong", null, r.name), el("span", "fine", ((SC[r.scenario] || {})[lang()] || r.scenario) + " · " + fmt(r.created) + (r.status !== "done" ? " · " + r.status : "")));
      const sc = el("b", "pill", r.overall != null ? Math.round(r.overall) : "–");
      const d = el("button", "btn ghost danger sm", KT.t("res_delete")); d.type = "button";
      d.addEventListener("click", () => remove([r.id], KT.t("res_confirm")));
      li.append(cb, a, sc, d); ul.append(li);
    });
    sync();
  }
  async function remove(ids, msg, all) {
    if (!confirm(msg)) return;
    const r = await fetch("/api/sessions/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, all: !!all }) });
    if (!r.ok) return;
    const j = await r.json(); ids.forEach((i) => sel.delete(i)); await load();
    if (j.busy) { const a = $("alert"); a.hidden = false; a.className = "alert err"; a.textContent = KT.t("ss_busy"); }
  }
  async function load() { rows = await (await fetch("/api/sessions")).json(); render(); }
  $("pick-all").addEventListener("change", (e) => { sel.clear(); if (e.target.checked) rows.forEach((r) => sel.add(r.id)); render(); });
  $("del-sel").addEventListener("click", () => remove([...sel], KT.t("ss_confirm_sel").replace("{n}", sel.size)));
  $("del-all").addEventListener("click", () => rows.length && remove([], KT.t("ss_confirm_all"), true));
  document.addEventListener("langchange", render);
  load();
})();
