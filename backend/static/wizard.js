(() => {
  const steps = [...document.querySelectorAll(".step")], dots = [...document.querySelectorAll("#stepper li")];
  function go(n) {
    steps.forEach((s) => (s.hidden = s.dataset.step !== String(n)));
    dots.forEach((d, i) => { d.classList.toggle("on", i + 1 === n); d.classList.toggle("done", i + 1 < n); });
    scrollTo({ top: 0, behavior: "smooth" });
  }
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(+b.dataset.go)));
  go(1);
})();
