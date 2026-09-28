/** Persisted state for one Resume Builder chat's canvas. Deliberately thin: the
 * resume document itself lives on the server (see resumeBuilderApi.ts) and the
 * canvas re-fetches it by `resumeId` on load -- this is just the pointer that
 * survives a page refresh, not a step machine (there is no "step 7" to resume). */
export type ResumeCanvasStep = "empty" | "editing" | "ready";

export interface ResumeCanvasState {
  step: ResumeCanvasStep;
  resumeId?: number;
  resumeTitle?: string;
  atsScore?: number;
}

export const createInitialResumeCanvasState = (): ResumeCanvasState => ({ step: "empty" });
