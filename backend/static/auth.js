(() => {
  const $ = (id) => document.getElementById(id);
  const T = (k) => KT.t(k);
  let mode = "login", errKey = null;
  const MAP = { bad_login: "au_err_login", email_taken: "au_err_taken", weak_password: "au_err_weak", bad_email: "au_err_email",
                bad_name: "au_err_name", too_many: "au_err_many" };
  function showErr(k) { errKey = k; const a = $("au-alert"); a.hidden = !k; if (k) a.textContent = T(k); }
  function render() {
    const reg = mode === "register";
    $("au-h").textContent = T(reg ? "au_register" : "au_login");
    $("au-go").textContent = T(reg ? "au_register" : "au_login");
    $("au-switch").textContent = T(reg ? "au_have" : "au_new");
    $("l-name").hidden = $("au-name").hidden = $("au-hint").hidden = !reg;
    $("au-pass").autocomplete = reg ? "new-password" : "current-password";
    if (errKey) showErr(errKey);
  }
  $("au-switch").addEventListener("click", () => { mode = mode === "login" ? "register" : "login"; showErr(null); render(); });
  $("au-form").addEventListener("submit", async (e) => {
    e.preventDefault(); showErr(null);
    const body = { email: $("au-email").value.trim(), password: $("au-pass").value };
    if (mode === "register") body.name = $("au-name").value.trim();
    $("au-go").disabled = true;
    try {
      const r = await fetch("/api/" + mode, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (r.ok) { location.href = window.NEXT || "/dashboard"; return; }
      const d = await r.json().catch(() => ({}));
      showErr(MAP[d.detail && d.detail.code] || "au_err_net");
    } catch (err) { showErr("au_err_net"); }
    $("au-go").disabled = false;
  });
  document.addEventListener("langchange", render);
  render();
})();
