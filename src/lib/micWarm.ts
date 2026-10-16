/**
 * The microphone, opened once for a whole voice conversation. It is opened
 * while Boss is still greeting (the permission prompt and the device start-up
 * are then done), and kept open: every recording, and the listener that waits
 * for the learner to talk over Boss, gets its own clone of this stream. A
 * clone can be stopped without closing the microphone, so interrupting Boss
 * does not wait for the device to open again and the first words are not lost.
 */
export const MICROPHONE_CONSTRAINTS: MediaStreamConstraints = {
  audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
};

let held: Promise<MediaStream | null> | null = null;

/** Starts opening the microphone and keeps it open until releaseWarmMicrophone.
 * Never throws: a refusal is reported again (as usual) when listening starts. */
export function warmMicrophone(): void {
  if (held || typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return;
  held = navigator.mediaDevices.getUserMedia(MICROPHONE_CONSTRAINTS).catch(() => null);
}

/** A stream of the microphone for one recording or listener: a clone of the
 * open one while a conversation holds it, else a fresh one. The caller may
 * stop its tracks. */
export async function acquireMicrophone(): Promise<MediaStream> {
  const stream = held ? await held : null;
  if (stream && stream.getAudioTracks().some((track) => track.readyState === "live")) return stream.clone();
  held = null;
  return navigator.mediaDevices.getUserMedia(MICROPHONE_CONSTRAINTS);
}

/** Closes the open microphone (the conversation ended). */
export function releaseWarmMicrophone(): void {
  const pending = held;
  held = null;
  void pending?.then((stream) => stream?.getTracks().forEach((track) => track.stop()));
}
