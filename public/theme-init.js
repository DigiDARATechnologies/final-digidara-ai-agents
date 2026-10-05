// Applies the saved theme before the app renders, so the page never flashes
// the wrong theme. A separate file (not an inline <script>) so the
// Content-Security-Policy in nginx.conf can forbid inline scripts entirely.
try {
  var t = localStorage.getItem("digidara_theme");
  if (t === "system") t = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t === "light" ? "light" : "dark";
  var a = JSON.parse(localStorage.getItem("digidara_appearance") || "{}");
  if (a.accent) document.documentElement.dataset.accent = a.accent;
  document.documentElement.dataset.motion = a.reduceMotion ? "reduced" : "full";
}
catch (e) { document.documentElement.dataset.theme = "dark"; }
