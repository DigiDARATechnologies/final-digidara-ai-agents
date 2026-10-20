// Sets the theme and saved appearance before the app renders, so the page never
// flashes. A separate file (not an inline <script>) so the
// Content-Security-Policy in nginx.conf can forbid inline scripts entirely.
// DigiDARA has one theme: light (white). A theme saved while dark mode
// existed is ignored.
document.documentElement.dataset.theme = "light";
try {
  var a = JSON.parse(localStorage.getItem("digidara_appearance") || "{}");
  if (a.accent) document.documentElement.dataset.accent = a.accent;
  document.documentElement.dataset.motion = a.reduceMotion ? "reduced" : "full";
}
catch (e) { /* storage unavailable: default appearance */ }
