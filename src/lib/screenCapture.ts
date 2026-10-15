/**
 * A screenshot of the DigiDARA page the learner is on, taken in the browser by
 * drawing the page itself (html2canvas-pro), so it works on every device: a
 * phone cannot share its screen with getDisplayMedia, but it can draw its page.
 * Only this app's page is captured, never other tabs or windows. Anything
 * marked data-screenshot-hide (Boss's own panel) is left out.
 */
const MAX_WIDTH = 1280;
// The server accepts up to 2.8M characters of data URL; stay well under.
const MAX_CHARS = 2_000_000;

export const SCREENSHOT_HIDE_ATTRIBUTE = "data-screenshot-hide";

/** A JPEG data URL of the page, or null when it could not be drawn. */
export async function captureScreenshot(): Promise<string | null> {
  if (typeof document === "undefined") return null;
  try {
    const { default: html2canvas } = await import("html2canvas-pro");
    const width = document.documentElement.clientWidth || window.innerWidth;
    const canvas = await html2canvas(document.body, {
      scale: Math.min(1, MAX_WIDTH / width),
      useCORS: true,
      logging: false,
      backgroundColor: getComputedStyle(document.body).backgroundColor || "#ffffff",
      // The visible part of the page, where the learner's doubt is.
      x: window.scrollX,
      y: window.scrollY,
      width: window.innerWidth,
      height: window.innerHeight,
      ignoreElements: (element) => element.hasAttribute(SCREENSHOT_HIDE_ATTRIBUTE),
    });
    for (const quality of [0.72, 0.55, 0.4]) {
      const url = canvas.toDataURL("image/jpeg", quality);
      if (url.length <= MAX_CHARS) return url;
    }
    return null;
  } catch {
    return null;
  }
}
