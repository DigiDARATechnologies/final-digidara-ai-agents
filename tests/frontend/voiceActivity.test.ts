import { VoiceDetector } from '../../src/lib/voiceActivity';

const BIN_HZ = 48000 / 1024; // about 47 Hz per bin
const BINS = 512;

/** A frame of a given loudness (0-1). */
function wave(level: number): Uint8Array {
  return Uint8Array.from({ length: 1024 }, (_, i) => Math.round(128 + 127 * level * Math.SQRT2 * Math.sin(i / 3)));
}

/** A spectrum with its energy between two frequencies. */
function spectrum(lowHz: number, highHz: number): Uint8Array {
  return Uint8Array.from({ length: BINS }, (_, bin) => (bin * BIN_HZ >= lowHz && bin * BIN_HZ <= highHz ? 200 : 5));
}

const FAN = spectrum(80, 280);        // a fan or AC hum: low frequencies only
const VOICE = spectrum(300, 3400);    // speech: the voice band

test('a steady fan is never taken for speech, however long it runs', () => {
  const detector = new VoiceDetector();
  const heard = Array.from({ length: 600 }, () => detector.sample(wave(0.08), FAN, BIN_HZ).speaking);
  expect(heard.some(Boolean)).toBe(false);
});

test('a voice over the fan is speech', () => {
  const detector = new VoiceDetector();
  for (let i = 0; i < 300; i += 1) detector.sample(wave(0.03), FAN, BIN_HZ);
  const heard = Array.from({ length: 5 }, () => detector.sample(wave(0.2), VOICE, BIN_HZ).speaking);
  expect(heard.at(-1)).toBe(true);
});

test('a single loud click is not speech; a few frames of voice are', () => {
  const detector = new VoiceDetector();
  for (let i = 0; i < 50; i += 1) detector.sample(wave(0.005), FAN, BIN_HZ);
  expect(detector.sample(wave(0.3), VOICE, BIN_HZ).speaking).toBe(false);
  expect(detector.sample(wave(0.005), FAN, BIN_HZ).speaking).toBe(false);
  detector.sample(wave(0.2), VOICE, BIN_HZ);
  detector.sample(wave(0.2), VOICE, BIN_HZ);
  expect(detector.sample(wave(0.2), VOICE, BIN_HZ).speaking).toBe(true);
});

test('a noisy room raises the bar: talking quietly at the noise level is not enough', () => {
  const detector = new VoiceDetector();
  // Steady broadband noise (traffic) with voice-band content too.
  for (let i = 0; i < 600; i += 1) detector.sample(wave(0.05), spectrum(80, 8000), BIN_HZ);
  expect(detector.noiseFloor).toBeGreaterThan(0.03);
  const quiet = Array.from({ length: 5 }, () => detector.sample(wave(0.06), VOICE, BIN_HZ).speaking);
  expect(quiet.some(Boolean)).toBe(false);
  const clear = Array.from({ length: 5 }, () => detector.sample(wave(0.25), VOICE, BIN_HZ).speaking);
  expect(clear.at(-1)).toBe(true);
});
