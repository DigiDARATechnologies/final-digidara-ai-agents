import { acquireMicrophone } from "./micWarm";
/**
 * Telling a person speaking apart from a fan, AC, traffic or room hum, for
 * every microphone in the app.
 *
 * A frame counts as speech only when all three hold:
 * - it is clearly louder than the room's own steady noise (a noise floor
 *   that follows the background: quickly down, slowly up, so a constant fan
 *   becomes "background" within a few seconds while speech does not);
 * - most of its energy is in the human voice band (about 300-3400 Hz), where
 *   fans and hum have little;
 * - it lasts a few frames in a row (a click or a tap is not speech).
 */
export interface VoiceDetectorOptions {
  /** Never speech below this level (0-1 RMS). */
  minLevel?: number;
  /** How far above the background noise speech must be. */
  aboveNoise?: number;
  /** The share of energy that must be in the voice band. */
  voiceBand?: number;
  /** Consecutive speech frames needed. */
  holdFrames?: number;
}

export interface VoiceSample {
  /** 0-1 loudness of this frame. */
  rms: number;
  /** A person is speaking (after holdFrames). */
  speaking: boolean;
}

const VOICE_LOW_HZ = 300;
const VOICE_HIGH_HZ = 3400;
const ALL_LOW_HZ = 80;
const ALL_HIGH_HZ = 8000;

/** The detector's decision for one frame, from raw analyser data (testable without audio). */
export class VoiceDetector {
  private floor: number;
  private run = 0;
  private readonly minLevel: number;
  private readonly aboveNoise: number;
  private readonly voiceBand: number;
  private readonly holdFrames: number;

  constructor(options: VoiceDetectorOptions = {}) {
    this.minLevel = options.minLevel ?? 0.015;
    this.aboveNoise = options.aboveNoise ?? 2.5;
    this.voiceBand = options.voiceBand ?? 0.45;
    this.holdFrames = options.holdFrames ?? 3;
    // Start at the quietest background, not at the first sound heard: the
    // learner may already be talking when the microphone opens.
    this.floor = this.minLevel / this.aboveNoise;
  }

  /** `samples`: time-domain bytes (128 = silence); `spectrum`: frequency
   * magnitudes in bytes; `binHz`: the width of one spectrum bin. */
  sample(samples: Uint8Array, spectrum: Uint8Array, binHz: number): VoiceSample {
    let sum = 0;
    for (const value of samples) {
      const centred = (value - 128) / 128;
      sum += centred * centred;
    }
    const rms = Math.sqrt(sum / Math.max(1, samples.length));

    let voice = 0;
    let all = 0;
    for (let bin = 0; bin < spectrum.length; bin += 1) {
      const hz = bin * binHz;
      if (hz < ALL_LOW_HZ || hz > ALL_HIGH_HZ) continue;
      const energy = spectrum[bin] * spectrum[bin];
      all += energy;
      if (hz >= VOICE_LOW_HZ && hz <= VOICE_HIGH_HZ) voice += energy;
    }
    // No spectrum (a device or test without frequency data): loudness decides.
    const bandShare = all > 0 ? voice / all : 1;

    const loudEnough = rms >= Math.max(this.minLevel, this.floor * this.aboveNoise);
    const voiced = loudEnough && bandShare >= this.voiceBand;
    // The background follows quiet frames quickly and loud ones slowly, and
    // never learns from speech itself.
    if (rms < this.floor) this.floor = this.floor * 0.9 + rms * 0.1;
    else if (!voiced) this.floor = this.floor * 0.99 + rms * 0.01;

    this.run = voiced ? this.run + 1 : 0;
    return { rms, speaking: this.run >= this.holdFrames };
  }

  /** The room's current background level (for tests and diagnostics). */
  get noiseFloor(): number {
    return this.floor;
  }
}

/** Reads one frame from a Web Audio analyser into a detector. */
export function analyserReader(analyser: AnalyserNode, detector: VoiceDetector): () => VoiceSample {
  const samples = new Uint8Array(analyser.fftSize);
  const hasSpectrum = typeof analyser.getByteFrequencyData === "function";
  const spectrum = new Uint8Array(hasSpectrum ? analyser.frequencyBinCount || analyser.fftSize / 2 : 0);
  const binHz = (analyser.context?.sampleRate || 48000) / analyser.fftSize;
  return () => {
    analyser.getByteTimeDomainData(samples);
    if (hasSpectrum) analyser.getByteFrequencyData(spectrum);
    return detector.sample(samples, spectrum, binHz);
  };
}

/**
 * Listens for the learner starting to talk (while Boss is speaking, so they
 * can interrupt). The microphone's echo cancellation removes Boss's own
 * voice; the bar is set higher than normal listening so leftover echo or
 * background noise does not interrupt. `onSpeech` fires once. Returns stop.
 */
export function watchForSpeech(onSpeech: () => void, minMs = 300): () => void {
  let stopped = false;
  let cleanup = () => {};
  const stop = () => {
    stopped = true;
    cleanup();
  };
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return stop;
  const AudioContextCtor = window.AudioContext
    || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) return stop;
  void acquireMicrophone().then((stream) => {
    if (stopped) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    const context = new AudioContextCtor();
    void context.resume?.();
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    context.createMediaStreamSource(stream).connect(analyser);
    const detector = new VoiceDetector({ minLevel: 0.03, aboveNoise: 3.5, voiceBand: 0.5, holdFrames: 1 });
    const read = analyserReader(analyser, detector);
    let since = 0;
    const timer = window.setInterval(() => {
      if (stopped) return;
      const { speaking } = read();
      const now = performance.now();
      since = speaking ? since || now : 0;
      if (since && now - since >= minMs) {
        stop();
        onSpeech();
      }
    }, 20);
    cleanup = () => {
      window.clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
      if (context.state !== "closed") void context.close();
    };
  }).catch(() => {
    // No microphone: the learner can still tap the logo to interrupt.
  });
  return stop;
}
