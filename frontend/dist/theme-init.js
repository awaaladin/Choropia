(function () {
  try {
    var p = JSON.parse(localStorage.getItem("choropia-preferences") || "{}");
    var root = document.documentElement;
    if (p.theme === "dark") root.classList.add("dark");
    if (p.motion === "reduced") root.dataset.motion = "reduced";
  } catch (e) {}
})();
