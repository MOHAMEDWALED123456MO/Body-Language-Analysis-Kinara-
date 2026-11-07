(() => {
  const $ = (id) => document.getElementById(id);
  const here = location.pathname;
  const map = [["/dashboard", "dashboard"], ["/new", "new"], ["/analyze", "new"], ["/sessions", "sessions"], ["/results", "sessions"],
               ["/report", "sessions"], ["/progress", "progress"], ["/profile", "profile"], ["/admin", "admin"]];
  const hit = (map.find(([p]) => here === p || here.startsWith(p + "/")) || [])[1];
  document.querySelectorAll(".s-nav a").forEach((a) => a.classList.toggle("on", a.dataset.nav === hit));
  fetch("/api/me").then((r) => (r.ok ? r.json() : null)).then((me) => {
    if (!me || !me.auth) return;
    $("s-who").textContent = me.name;
    $("nav-admin").hidden = !me.admin;
  }).catch(() => {});
  $("logoutBtn").addEventListener("click", async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; });
  $("themeBtn").addEventListener("click", () => {
    const d = document.documentElement, next = d.dataset.theme === "light" ? "dark" : "light";
    d.dataset.theme = next; try { localStorage.setItem("theme", next); } catch (e) {}
  });
  $("burger").addEventListener("click", () => $("side").classList.toggle("open"));
  document.addEventListener("click", (e) => { if (!e.target.closest("#side, #burger")) $("side").classList.remove("open"); });
})();
