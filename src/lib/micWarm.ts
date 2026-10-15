/**
 * The microphone, opened ahead of time. A voice conversation asks for it while
 * Boss is still greeting, so the permission prompt and the device start-up are
 * done by the time the learner speaks; the first recording then takes this
 * stream instead of opening a new one.
 */
export const MICROPHONE_CONSTRAINTS: MediaStreamConstraints = {
  audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
};

let warm: Promise<MediaStream | null> | null = null;

/** Starts opening the microphone. Never throws: a refusal is reported again
 * (as usual) when listening starts. */
export function warmMicrophone(): void {
  if (warm || typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
  warm = navigator.mediaDevices.getUserMedia(MICROPHONE_CONSTRAINTS).catch(() => null);
}

/** The warmed stream when it is still live (used once), else a fresh one. */
export async function acquireMicrophone(): Promise<MediaStream> {
  const pending = warm;
  warm = null;
  const stream = pending ? await pending : null;
  if (stream && stream.getAudioTracks().some((track) => track.readyState === "live")) return stream;
  return navigator.mediaDevices.getUserMedia(MICROPHONE_CONSTRAINTS);
}

/** Closes a warmed microphone nobody used (the conversation was closed). */
export function releaseWarmMicrophone(): void {
  const pending = warm;
  warm = null;
  void pending?.then((stream) => stream?.getTracks().forEach((track) => track.stop()));
}
