(() => {
  const nav = document.querySelector(".nav nav"); if (!nav) return;
  fetch("/api/me").then((r) => (r.ok ? r.json() : null)).then((me) => {
    if (!me || !me.auth) return;
    const box = document.createElement("span"); box.className = "who";
    const name = document.createElement("span"); name.textContent = me.name;
    const out = document.createElement("button"); out.type = "button"; out.className = "lang"; out.textContent = KT.t("au_logout");
    out.addEventListener("click", async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; });
    box.append(name, out); nav.append(box);
    document.addEventListener("langchange", () => { out.textContent = KT.t("au_logout"); });
  }).catch(() => {});
})();
