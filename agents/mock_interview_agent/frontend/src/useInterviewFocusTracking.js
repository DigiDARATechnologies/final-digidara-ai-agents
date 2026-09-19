import { useEffect, useRef, useState } from "react";
import { recordFocusEvent } from "./api";
import { reportClientWarning } from "./utils/clientLogger";


const BLUR_GRACE_MS = 1000;

function newEventUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (token) => {
    const random = Math.floor(Math.random() * 16);
    const value = token === "x" ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

/** Track deduplicated visibility/window-focus episodes for one live interview. */
export default function useInterviewFocusTracking(interviewId, active = true) {
  const [warning, setWarning] = useState(null);
  const [summary, setSummary] = useState({
    focus_loss_count: 0,
    focus_loss_total_seconds: 0,
    integrity_flagged: false,
  });
  const eventRef = useRef(null);
  const blurTimerRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!active || !interviewId) return undefined;

    function confirmAway(source) {
      if (eventRef.current) return;
      if (blurTimerRef.current) {
        window.clearTimeout(blurTimerRef.current);
        blurTimerRef.current = null;
      }
      const event = {
        event_uuid: newEventUuid(),
        source,
        client_left_at: Date.now(),
      };
      eventRef.current = event;
      event.leftPromise = recordFocusEvent(interviewId, {
        event_uuid: event.event_uuid,
        action: "left",
        source,
      });
      event.leftPromise.then((payload) => {
        if (mountedRef.current) setSummary(payload);
      }).catch((error) => {
        reportClientWarning("focus_event_start_failed", error, {
          interview_id: interviewId,
          event_uuid: event.event_uuid,
        });
        if (mountedRef.current) {
          setWarning(
            "Focus loss was detected, but it could not be saved. "
            + "Your interview will continue normally."
          );
        }
      });
    }

    function finishAway() {
      if (blurTimerRef.current) {
        window.clearTimeout(blurTimerRef.current);
        blurTimerRef.current = null;
      }
      const event = eventRef.current;
      if (!event) return;
      if (document.visibilityState === "hidden") return;
      if (typeof document.hasFocus === "function" && !document.hasFocus()) return;

      eventRef.current = null;
      const clientSeconds = Math.max(
        0,
        Math.round((Date.now() - event.client_left_at) / 1000)
      );
      async function persistReturn() {
        try {
          await event.leftPromise;
        } catch (leftError) {
          // Retry the opening write once before closing it. This covers a
          // transient failure without inventing client-authored timestamps.
          reportClientWarning("focus_event_start_retrying", leftError, {
            interview_id: interviewId,
            event_uuid: event.event_uuid,
          });
          await recordFocusEvent(interviewId, {
            event_uuid: event.event_uuid,
            action: "left",
            source: event.source,
          });
        }
        return recordFocusEvent(interviewId, {
          event_uuid: event.event_uuid,
          action: "returned",
        });
      }

      persistReturn().then((payload) => {
        if (!mountedRef.current) return;
        setSummary(payload);
        const awaySeconds = Number(payload.away_seconds ?? clientSeconds);
        setWarning(
          `You left the interview window for ${awaySeconds} seconds. `
          + "This has been recorded, but your interview will continue normally."
        );
      }).catch((error) => {
        reportClientWarning("focus_event_return_failed", error, {
          interview_id: interviewId,
          event_uuid: event.event_uuid,
        });
        if (mountedRef.current) {
          setWarning(
            "Focus loss was detected, but it could not be saved. "
            + "Your interview will continue normally."
          );
        }
      });
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") {
        confirmAway("visibility");
      } else {
        finishAway();
      }
    }

    function handleBlur() {
      if (eventRef.current || blurTimerRef.current) return;
      blurTimerRef.current = window.setTimeout(() => {
        blurTimerRef.current = null;
        confirmAway("window_blur");
      }, BLUR_GRACE_MS);
    }

    function handleFocus() {
      finishAway();
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("focus", handleFocus);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("focus", handleFocus);
      if (blurTimerRef.current) {
        window.clearTimeout(blurTimerRef.current);
        blurTimerRef.current = null;
      }
      const event = eventRef.current;
      eventRef.current = null;
      if (event) {
        recordFocusEvent(interviewId, {
          event_uuid: event.event_uuid,
          action: "returned",
        }).catch((error) => {
          reportClientWarning("focus_event_cleanup_failed", error, {
            interview_id: interviewId,
            event_uuid: event.event_uuid,
          });
        });
      }
    };
  }, [active, interviewId]);

  return { warning, summary };
}
