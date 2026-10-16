/** Where the natural voice is served from (the orchestrator gateway). Its own
 * module so the voice engine can be tested without Vite's import.meta. */
export const VOICE_API_BASE = (() => {
  const raw = import.meta.env.VITE_GATEWAY_API_URL !== undefined ? String(import.meta.env.VITE_GATEWAY_API_URL) : "http://127.0.0.1:8100";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
})();
