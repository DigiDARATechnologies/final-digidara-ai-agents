/** Shared pieces of the record-then-transcribe voice path used on phones.
 *
 * Desktop Chrome/Edge run the browser's live speech recognition and a second
 * microphone stream (a recorder, or a volume meter) side by side without
 * trouble. Phones do not: on Android the recognizer and the second stream
 * compete for the microphone and the recognizer often hears nothing, and on
 * iPhone/iPad recognition may only start from a tap. So on a phone the answer
 * is recorded on one stream and transcribed on the server instead. */

/** Android, iPhone, iPad (including iPadOS, which reports itself as a Mac). */
export function isMobileVoiceDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return true;
  return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
}

export function audioRecordingSupported(): boolean {
  return typeof window !== "undefined"
    && "MediaRecorder" in window
    && Boolean(navigator.mediaDevices?.getUserMedia);
}

/** The first recording format this browser supports. iPhone records mp4/AAC;
 * everything else prefers webm/opus. Undefined lets the browser pick. */
export function preferredRecordingType(): string | undefined {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") return undefined;
  const appleMobile = /iPhone|iPad|iPod/i.test(navigator.userAgent);
  const candidateTypes = appleMobile
    ? ["audio/mp4", "audio/mp4;codecs=mp4a.40.2", "audio/webm;codecs=opus", "audio/webm"]
    : ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4", "audio/mp4;codecs=mp4a.40.2"];
  return candidateTypes.find((type) => MediaRecorder.isTypeSupported(type));
}

/** The MIME type the server should be told, without codec parameters. */
export function baseAudioType(audio: Blob): string {
  return (audio.type || "audio/webm").split(";", 1)[0].toLowerCase();
}

export async function audioBlobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

/** A microphone failure in words the student can act on. */
export function microphoneErrorMessage(error: unknown): string {
  const name = (error as { name?: string })?.name ?? "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone permission was denied. Allow microphone access for this site in your browser settings, then tap the microphone again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No microphone was found on this device.";
  if (name === "NotReadableError" || name === "AbortError") {
    return "The microphone is being used by another app. Close it (for example a call or voice recorder), then tap the microphone again.";
  }
  return "The microphone could not start. Tap the microphone to try again, or type your answer.";
}
